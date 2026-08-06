# Raspberry Pi 5 Kamera Entegrasyonu

Bu kurulumda kişi algılama Raspberry Pi 5 üzerinde yapılır. Tablet veya bilgisayar sadece web arayüzünü gösterir. Böylece eski Chrome sürümleri kamera/model uyumsuzluğu yaşasa bile robot karşılama tepkisini güvenilir şekilde verebilir.

## Çalışma Mantığı

1. Raspberry Pi 5 kamera görüntüsünü okur.
2. Önce OpenCV HOG insan algılama çalışır.
3. İnsan algılama yeterince güvenli sonuç vermezse hareket algılama yedek olarak devreye girer.
4. Algılama olunca Pi backend'e şu isteği gönderir:

```text
POST /robot/presence
```

5. Web arayüzü `/robot/presence/latest` endpoint'ini 1.5 saniyede bir kontrol eder.
6. Yeni algılama olayı gelirse çizgi yüz gülümser ve karşılama sesi çalınır.

## Raspberry Pi Kurulumu

```bash
sudo apt update
sudo apt install -y python3-opencv
pip install requests
```

Kamera modülünü test etmek için:

```bash
libcamera-hello
```

OpenCV kamerayı görmüyorsa kamera için V4L2 uyumluluğunu kontrol etmek gerekebilir.

## Çalıştırma

```bash
python raspberry_pi_presence.py
```

Varsayılan API adresi:

```text
https://robot-app-1047763414877.europe-west1.run.app
```

Farklı bir backend kullanmak için:

```bash
ROBOT_API_BASE_URL=https://SENIN-CLOUD-RUN-ADRESIN python raspberry_pi_presence.py
```

## Ayarlar

Ortam değişkenleriyle hassasiyet değiştirilebilir:

```bash
ROBOT_DETECTION_COOLDOWN=30
ROBOT_PERSON_CONFIRM_FRAMES=2
ROBOT_MOTION_CONFIRM_FRAMES=6
ROBOT_MOTION_AREA_THRESHOLD=9000
ROBOT_CAMERA_INDEX=0
ROBOT_SHOW_PREVIEW=1
python raspberry_pi_presence.py
```

Öneriler:

- Çok sık tetikliyorsa `ROBOT_MOTION_AREA_THRESHOLD` değerini yükseltin.
- Geç tetikliyorsa `ROBOT_MOTION_CONFIRM_FRAMES` değerini düşürün.
- Test sırasında görüntüyü görmek için `ROBOT_SHOW_PREVIEW=1` kullanın.
- Üretimde preview kapalı kalsın.

## Kafa Sevme / Dokunma Algılama

Robotun kafasına kapasitif dokunma sensörü eklenirse Raspberry Pi backend'e şu endpoint ile haber verir:

```text
POST /robot/touch/head
```

Kurulum:

```bash
pip install gpiozero requests
python raspberry_pi_head_touch.py
```

Varsayılan pin:

```text
GPIO17
```

Tipik bağlantı:

```text
VCC -> 3.3V
GND -> GND
OUT -> GPIO17
```

Endpoint cevabında `face_state` alanı `complimented` olarak gelir.
