# Raspberry Pi 5 Kamera Entegrasyonu

Bu ilk surumde Raspberry Pi 5 kamera ile kisi algilaninca backend'e oturum baslatma istegi gonderilir.

## Kurulum

Raspberry Pi uzerinde:

```bash
pip install opencv-python requests
```

## Calistirma

```bash
python raspberry_pi_presence.py
```

Script kamera goruntusunde kisi algiladiginda su endpoint'i cagirir:

```text
POST /session/start
```

Backend su cevabi uretir:

```text
Merhaba, ben Data Koleji tanitim robotuyum. Size nasil hitap edebilirim?
```

Sonraki soru isteklerinde ayni `session_id` kullanilirsa backend kullanicinin ismini konusma boyunca hatirlar.

## Soru gonderme ornegi

```json
{
  "session_id": "pi5-ornek-oturum",
  "question": "Benim adim Arif"
}
```

Sonraki soru:

```json
{
  "session_id": "pi5-ornek-oturum",
  "question": "Okul hakkinda bilgi verir misin?"
}
```
