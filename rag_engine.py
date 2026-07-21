import os
import re
import pickle
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
            model="models/embedding-001",
            google_api_key=api_key,
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest",
            google_api_key=api_key,
            temperature=0.3
        )
        self.vectordb = None
        self.chain = None
        self.db_path = Path("./vectordb")
        self.lessons_dir = Path("./data/lessons")
        
    def load_documents(self, markdown_path: str):
        """Markdown dosyasını yükle ve vektör veritabanına kaydet"""
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self._index_text(content)

    def load_from_url(self, url: str, max_pages: int = 30):
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
2. Giriş cümlesinden sonra \n\n (çift satır atlama) kullan
3. Başlıkları numaralı ve BÜYÜK HARFLE yaz (örnek: 1. AKADEMİK BAŞARILAR)
4. Başlıklardan sonra \n\n kullan
5. Her paragraftan sonra \n\n kullan
6. Madde işareti kullanma, akıcı paragraflar yaz

ÖRNEK FORMAT:
Ben Data Koleji Ovacık Mesleki ve Teknik Anadolu Lisesi'nin resmi tanıtım robotuyum. Okulumuz hakkında talep ettiğiniz bilgileri aşağıda sunmaktan memnuniyet duyarım.

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
        """Türkçe karakterleri ASCII'ye dönüştür"""
        tr_map = str.maketrans('çğıöşüÇĞİIÖŞÜ', 'cgiosuCGIIOSU')
        return text.translate(tr_map).lower()

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
