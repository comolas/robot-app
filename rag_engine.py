import os
import re
import pickle
import unicodedata
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

class RAGEngine:
    def __init__(self, api_key: str):
        # Lokal embedding modeli (ücretsiz, internet gerektirmez)
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key,
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=api_key,
            temperature=0.3
        )
        self.vectordb = None
        self.chain = None
        self.raw_content = ""
        self.db_path = Path("./vectordb")
        self.lessons_dir = Path("./data/lessons")
        
    def load_documents(self, markdown_path: str):
        """Markdown dosyasını yükle ve vektör veritabanına kaydet"""
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self._index_text(content)

    def load_from_url(self, url: str, max_pages: int = 120):
        """Web sitesini tarayıp vektör veritabanına kaydet"""
        from web_scraper import WebScraper
        scraper = WebScraper(url, max_pages=max_pages)
        content = scraper.scrape()
        if not content.strip():
            raise ValueError("Web sitesinden içerik çekilemedi.")
        # Markdown dosyasına da kaydet (yedek)
        with open("./data/okul_bilgileri_web.md", "w", encoding="utf-8") as f:
            f.write(content)
        self._index_text(content)
        return len(content)

    def _index_text(self, content: str):
        """Metni parçala ve vektör veritabanına kaydet"""
        self.raw_content = content
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_text(content)
        self.vectordb = FAISS.from_texts(
            texts=chunks,
            embedding=self.embeddings
        )
        self.db_path.mkdir(exist_ok=True)
        self.vectordb.save_local(str(self.db_path))
        self._create_chain()
        
    def load_existing_db(self):
        """Mevcut vektör veritabanını yükle"""
        web_cache = Path("./data/okul_bilgileri_web.md")
        file_cache = Path("./data/okul_bilgileri.md")
        if web_cache.exists():
            self.raw_content = web_cache.read_text(encoding="utf-8", errors="ignore")
        elif file_cache.exists():
            self.raw_content = file_cache.read_text(encoding="utf-8", errors="ignore")
        self.vectordb = FAISS.load_local(
            str(self.db_path),
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        
        self._create_chain()
    
    def _create_chain(self):
        """RAG chain oluştur"""
        template = """Sen Data Koleji Ovacık Mesleki ve Teknik Anadolu Lisesi'nin resmi tanıtım robotusun.

FORMATLAMA KURALLARI (MUTLAKA UYULMASI GEREKEN):
1. Cevaplarını MUTLAKA Markdown formatında döndür
1a. Kendini sadece ilk tanışma cevabında tanıt; takip eden cevaplarda doğrudan sorunun cevabına geç
2. Giriş cümlesinden sonra en fazla tek boş satır kullan
3. Başlıkları numaralı ve BÜYÜK HARFLE yaz (örnek: 1. AKADEMİK BAŞARILAR)
4. Başlıktan hemen sonra metne geç; başlık ile paragraf arasında boş satır bırakma
5. Paragraflar arasında en fazla tek boş satır kullan; art arda boş satır kullanma
6. Madde işareti kullanma, akıcı paragraflar yaz

ÖRNEK FORMAT:
İlk bilgi cevabında kısa bir tanıtım cümlesi kullanabilirsin. Takip eden cevaplarda bu cümleyi tekrar etme.

Eğer sorulan bilgi mevcut değilse: "Bu konuda detaylı bilgiye sahip değilim. Daha fazla bilgi için lütfen okul yönetimi ile iletişime geçiniz."

Bağlam: {context}

Soru: {question}

Cevap:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        retriever = self.vectordb.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10}
        )
        
        self.chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
    
    @staticmethod
    def _normalize_tr(text: str) -> str:
        """Normalize Turkish text for case-insensitive exact search."""
        mapping = str.maketrans({
            "\u00e7": "c", "\u011f": "g", "\u0131": "i", "\u00f6": "o", "\u015f": "s", "\u00fc": "u",
            "\u00c7": "c", "\u011e": "g", "\u0130": "i", "I": "i", "\u00d6": "o", "\u015e": "s", "\u00dc": "u",
        })
        value = text.translate(mapping).lower()
        value = unicodedata.normalize("NFKD", value)
        return "".join(ch for ch in value if not unicodedata.combining(ch))

    def answer_staff_question(self, question: str) -> str | None:
        """Use exact text search for staff, teacher, branch and department questions."""
        content = self.raw_content or self._read_cached_content()
        if not content.strip() or not self._looks_like_staff_question(question):
            return None

        context = self._find_staff_context(question, content)
        if not context:
            return None

        prompt = ChatPromptTemplate.from_template(
            """Sen Data Koleji'nin resmi tanitim robotusun.

Asagidaki baglam okulun web sitesinden cikarilmis egitim kadrosu ve personel bilgisidir.
Soruda bir kisi adi geciyorsa, baglamda o kisi hangi kampus ve brans altinda gorunuyorsa bunu acikca soyle.
Soruda bir brans veya zumre geciyorsa, o branstaki ogretmenleri ve kampus bilgisini ozetle.
Baglamda acikca olmayan bilgiyi uydurma.
Cevabi Turkce ver.

Baglam:
{context}

Soru: {question}

Cevap:"""
        )
        return (prompt | self.llm | StrOutputParser()).invoke({"context": context, "question": question})

    def _read_cached_content(self) -> str:
        for path in (Path("./data/okul_bilgileri_web.md"), Path("./data/okul_bilgileri.md")):
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore")
        return ""

    def _looks_like_staff_question(self, question: str) -> bool:
        q = self._normalize_tr(question)
        staff_words = [
            "ogretmen", "egitim kadro", "kadro", "zumre", "mudur", "rehberlik",
            "turk dili", "edebiyat", "matematik", "fizik", "kimya", "biyoloji",
            "ingilizce", "almanca", "cografya", "tarih", "felsefe", "din kulturu",
            "beden egitimi", "makine", "elektrik",
        ]
        return any(word in q for word in staff_words) or bool(self._extract_person_name_query(question))

    def _find_staff_context(self, question: str, content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        norm_lines = [self._normalize_tr(line) for line in lines]
        terms = self._staff_search_terms(question)
        matched_indexes: set[int] = set()

        for term in terms:
            norm_term = self._normalize_tr(term)
            if len(norm_term) < 3:
                continue
            for i, line in enumerate(norm_lines):
                if norm_term in line:
                    matched_indexes.update(range(max(0, i - 8), min(len(lines), i + 12)))

        if not matched_indexes:
            return ""
        selected = [lines[i] for i in sorted(matched_indexes)]
        return "\n".join(selected[:220])

    def _staff_search_terms(self, question: str) -> list[str]:
        terms = []
        name = self._extract_person_name_query(question)
        if name:
            terms.append(name)

        q = self._normalize_tr(question)
        branch_aliases = {
            "turk dili": ["turk dili ve edebiyati", "edebiyat ogretmeni"],
            "edebiyat": ["turk dili ve edebiyati", "edebiyat ogretmeni"],
            "ingilizce": ["ingilizce ogretmeni"],
            "matematik": ["matematik ogretmeni"],
            "fizik": ["fizik ogretmeni"],
            "kimya": ["kimya ogretmeni"],
            "biyoloji": ["biyoloji ogretmeni"],
            "tarih": ["tarih ogretmeni"],
            "cografya": ["cografya ogretmeni"],
            "felsefe": ["felsefe ogretmeni"],
            "din kulturu": ["din kulturu ve ahlak bilgisi ogretmeni"],
            "beden egitimi": ["beden egitimi ogretmeni"],
            "makine": ["makine ogretmeni"],
            "elektrik": ["elektrik-elektronik ogretmeni", "elektrik elektronik ogretmeni"],
            "rehberlik": ["rehberlik"],
            "mudur": ["muduriyet", "mudur"],
        }
        for key, values in branch_aliases.items():
            if key in q:
                terms.extend(values)
        if "ogretmen" in q or "kadro" in q or "zumre" in q:
            terms.extend(["egitim kadromuz", "ogretmeni", "ogretmen"])
        return list(dict.fromkeys(terms))

    def _extract_person_name_query(self, question: str) -> str:
        quoted = re.search(r'"([^"]{5,80})"', question)
        if quoted:
            return quoted.group(1).strip()
        pattern = r"\b[A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc][a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]+(?:\s+[A-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc][a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc]+)+\b"
        words = re.findall(pattern, question)
        ignored = {"Data Koleji", "Bilgi Al", "Turk Dili", "T\u00fcrk Dili"}
        for item in words:
            if item not in ignored:
                return item.strip()
        return ""
    def parse_pdf_command(self, question: str) -> dict | None:
        """Sorunun PDF okuma komutu olup olmadığını kontrol et.
        Dönüş: {"pdf": dosya_adı, "page": sayfa_no} veya None"""
        q = self._normalize_tr(question)
        read_keywords = ["oku", "ac", "sayfa", "page", "pdf"]
        if not any(k in q for k in read_keywords):
            return None

        if not self.lessons_dir.exists():
            return None
        pdfs = list(self.lessons_dir.glob("*.pdf"))

        # En iyi eşleşmeyi bul (en çok kelime eşleşen)
        best_pdf = None
        best_score = 0
        for pdf in pdfs:
            name_norm = self._normalize_tr(pdf.stem)
            parts = [p for p in name_norm.split() if len(p) > 2]
            score = sum(1 for p in parts if p in q)
            if score > best_score:
                best_score = score
                best_pdf = pdf

        if not best_pdf:
            return None

        page = None
        m = re.search(r'(\d+)\s*\.?\s*sayfa|sayfa\s*(\d+)|page\s*(\d+)', q)
        if m:
            page = int(next(g for g in m.groups() if g))
        return {"pdf": str(best_pdf), "page": page}

    def ask(self, question: str) -> str:
        """Soruya cevap ver"""
        if not self.chain:
            raise ValueError("RAG engine henüz yüklenmedi. Önce load_documents() veya load_existing_db() çağırın.")
        
        return self.chain.invoke(question)

