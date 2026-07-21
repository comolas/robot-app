import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Farklı model adlarını dene
models = [
    "embedding-001",
    "models/embedding-001",
    "text-embedding-004",
    "models/text-embedding-004"
]

for model in models:
    try:
        print(f"\nDeneniyor: {model}")
        embeddings = GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=api_key
        )
        result = embeddings.embed_query("test")
        print(f"✓ BAŞARILI: {model} - Embedding boyutu: {len(result)}")
        break
    except Exception as e:
        print(f"✗ HATA: {model} - {str(e)[:100]}")
