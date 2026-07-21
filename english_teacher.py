import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
import fitz  # PyMuPDF


class EnglishTeacher:
    def __init__(self, api_key: str, tts_service, stt_service):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=api_key,
            temperature=0.4,
        )
        self.tts = tts_service
        self.stt = stt_service
        self.evaluations_dir = Path("data/evaluations")
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)
        self.current_text = ""

    def _extract_text(self, content) -> str:
        """Gemini content'ini string'e çevir (str veya list olabilir)"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, str):
                    parts.append(c)
                elif isinstance(c, dict) and "text" in c:
                    parts.append(c["text"])
                else:
                    parts.append(str(c))
            return "".join(parts)
        return str(content)

    # ── PDF ──────────────────────────────────────────────────────────────────

    def load_pdf(self, pdf_path: str, page: int | None = None) -> str:
        """PDF'den metin çıkar. page verilirse sadece o sayfayı okur (1-tabanlı)."""
        doc = fitz.open(pdf_path)
        if page is not None:
            if page < 1 or page > len(doc):
                raise ValueError(f"Sayfa {page} bulunamadı. PDF {len(doc)} sayfa.")
            self.current_text = doc[page - 1].get_text()
        else:
            self.current_text = "\n".join(p.get_text() for p in doc)
        return self.current_text

    def get_page_count(self, pdf_path: str) -> int:
        """PDF sayfa sayısını döndür"""
        return len(fitz.open(pdf_path))

    def read_material(self, pdf_path: str, page: int | None = None) -> str:
        """PDF'i yükle ve TTS ile sesli oku, ses dosyası yolunu döndür"""
        text = self.load_pdf(pdf_path, page)
        filename = f"material_{uuid.uuid4().hex[:8]}.mp3"
        audio_path = self.tts.text_to_speech_lang(text, filename, language_code="en-US")
        return audio_path

    # ── SORU ÜRETME ──────────────────────────────────────────────────────────

    def generate_questions(self, num_questions: int = 3) -> list[dict]:
        """Mevcut metinden İngilizce soru ve cevaplar üret. En az num_questions adet."""
        if not self.current_text:
            raise ValueError("Önce load_pdf() çağırın.")

        prompt = f"""Based on the following English text, generate exactly {num_questions} reading comprehension questions WITH detailed answers.

Rules:
- Questions and answers must be in English
- Each answer should be 1-2 sentences
- Return ONLY a valid JSON array, no markdown, no explanation

Text:
{self.current_text[:3000]}

Required JSON format:
[{{"question": "What is...?", "answer": "The text states that..."}}, {{"question": "Why does...?", "answer": "Because..."}}]"""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()

            # JSON array'i bul
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                items = json.loads(match.group())
                if items and isinstance(items[0], dict) and "question" in items[0]:
                    return items[:num_questions] if len(items) >= num_questions else items
                if items and isinstance(items[0], str):
                    return [{"question": q, "answer": ""} for q in items[:num_questions]]

            # Satır satır soru çıkar
            questions = re.findall(r'\d+\.\s*(.+\?)', response)
            if questions:
                return [{"question": q, "answer": ""} for q in questions[:num_questions]]
        except Exception as e:
            print(f"Soru üretme hatası: {e}")

        return [{"question": "What is this text about?", "answer": "This text discusses the topic presented on the page."}]

    def ask_question_audio(self, question: str) -> str:
        """Soruyu TTS ile sesli sor, ses dosyası yolunu döndür"""
        filename = f"question_{uuid.uuid4().hex[:8]}.mp3"
        return self.tts.text_to_speech_lang(question, filename, language_code="en-US")

    # ── DEĞERLENDİRME ────────────────────────────────────────────────────────

    def evaluate_answer(self, question: str, audio_path: str, student_name: str) -> dict:
        """Öğrencinin sesli cevabını değerlendir ve kaydet"""
        transcript = self.stt.transcribe(audio_path, language_code="en-US")

        prompt = f"""You are an English language teacher evaluating a student's spoken answer.

Question: {question}
Student's answer (transcribed): {transcript}
Reference text: {self.current_text[:2000]}

Evaluate the student's answer and return a JSON object with these fields:
- score: integer 1-10
- grammar_feedback: string
- vocabulary_feedback: string
- content_feedback: string
- overall_feedback: string (in Turkish, to be spoken aloud)

Return only valid JSON, nothing else."""

        raw = self.llm.invoke(prompt).content
        response = self._extract_text(raw)
        response = response.replace("```json", "").replace("```", "").strip()

        # JSON objesini bul
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            evaluation = json.loads(match.group())
        else:
            evaluation = json.loads(response)
        evaluation["transcript"] = transcript
        evaluation["question"] = question

        self._save_evaluation(student_name, evaluation)

        # Geri bildirimi sesli ver
        feedback_audio = self.tts.text_to_speech_lang(
            evaluation["overall_feedback"],
            f"feedback_{uuid.uuid4().hex[:8]}.mp3",
            language_code="tr-TR",
        )
        evaluation["feedback_audio"] = feedback_audio
        return evaluation

    # ── TELAFFUZ DEĞERLENDİRME ───────────────────────────────────────────────

    def evaluate_pronunciation(self, reference_text: str, audio_path: str, student_name: str = "anonymous") -> dict:
        """Öğrencinin sesli okumasını referans metinle karşılaştırarak telaffuz değerlendir"""
        transcript = self.stt.transcribe(audio_path, language_code="en-US")

        prompt = f"""You are an expert English pronunciation evaluator.

The student was asked to read the following reference text aloud.
Compare the student's spoken output (transcribed by speech-to-text) with the reference text.

Reference text:
{reference_text[:2000]}

Student's transcription:
{transcript}

Analyze and return a JSON object with these fields:
- score: integer 1-10 (overall pronunciation score)
- accuracy_percent: integer 0-100 (word match percentage)
- mispronounced_words: array of objects, each with "word" (the correct word), "spoken_as" (what student said or "skipped" if missing), "tip" (short pronunciation tip in Turkish)
- skipped_words: array of strings (words in reference but missing in transcription)
- extra_words: array of strings (words in transcription but not in reference)
- fluency_feedback: string (feedback about speaking pace and flow, in Turkish)
- overall_feedback: string (general feedback and encouragement, in Turkish)

Return ONLY valid JSON, nothing else."""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()

            match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(match.group()) if match else json.loads(response)
        except Exception as e:
            print(f"Telaffuz değerlendirme hatası (Gemini): {e}")
            # Gemini başarısız olursa lokal kelime karşılaştırma yap
            result = self._local_pronunciation_eval(reference_text, transcript)

        result["transcript"] = transcript
        result["reference_text"] = reference_text[:500]

        # Sesli geri bildirim
        feedback_audio = self.tts.text_to_speech_lang(
            result["overall_feedback"],
            f"pron_feedback_{uuid.uuid4().hex[:8]}.mp3",
            language_code="tr-TR",
        )
        result["feedback_audio"] = f"/audio/{Path(feedback_audio).name}"

        # Kaydet
        self._save_evaluation(student_name, {"type": "pronunciation", **result})
        return result

    # ── LOKAL TELAFFUZ DEĞERLENDİRME (FALLBACK) ─────────────────────────────

    def _local_pronunciation_eval(self, reference_text: str, transcript: str) -> dict:
        """Gemini kullanılamadığında basit kelime karşılaştırma ile değerlendirme"""
        ref_words = re.findall(r'[a-zA-Z\']+', reference_text.lower())
        spoken_words = re.findall(r'[a-zA-Z\']+', transcript.lower())

        ref_set = set(ref_words)
        spoken_set = set(spoken_words)

        matched = ref_set & spoken_set
        skipped = list(ref_set - spoken_set)
        extra = list(spoken_set - ref_set)

        accuracy = int(len(matched) / len(ref_set) * 100) if ref_set else 0
        score = min(10, max(1, accuracy // 10))

        mispronounced = [{"word": w, "spoken_as": "atlandı", "tip": "Bu kelimeyi tekrar okumayı deneyin."} for w in skipped[:10]]

        if accuracy >= 80:
            feedback = f"Harika! Kelimelerin %{accuracy}'ini doğru okudunuz. Devam edin!"
        elif accuracy >= 50:
            feedback = f"Kelimelerin %{accuracy}'ini doğru okudunuz. Atladığınız kelimelere dikkat edin."
        else:
            feedback = f"Kelimelerin %{accuracy}'ini doğru okudunuz. Metni tekrar dinleyip yeniden okumayı deneyin."

        return {
            "score": score,
            "accuracy_percent": accuracy,
            "mispronounced_words": mispronounced,
            "skipped_words": skipped[:15],
            "extra_words": extra[:10],
            "fluency_feedback": f"Toplam {len(ref_words)} kelimeden {len(matched)} tanesini doğru okudunuz.",
            "overall_feedback": feedback,
        }

    # ── SINAV / QUIZ OLUŞTURUCU ───────────────────────────────────────────

    def generate_quiz(self, text: str, difficulty: str = "medium", num_questions: int = 5, language: str = "en") -> dict:
        """Metinden farklı tipte sınav soruları üret"""
        diff_desc = {
            "easy": "simple vocabulary, short sentences, basic grammar (A1-A2)",
            "medium": "intermediate vocabulary, moderate complexity (B1-B2)",
            "hard": "advanced vocabulary, complex structures (C1-C2)",
        }
        diff_text = diff_desc.get(difficulty, diff_desc["medium"])
        lang_instruction = "Türkçe yaz. Sorular, şıklar ve açıklamalar Türkçe olmalı." if language == "tr" else "Write in English. Questions, options and explanations must be in English."

        prompt = f"""You are an exam creator. Generate a quiz based on the text below.

{lang_instruction}

Difficulty: {difficulty} ({diff_text})
Generate exactly {num_questions} questions total with a MIX of these types:
- multiple_choice: 4 options (A/B/C/D), one correct
- fill_blank: sentence with ___ blank, one correct answer
- matching: 3-4 pairs to match (words to definitions)

Text:
{text[:3000]}

Return ONLY a valid JSON object:
{{{{
  "title": "Quiz title",
  "difficulty": "{difficulty}",
  "questions": [
    {{{{
      "type": "multiple_choice",
      "question": "What is...?",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct": "A",
      "explanation": "Because..."
    }}}},
    {{{{
      "type": "fill_blank",
      "question": "The cat ___ on the mat.",
      "correct": "sat",
      "explanation": "Past tense of sit"
    }}}},
    {{{{
      "type": "matching",
      "question": "Match the words with their meanings",
      "pairs": [{{"left": "word1", "right": "meaning1"}}, {{"left": "word2", "right": "meaning2"}}],
      "explanation": "Vocabulary from the text"
    }}}}
  ]
}}}}"""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()

            match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(match.group()) if match else json.loads(response)

            if "questions" not in result:
                result = {"questions": []}
        except Exception as e:
            print(f"Quiz üretme hatası: {e}")
            result = {
                "title": "Quiz",
                "difficulty": difficulty,
                "questions": [],
                "error": "Quiz üretilemedi. Lütfen tekrar deneyin.",
            }

        result["difficulty"] = difficulty
        return result

    # ── KONUŞMA PRATİĞİ (DIALOGUE PRACTICE) ────────────────────────────

    SCENARIOS = {
        "restaurant": {"title": "Restoranda Sipariş", "desc": "You are a waiter at a restaurant. Greet the customer and take their order.", "role": "waiter", "student_role": "customer"},
        "hotel": {"title": "Otel Resepsiyonu", "desc": "You are a hotel receptionist. Help the guest check in.", "role": "receptionist", "student_role": "guest"},
        "directions": {"title": "Yol Tarifi", "desc": "You are a local person. A tourist asks you for directions to the museum.", "role": "local", "student_role": "tourist"},
        "shopping": {"title": "Alışveriş", "desc": "You are a shop assistant. Help the customer find what they need.", "role": "shop assistant", "student_role": "customer"},
        "doctor": {"title": "Doktor Ziyareti", "desc": "You are a doctor. Ask the patient about their symptoms.", "role": "doctor", "student_role": "patient"},
        "airport": {"title": "Havalimanı", "desc": "You are an airport check-in agent. Help the passenger.", "role": "agent", "student_role": "passenger"},
        "job_interview": {"title": "İş Görüşmesi", "desc": "You are an interviewer. Conduct a simple job interview.", "role": "interviewer", "student_role": "candidate"},
    }

    def dialogue_start(self, scenario_id: str, level: str = "B1") -> dict:
        """Diyalog senaryosu başlat"""
        scenario = self.SCENARIOS.get(scenario_id)
        if not scenario:
            raise ValueError(f"Geçersiz senaryo. Geçerli: {', '.join(self.SCENARIOS.keys())}")

        system_prompt = f"""You are playing the role of a {scenario['role']} in a dialogue practice.
Scenario: {scenario['desc']}
The student is the {scenario['student_role']}.
Level: {level} (adjust your language complexity accordingly)

Rules:
- Speak naturally as a {scenario['role']}
- Keep responses 1-3 sentences
- After each response, wait for the student
- Be encouraging and patient
- Use vocabulary appropriate for {level} level

Start the conversation with a greeting."""

        try:
            raw = self.llm.invoke(system_prompt).content
            ai_message = self._extract_text(raw).strip()
        except Exception as e:
            print(f"Diyalog başlatma hatası: {e}")
            greetings = {
                "restaurant": "Hello! Welcome to our restaurant. How can I help you today?",
                "hotel": "Good evening! Welcome to Grand Hotel. Do you have a reservation?",
                "directions": "Hi there! You look a bit lost. Can I help you find something?",
                "shopping": "Hello! Welcome to our store. Are you looking for something special?",
                "doctor": "Good morning! Please have a seat. What seems to be the problem?",
                "airport": "Hello! May I see your passport and ticket, please?",
                "job_interview": "Good morning! Please have a seat. Tell me a little about yourself.",
            }
            ai_message = greetings.get(scenario_id, "Hello! How can I help you?")

        fname = f"dlg_{uuid.uuid4().hex[:8]}.mp3"
        audio = self.tts.text_to_speech_lang(ai_message, fname, language_code="en-US")

        return {
            "scenario_id": scenario_id,
            "scenario_title": scenario["title"],
            "student_role": scenario["student_role"],
            "ai_role": scenario["role"],
            "level": level,
            "ai_message": ai_message,
            "ai_audio": f"/audio/{Path(audio).name}",
            "history": [{"role": "ai", "message": ai_message}],
        }

    def dialogue_respond(self, scenario_id: str, history: list, student_audio_path: str, level: str = "B1") -> dict:
        """Öğrencinin sesli yanıtına AI cevabı üret"""
        scenario = self.SCENARIOS.get(scenario_id)
        if not scenario:
            raise ValueError("Geçersiz senaryo")

        student_text = self.stt.transcribe(student_audio_path, language_code="en-US")
        history.append({"role": "student", "message": student_text})

        conv_text = "\n".join(f"{m['role'].upper()}: {m['message']}" for m in history)

        prompt = f"""You are a {scenario['role']} in a dialogue practice with a {level} level English student.
Scenario: {scenario['desc']}

Conversation so far:
{conv_text}

Continue the conversation naturally as the {scenario['role']}.
Keep your response 1-3 sentences, appropriate for {level} level.
If the conversation has reached a natural ending (after 4-6 exchanges), add [END] at the very end.

Return ONLY your dialogue line (and optionally [END]), nothing else."""

        try:
            raw = self.llm.invoke(prompt).content
            ai_message = self._extract_text(raw).strip()
        except Exception as e:
            print(f"Diyalog yanıt hatası: {e}")
            ai_message = "That sounds great! Is there anything else I can help you with? [END]"

        is_ended = "[END]" in ai_message
        ai_message = ai_message.replace("[END]", "").strip()
        history.append({"role": "ai", "message": ai_message})

        fname = f"dlg_{uuid.uuid4().hex[:8]}.mp3"
        audio = self.tts.text_to_speech_lang(ai_message, fname, language_code="en-US")

        result = {
            "student_text": student_text,
            "ai_message": ai_message,
            "ai_audio": f"/audio/{Path(audio).name}",
            "history": history,
            "ended": is_ended,
        }

        if is_ended:
            result["evaluation"] = self._evaluate_dialogue(scenario, history, level)

        return result

    def _evaluate_dialogue(self, scenario: dict, history: list, level: str) -> dict:
        """Diyalog sonunda öğrenci performansını değerlendir"""
        student_msgs = [m["message"] for m in history if m["role"] == "student"]
        conv_text = "\n".join(f"{m['role'].upper()}: {m['message']}" for m in history)

        prompt = f"""Evaluate this English dialogue practice for a {level} level student.
Scenario: {scenario['desc']}
Student role: {scenario['student_role']}

Conversation:
{conv_text}

Return a JSON object:
{{{{
  "score": 1-10,
  "grammar_score": 1-10,
  "vocabulary_score": 1-10,
  "fluency_score": 1-10,
  "task_completion": 1-10,
  "strengths": ["strength1", "strength2"],
  "improvements": ["area1", "area2"],
  "feedback_tr": "Türkçe genel değerlendirme"
}}}}

Return ONLY valid JSON."""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw).replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', response, re.DOTALL)
            evaluation = json.loads(match.group()) if match else json.loads(response)
        except Exception as e:
            print(f"Diyalog değerlendirme hatası: {e}")
            total_words = sum(len(m.split()) for m in student_msgs)
            score = min(10, max(1, total_words // 5))
            evaluation = {
                "score": score,
                "grammar_score": score,
                "vocabulary_score": score,
                "fluency_score": score,
                "task_completion": score,
                "strengths": ["Participated in the dialogue"],
                "improvements": ["Try to use longer sentences"],
                "feedback_tr": f"Diyaloğa katıldınız, toplam {len(student_msgs)} yanıt verdiniz.",
            }

        fname = f"dlg_feedback_{uuid.uuid4().hex[:8]}.mp3"
        audio = self.tts.text_to_speech_lang(evaluation.get("feedback_tr", ""), fname, language_code="tr-TR")
        evaluation["feedback_audio"] = f"/audio/{Path(audio).name}"
        return evaluation

    # ── KELİME LİSTESİ ÇIKARMA (VOCABULARY BUILDER) ───────────────────────

    def extract_vocabulary(self, text: str, target_level: str = "B1") -> dict:
        """Metinden önemli kelimeleri, anlamlarını, örnek cümleleri ve CEFR seviyelerini çıkar"""
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        target_level = target_level.upper()
        if target_level not in valid_levels:
            raise ValueError(f"Geçersiz seviye: {target_level}")

        prompt = f"""You are an English vocabulary expert. Extract important vocabulary from the text for {target_level} level students.

Rules:
- Select 8-15 key words/phrases appropriate for {target_level} learners
- For each word provide: the word, part of speech, English definition, Turkish meaning, CEFR level (A1-C2), and an example sentence using the word
- Sort by CEFR level (easiest first)
- Return ONLY valid JSON, no markdown

Text:
{text[:3000]}

Required JSON format:
{{{{
  "target_level": "{target_level}",
  "words": [
    {{{{
      "word": "struggle",
      "pos": "verb",
      "definition": "to try very hard to do something difficult",
      "turkish": "mücadele etmek",
      "level": "B1",
      "example": "They struggle to find clean water."
    }}}}
  ]
}}}}"""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()

            match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(match.group()) if match else json.loads(response)
            if "words" not in result:
                result = {"words": []}
        except Exception as e:
            print(f"Kelime çıkarma hatası: {e}")
            result = self._local_vocabulary_extract(text)

        result["target_level"] = target_level

        # Her kelimenin telaffuzunu TTS ile oluştur
        for w in result.get("words", []):
            fname = f"vocab_{uuid.uuid4().hex[:8]}.mp3"
            audio = self.tts.text_to_speech_lang(w["word"], fname, language_code="en-US")
            w["audio_path"] = f"/audio/{Path(audio).name}"

        return result

    def _local_vocabulary_extract(self, text: str) -> dict:
        """Gemini başarısız olursa basit kelime çıkarma"""
        words = re.findall(r'[a-zA-Z]{4,}', text.lower())
        freq: dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        stop = {"this","that","with","from","they","their","have","been","were","will","would","could","should","about","which","there","these","those","them","than","then","also","into","some","other","more","very","when","what","your","each"}
        top = sorted([(w,c) for w,c in freq.items() if w not in stop], key=lambda x: -x[1])[:12]
        return {
            "words": [
                {"word": w, "pos": "", "definition": "", "turkish": "", "level": "", "example": "", "count": c}
                for w, c in top
            ]
        }

    # ── METİN SADELEŞTİRME / SEVİYE UYARLAMA ────────────────────────────────

    def simplify_text(self, text: str, target_level: str = "A2") -> dict:
        """Metni hedef CEFR seviyesine uyarla (A1, A2, B1, B2, C1, C2)"""
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        target_level = target_level.upper()
        if target_level not in valid_levels:
            raise ValueError(f"Geçersiz seviye: {target_level}. Geçerli: {', '.join(valid_levels)}")

        level_desc = {
            "A1": "very basic, simple present tense, common words only, very short sentences (5-8 words)",
            "A2": "elementary, simple tenses, basic vocabulary, short sentences (8-12 words)",
            "B1": "intermediate, common tenses, everyday vocabulary, moderate sentences",
            "B2": "upper-intermediate, varied tenses, wider vocabulary, complex sentences allowed",
            "C1": "advanced, all tenses, rich vocabulary, sophisticated sentence structures",
            "C2": "proficiency, native-like, academic vocabulary, nuanced expressions",
        }

        prompt = f"""You are an expert English language teacher adapting texts for different CEFR levels.

Rewrite the following text for {target_level} level students.

Level description: {level_desc[target_level]}

Rules:
- Keep the SAME meaning and key information
- Adjust vocabulary complexity to {target_level} level
- Adjust sentence length and grammar to {target_level} level
- Return ONLY a JSON object, no markdown, no explanation

Original text:
{text[:3000]}

Required JSON format:
{{"simplified_text": "...", "vocabulary_notes": [{{"word": "difficult word", "meaning": "simple explanation in Turkish"}}], "level": "{target_level}"}}"""

        try:
            raw = self.llm.invoke(prompt).content
            response = self._extract_text(raw)
            response = response.replace("```json", "").replace("```", "").strip()

            match = re.search(r'\{.*\}', response, re.DOTALL)
            result = json.loads(match.group()) if match else json.loads(response)
        except Exception as e:
            print(f"Metin sadeleştirme hatası: {e}")
            result = {
                "simplified_text": text[:2000],
                "vocabulary_notes": [],
                "level": target_level,
                "error": "Sadeleştirme yapılamadı, orijinal metin gösteriliyor.",
            }

        result["original_text"] = text[:500]
        result["level"] = target_level

        # Sadeleştirilmiş metni sesli oku
        audio_filename = f"simplified_{uuid.uuid4().hex[:8]}.mp3"
        audio_path = self.tts.text_to_speech_lang(
            result["simplified_text"], audio_filename, language_code="en-US"
        )
        result["audio_path"] = f"/audio/{Path(audio_path).name}"

        return result

    # ── KAYIT ────────────────────────────────────────────────────────────────

    def _save_evaluation(self, student_name: str, evaluation: dict):
        """Değerlendirmeyi JSON dosyasına kaydet"""
        student_file = self.evaluations_dir / f"{student_name}.json"

        records = []
        if student_file.exists():
            with open(student_file, "r", encoding="utf-8") as f:
                records = json.load(f)

        records.append({"timestamp": datetime.now().isoformat(), **evaluation})

        with open(student_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def get_student_history(self, student_name: str) -> list:
        """Öğrencinin geçmiş değerlendirmelerini getir"""
        student_file = self.evaluations_dir / f"{student_name}.json"
        if not student_file.exists():
            return []
        with open(student_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_students(self) -> list[str]:
        """Kayıtlı öğrenci isimlerini listele"""
        return [f.stem for f in self.evaluations_dir.glob("*.json")]

    def get_student_report(self, student_name: str) -> dict:
        """Öğrencinin performans raporunu üret"""
        records = self.get_student_history(student_name)
        if not records:
            return {"student_name": student_name, "error": "Kayıt bulunamadı."}

        pron_records = [r for r in records if r.get("type") == "pronunciation"]
        answer_records = [r for r in records if r.get("type") != "pronunciation" and "score" in r]

        report = {
            "student_name": student_name,
            "total_activities": len(records),
            "pronunciation": self._pron_stats(pron_records),
            "answers": self._answer_stats(answer_records),
            "timeline": self._build_timeline(records),
        }
        return report

    def _pron_stats(self, records: list) -> dict:
        if not records:
            return {"count": 0}
        scores = [r.get("score", 0) for r in records]
        accuracies = [r.get("accuracy_percent", 0) for r in records]

        # En çok yanlanan kelimeler
        word_freq: dict[str, int] = {}
        for r in records:
            for w in r.get("skipped_words", []):
                word_freq[w] = word_freq.get(w, 0) + 1
            for w in r.get("mispronounced_words", []):
                word = w["word"] if isinstance(w, dict) else str(w)
                word_freq[word] = word_freq.get(word, 0) + 1
        weak_words = sorted(word_freq.items(), key=lambda x: -x[1])[:10]

        return {
            "count": len(records),
            "avg_score": round(sum(scores) / len(scores), 1),
            "best_score": max(scores),
            "latest_score": scores[-1],
            "avg_accuracy": round(sum(accuracies) / len(accuracies), 1),
            "trend": self._calc_trend(scores),
            "weak_words": [{"word": w, "count": c} for w, c in weak_words],
        }

    def _answer_stats(self, records: list) -> dict:
        if not records:
            return {"count": 0}
        scores = [r.get("score", 0) for r in records]
        return {
            "count": len(records),
            "avg_score": round(sum(scores) / len(scores), 1),
            "best_score": max(scores),
            "latest_score": scores[-1],
            "trend": self._calc_trend(scores),
        }

    def _calc_trend(self, scores: list) -> str:
        if len(scores) < 2:
            return "neutral"
        recent = scores[-min(3, len(scores)):]
        older = scores[:max(1, len(scores) - 3)]
        diff = sum(recent) / len(recent) - sum(older) / len(older)
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        return "stable"

    def _build_timeline(self, records: list) -> list:
        return [
            {
                "date": r.get("timestamp", "")[:10],
                "type": r.get("type", "answer"),
                "score": r.get("score", 0),
                "accuracy": r.get("accuracy_percent"),
            }
            for r in records if "score" in r
        ]
