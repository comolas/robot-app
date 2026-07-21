# Okul Tanıtım Robot - RAG Sistemi

FastAPI + LangChain + Gemini + ChromaDB + Google Cloud TTS

## Kurulum

### 1. Gerekli Paketleri Yükle
```bash
pip install -r requirements.txt
```

### 2. API Anahtarlarını Ayarla

`.env` dosyası oluştur:
```
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/google-cloud-credentials.json
```

**Gemini API Key**: https://makersuite.google.com/app/apikey
**Google Cloud TTS**: https://console.cloud.google.com/

### 3. Okul Bilgilerini Ekle

`data/okul_bilgileri.md` dosyasını düzenle ve okul bilgilerini ekle.

### 4. Uygulamayı Başlat

```bash
python app.py
```

API: http://localhost:8000
Dokümantasyon: http://localhost:8000/docs

## API Kullanımı

### Soru Sor
```bash
POST /ask
{
  "question": "Okulun kuruluş tarihi nedir?"
}
```

Yanıt:
```json
{
  "answer": "...",
  "audio_path": "audio_output/xxxxx.mp3"
}
```

### Ses Dosyasını İndir
```
GET /audio/{filename}
```

### Verileri Yeniden Yükle
```
POST /reload-data
```

## Arduino Entegrasyonu

Arduino'dan HTTP POST isteği örneği:

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

void askQuestion(String question) {
  HTTPClient http;
  http.begin("http://YOUR_SERVER_IP:8000/ask");
  http.addHeader("Content-Type", "application/json");
  
  String payload = "{\"question\":\"" + question + "\"}";
  int httpCode = http.POST(payload);
  
  if (httpCode == 200) {
    String response = http.getString();
    // Parse JSON ve ses dosyasını çal
  }
  
  http.end();
}
```

## Proje Yapısı

```
Robot/
├── app.py                 # FastAPI ana dosya
├── rag_engine.py          # RAG motoru
├── tts_service.py         # Google TTS
├── requirements.txt       # Python paketleri
├── .env                   # API anahtarları
├── data/
│   └── okul_bilgileri.md  # Okul bilgileri
├── vectordb/              # ChromaDB (otomatik oluşur)
└── audio_output/          # Ses dosyaları (otomatik oluşur)
```

## Notlar

- İlk çalıştırmada vektör veritabanı oluşturulur (birkaç saniye sürer)
- Ses dosyaları `audio_output/` klasöründe saklanır
- Markdown dosyasını güncellerseniz `/reload-data` endpoint'ini çağırın
