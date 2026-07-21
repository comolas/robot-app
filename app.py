import os
import time
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from rag_engine import RAGEngine
import hashlib
import json
import uuid
from pathlib import Path

AUDIO_MAX_AGE_DAYS = 7

def cleanup_audio(max_age_days: int = AUDIO_MAX_AGE_DAYS) -> dict:
    """audio_output klasöründeki eski ses dosyalarını sil. Kalıcı cache_* dosyaları korunur."""
    audio_dir = Path("audio_output")
    if not audio_dir.exists():
        return {"deleted": 0, "kept": 0}

    cutoff = time.time() - max_age_days * 86400
    deleted, kept = 0, 0

    for f in audio_dir.iterdir():
        if f.suffix not in (".mp3", ".webm") or f.name.startswith("cache_"):
            kept += 1
            continue
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
        else:
            kept += 1

    print(f"✓ Audio temizleme: {deleted} dosya silindi, {kept} dosya korundu.")
    return {"deleted": deleted, "kept": kept}

async def _periodic_cleanup():
    """7 günde bir audio temizliği çalıştır."""
    while True:
        await asyncio.sleep(AUDIO_MAX_AGE_DAYS * 86400)
        cleanup_audio()

load_dotenv(override=True)

@asynccontextmanager
async def lifespan(app):
    """Uygulama başlarken RAG engine'i yükle"""
    global rag_engine
    cleanup_audio()
    asyncio.create_task(_periodic_cleanup())
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY bulunamadı!")
    rag_engine = RAGEngine(api_key)
    if os.path.exists("./vectordb"):
        print("Mevcut vektör veritabanı yükleniyor...")
        rag_engine.load_existing_db()
    else:
        # Önce web sitesinden yükle, başarısız olursa markdown'dan
        school_url = os.getenv("SCHOOL_WEBSITE_URL", "")
        if school_url:
            try:
                print(f"Web sitesi taranıyor: {school_url}")
                char_count = rag_engine.load_from_url(school_url)
                print(f"Web sitesinden {char_count} karakter yüklendi.")
            except Exception as e:
                print(f"Web sitesi taranamadı: {e}")
                if os.path.exists("./data/okul_bilgileri.md"):
                    print("Markdown dosyasından yükleniyor...")
                    rag_engine.load_documents("./data/okul_bilgileri.md")
        elif os.path.exists("./data/okul_bilgileri.md"):
            print("Vektör veritabanı oluşturuluyor...")
            rag_engine.load_documents("./data/okul_bilgileri.md")
        else:
            print("UYARI: Veri kaynağı bulunamadı!")
    yield

app = FastAPI(title="Okul Tanıtım Robot API", lifespan=lifespan)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servisler
rag_engine = None
tts_service = None
english_teacher = None

# TTS'i opsiyonel yap
try:
    from tts_service import TTSService
    tts_service = TTSService()
    print("✓ Google Cloud TTS yüklendi")
except Exception as e:
    print(f"⚠ Google Cloud TTS yüklenemedi: {e}")
    print("TTS olmadan devam ediliyor...")

# STT ve EnglishTeacher
try:
    from stt_service import STTService
    from english_teacher import EnglishTeacher
    stt_service = STTService()
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if tts_service and api_key:
        english_teacher = EnglishTeacher(api_key, tts_service, stt_service)
        print("✓ EnglishTeacher yüklendi")
except Exception as e:
    print(f"⚠ EnglishTeacher yüklenemedi: {e}")

# ScienceTeacher
science_teacher = None
try:
    from science_teacher import ScienceTeacher
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if tts_service and api_key:
        science_teacher = ScienceTeacher(api_key, tts_service)
        print("✓ ScienceTeacher yüklendi")
except Exception as e:
    print(f"⚠ ScienceTeacher yüklenemedi: {e}")

class Question(BaseModel):
    question: str

# WebScraper (galeri cache icin global)
_web_scraper_instance = None
def get_web_scraper():
    global _web_scraper_instance
    if _web_scraper_instance is None:
        school_url = os.getenv("SCHOOL_WEBSITE_URL", "")
        if school_url:
            from web_scraper import WebScraper
            _web_scraper_instance = WebScraper(school_url)
    return _web_scraper_instance

class Answer(BaseModel):
    answer: str
    audio_path: str
    questions: list[str] = []
    answers: list[str] = []
    question_audio_paths: list[str] = []
    pdf_name: str = ""
    language: str = ""

class EvaluateRequest(BaseModel):
    question: str
    audio_path: str
    student_name: str


@app.post("/ask", response_model=Answer)
async def ask_question(question: Question):
    """Arduino'dan gelen soruyu yanıtla"""
    if not rag_engine:
        raise HTTPException(status_code=500, detail="RAG engine yüklenmedi")
    
    try:
        # Galeri komutu mu kontrol et
        q_lower = question.question.lower()
        gallery_keywords = ["gorsel", "görsel", "galeri", "foto", "resim", "gallery"]
        if any(k in q_lower for k in gallery_keywords):
            return Answer(
                answer="__GALLERY__",
                audio_path="",
            )

        # Kütüphane komutu mu kontrol et
        library_keywords = ["kütüphane", "kutuphane", "kitaplık", "kitaplik", "library", "ödünç", "odunc"]
        if any(k in q_lower for k in library_keywords):
            return Answer(
                answer="__LIBRARY__",
                audio_path="",
            )

        # PDF okuma komutu mu kontrol et
        pdf_cmd = rag_engine.parse_pdf_command(question.question)
        if pdf_cmd:
            try:
                pdf_name = Path(pdf_cmd["pdf"]).name
                pdf_name_lower = rag_engine._normalize_tr(pdf_name)
                is_english = "ingilizce" in pdf_name_lower or "english" in pdf_name_lower
                lang = "en" if is_english else "tr"
                tts_lang = "en-US" if is_english else "tr-TR"

                # PDF metnini oku
                import fitz
                doc = fitz.open(pdf_cmd["pdf"])
                page_num = pdf_cmd["page"]
                if page_num and 1 <= page_num <= len(doc):
                    page_text = doc[page_num - 1].get_text()
                else:
                    page_text = "\n".join(p.get_text() for p in doc)

                # TTS ile seslendir (doğru dilde)
                audio_filename = f"page_{hashlib.md5(page_text.encode()).hexdigest()}.mp3"
                audio_path = ""
                if tts_service:
                    cached_path = tts_service.text_to_speech_lang(page_text[:5000], audio_filename, language_code=tts_lang)
                    audio_path = f"/audio/{Path(cached_path).name}"

                page_info = f" (Sayfa {page_num})" if page_num else ""
                questions = []
                answers_list = []
                q_audio_paths = []

                # İngilizce kitap ise soru üret
                if is_english and english_teacher:
                    english_teacher.current_text = page_text
                    qa_pairs = english_teacher.generate_questions(3)
                    questions = [item["question"] for item in qa_pairs]
                    answers_list = [item.get("answer", "") for item in qa_pairs]
                    for q in questions:
                        qpath = english_teacher.ask_question_audio(q)
                        q_audio_paths.append(f"/audio/{Path(qpath).name}")

                questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
                answer = f"PDF okunuyor{page_info}:\n\n{page_text[:2000]}"
                if questions_text:
                    answer += f"\n\n---\n\nSorular:\n{questions_text}"

                return Answer(
                    answer=answer,
                    audio_path=audio_path,
                    questions=questions,
                    answers=answers_list,
                    question_audio_paths=q_audio_paths,
                    pdf_name=pdf_name,
                    language=lang,
                )
            except ValueError as e:
                return Answer(answer=str(e), audio_path="")

        # Normal okul sorusu
        answer = rag_engine.ask(question.question)
        
        audio_path = ""
        if tts_service:
            cached_path = tts_service.text_to_speech(answer)
            audio_path = f"/audio/{Path(cached_path).name}"
        
        return Answer(answer=answer, audio_path=audio_path)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Ses dosyasını indir"""
    audio_path = f"audio_output/{filename}"
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı")
    
    return FileResponse(audio_path, media_type="audio/mpeg")

@app.post("/audio/cleanup")
async def manual_cleanup():
    """Eski ses dosyalarını manuel olarak temizle"""
    result = cleanup_audio()
    return {"message": f"{result['deleted']} dosya silindi, {result['kept']} dosya korundu.", **result}

@app.post("/reload-data")
async def reload_data(source: str = "auto"):
    """Verileri yeniden yükle. source: auto, web, file"""
    global rag_engine
    api_key = os.getenv("GOOGLE_API_KEY")
    rag_engine = RAGEngine(api_key)

    school_url = os.getenv("SCHOOL_WEBSITE_URL", "")

    if source in ("auto", "web") and school_url:
        try:
            char_count = rag_engine.load_from_url(school_url)
            return {"message": f"Web sitesinden {char_count} karakter yüklendi.", "source": "web"}
        except Exception as e:
            if source == "web":
                return {"message": f"Web sitesi taranamadı: {e}", "source": "error"}

    if os.path.exists("./data/okul_bilgileri.md"):
        rag_engine.load_documents("./data/okul_bilgileri.md")
        return {"message": "Markdown dosyasından yüklendi.", "source": "file"}

    return {"message": "Veri kaynağı bulunamadı.", "source": "none"}

@app.get("/english/lessons")
async def list_lessons():
    """Lessons klasöründeki PDF dosyalarını listele"""
    lessons_dir = Path("data/lessons")
    if not lessons_dir.exists():
        return {"lessons": []}
    pdfs = []
    for f in lessons_dir.glob("*.pdf"):
        import fitz
        doc = fitz.open(str(f))
        pdfs.append({"name": f.name, "pages": len(doc)})
    return {"lessons": pdfs}

@app.get("/pdf/page-image")
async def pdf_page_image(pdf_name: str, page: int = 1, zoom: float = 2.0):
    """PDF sayfasını PNG resim olarak döndür"""
    import fitz
    pdf_path = Path("data/lessons") / pdf_name
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF bulunamadı")
    doc = fitz.open(str(pdf_path))
    if page < 1 or page > len(doc):
        raise HTTPException(status_code=400, detail=f"Geçersiz sayfa. PDF {len(doc)} sayfa.")
    mat = fitz.Matrix(zoom, zoom)
    pix = doc[page - 1].get_pixmap(matrix=mat)
    return Response(content=pix.tobytes("png"), media_type="image/png")

@app.post("/english/read-material")
async def read_material(pdf_path: str, page: int | None = None):
    """PDF materyalini sesli oku. page verilirse sadece o sayfayı okur."""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    # Lessons klasöründen dosya adıyla da erişilebilsin
    full_path = pdf_path if os.path.exists(pdf_path) else f"data/lessons/{pdf_path}"
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="PDF bulunamadı")
    try:
        audio_path = english_teacher.read_material(full_path, page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"audio_path": f"/audio/{Path(audio_path).name}", "text": english_teacher.current_text}

@app.get("/english/generate-questions")
async def generate_questions(num_questions: int = 3):
    """Yüklü metinden soru üret"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    qa_pairs = english_teacher.generate_questions(max(num_questions, 3))
    questions = [item["question"] for item in qa_pairs]
    answers = [item.get("answer", "") for item in qa_pairs]
    audio_paths = [english_teacher.ask_question_audio(q) for q in questions]
    return {"questions": questions, "answers": answers, "audio_paths": audio_paths}

@app.post("/english/pronunciation")
async def evaluate_pronunciation(
    audio: UploadFile = File(...),
    reference_text: str = Form(...),
    student_name: str = Form("anonymous"),
):
    """Telaffuz değerlendirmesi: ses dosyası + referans metin"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")

    # Ses dosyasını kaydet
    audio_dir = Path("audio_output")
    audio_dir.mkdir(exist_ok=True)
    temp_path = audio_dir / f"pron_input_{hashlib.md5(audio.filename.encode()).hexdigest()}.webm"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    try:
        result = english_teacher.evaluate_pronunciation(reference_text, str(temp_path), student_name)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class SimplifyRequest(BaseModel):
    text: str
    level: str = "A2"

class QuizRequest(BaseModel):
    text: str
    difficulty: str = "medium"
    num_questions: int = 5
    language: str = "en"

class VocabRequest(BaseModel):
    text: str
    level: str = "B1"

class DialogueStartRequest(BaseModel):
    scenario: str
    level: str = "B1"

@app.get("/english/dialogue/scenarios")
async def list_scenarios():
    """Mevcut diyalog senaryolarını listele"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    return {"scenarios": [
        {"id": k, "title": v["title"], "student_role": v["student_role"], "ai_role": v["role"]}
        for k, v in english_teacher.SCENARIOS.items()
    ]}

@app.post("/english/dialogue/start")
async def dialogue_start(req: DialogueStartRequest):
    """Diyalog senaryosu başlat"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    try:
        return english_teacher.dialogue_start(req.scenario, req.level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/english/dialogue/respond")
async def dialogue_respond(
    audio: UploadFile = File(...),
    scenario: str = Form(...),
    history: str = Form(...),
    level: str = Form("B1"),
):
    """Diyalogda öğrenci yanıtına AI cevabı"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")

    audio_dir = Path("audio_output")
    audio_dir.mkdir(exist_ok=True)
    temp_path = audio_dir / f"dlg_input_{uuid.uuid4().hex[:8]}.webm"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    try:
        hist = json.loads(history)
    except Exception:
        hist = []

    try:
        return english_teacher.dialogue_respond(scenario, hist, str(temp_path), level)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/english/quiz")
async def generate_quiz(req: QuizRequest):
    """Metinden sınav/quiz oluştur"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    if req.difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(status_code=400, detail="Geçerli zorluk: easy, medium, hard")
    result = english_teacher.generate_quiz(req.text, req.difficulty, max(req.num_questions, 3), req.language)
    return result

@app.post("/english/vocabulary")
async def extract_vocabulary(req: VocabRequest):
    """Metinden kelime listesi çıkar"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    try:
        result = english_teacher.extract_vocabulary(req.text, req.level)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/english/simplify")
async def simplify_text(req: SimplifyRequest):
    """Metni hedef CEFR seviyesine uyarla"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    try:
        result = english_teacher.simplify_text(req.text, req.level)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/english/evaluate")
async def evaluate_answer(req: EvaluateRequest):
    """Öğrencinin cevabını değerlendir"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    if not os.path.exists(req.audio_path):
        raise HTTPException(status_code=404, detail="Ses dosyası bulunamadı")
    result = english_teacher.evaluate_answer(req.question, req.audio_path, req.student_name)
    return result

@app.get("/english/student/{student_name}")
async def get_student_history(student_name: str):
    """Öğrencinin geçmiş değerlendirmelerini getir"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    return english_teacher.get_student_history(student_name)

@app.get("/english/students")
async def list_students():
    """Kayıtlı öğrenci listesi"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    return {"students": english_teacher.list_students()}

@app.get("/english/report/{student_name}")
async def get_student_report(student_name: str):
    """Öğrenci performans raporu"""
    if not english_teacher:
        raise HTTPException(status_code=500, detail="EnglishTeacher yüklenmedi")
    report = english_teacher.get_student_report(student_name)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report

class SimulationRequest(BaseModel):
    text: str

@app.get("/school/gallery")
async def school_gallery():
    """Okul web sitesinden galeri görsellerini çek (cache'li)"""
    scraper = get_web_scraper()
    if not scraper:
        raise HTTPException(status_code=400, detail="SCHOOL_WEBSITE_URL ayarlanmamış")
    images = scraper.scrape_gallery()
    return {"images": images, "count": len(images)}

@app.post("/science/simulation")
async def generate_simulation(req: SimulationRequest):
    """Sayfa metninden deney simülasyonu üret"""
    if not science_teacher:
        raise HTTPException(status_code=500, detail="ScienceTeacher yüklenmedi")
    result = science_teacher.generate_simulation(req.text)
    return result

@app.post("/voice-ask")
async def voice_ask(audio: UploadFile = File(...)):
    """Sesli komut: ses -> metin -> cevap"""
    audio_dir = Path("audio_output")
    audio_dir.mkdir(exist_ok=True)
    temp_path = audio_dir / f"voice_input_{uuid.uuid4().hex[:8]}.webm"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    # STT ile metne çevir
    transcript = ""
    if stt_service:
        try:
            transcript = stt_service.transcribe(str(temp_path), language_code="tr-TR")
        except Exception:
            pass
    if not transcript and stt_service:
        try:
            transcript = stt_service.transcribe(str(temp_path), language_code="en-US")
        except Exception:
            pass

    if not transcript:
        return {"transcript": "", "error": "Ses anlaşılamadı. Lütfen tekrar deneyin."}

    return {"transcript": transcript}

@app.get("/")
async def root():
    return {"status": "ok", "service": "robot-api"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
