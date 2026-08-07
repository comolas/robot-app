# Tarayici Kamerasi ile Karsilama

Firebase Hosting arayuzu tarayici kamerasini kullanarak yaklasan kisiyi algilayabilir.

## Calisma mantigi

- Site acilinca karşilama ekrani gorunur.
- Tarayici kamera izni ister.
- Izin bir kez verildikten sonra tarayici bu izni site icin hatirlayabilir.
- Kamera goruntusunde belirgin hareket/yaklasma algilaninca backend'e su istek atilir:

```text
POST /session/start
```

Gonderilen govde:

```json
{
  "session_id": "...",
  "greeting_type": "presence"
}
```

Robotun karşilama cumlesi:

```text
Merhaba, okulumuza hoş geldiniz. Bilgi almak icin Bilgi Al butonuna tıklayabilirsiniz.
```

## Tam ekran

Tarayicilar guvenlik nedeniyle tam ekrani tamamen otomatik zorlamaz. Site tam ekran modunu sayfa acilisinda dener, ayrica `BILGI AL` butonuna tiklandiginda tekrar ister.

Fiziksel kiosk icin en saglam yontem Chrome veya Edge'i kiosk modunda baslatmaktir.

Ornek Chrome:

```bash
chrome --kiosk https://YOUR_FIREBASE_HOSTING_URL
```

Ornek Edge:

```bash
msedge --kiosk https://YOUR_FIREBASE_HOSTING_URL --edge-kiosk-type=fullscreen
```

## Notlar

- Kamera izni olmadan web sitesi kamerayi acamaz.
- Algilama oncelikle TensorFlow.js + COCO-SSD ile `person` sinifina gore yapilir.
- Kamera goruntusu sunucuya gonderilmez; model tarayici icinde calisir.
- COCO-SSD modeli yuklenemezse eski hareket algilama yedek olarak devreye girer.
- `person` algilama guven esigi arayuz kodunda `PERSON_SCORE_THRESHOLD` degeriyle ayarlanir.
