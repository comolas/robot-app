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
Merhaba, okulumuza hos geldiniz. Bilgi almak icin Bilgi Al butonuna tiklayabilirsiniz.
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
- Algilama goruntu kareleri arasindaki hareket farkina gore yapilir; goruntu sunucuya gonderilmez.
- Daha hassas insan algilama gerekirse sonraki adimda TensorFlow.js veya MediaPipe eklenebilir.
