import requests
import json

# API'ye soru sor
url = "http://localhost:8000/ask"
data = {
    "question": "Merhaba, kendin hakkında bilgi verir misin?"
}

response = requests.post(url, json=data)
print("Status Code:", response.status_code)
print("\nYanıt:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if response.status_code == 200:
    result = response.json()
    print("\n" + "="*50)
    print("Soru:", data["question"])
    print("\nCevap:", result.get("answer", "Cevap bulunamadı"))
    print("\nSes dosyası:", result.get("audio_path", "Yok"))
