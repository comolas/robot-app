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

## Kafa sevme / dokunma algilama

Robotun kafasina kapasitif dokunma sensoru eklenirse Raspberry Pi backend'e su endpoint ile haber verir:

```text
POST /robot/touch/head
```

Backend su anlamda bir cevap dondurur:

```text
Beni mutlu ettiniz. Tesekkur ederim.
```

Kullanici adi biliniyorsa cevap isme gore kisilesir.

Ornek GPIO script'i:

```bash
pip install gpiozero requests
python raspberry_pi_head_touch.py
```

Varsayilan pin:

```text
GPIO17
```

Kapasitif dokunma sensoru icin tipik baglanti:

```text
VCC -> 3.3V
GND -> GND
OUT -> GPIO17
```

Endpoint cevabinda `face_state` alani `complimented` olarak gelir. Pi uzerindeki ekran bu degeri gorunce iltifat/kizarma yuzunu 5 saniye gosterebilir.
