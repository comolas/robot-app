# Firebase Hosting

Bu proje Firebase Hosting uzerinden statik arayuzu yayinlayacak sekilde ayarlandi.

## Dosyalar

- `public/index.html`: Firebase Hosting tarafindan yayinlanacak arayuz.
- `firebase.json`: Hosting public klasoru ve rewrite ayarlari.
- `.firebaserc`: Varsayilan Firebase projesi: `temizle-49c5c`.

## Backend adresi

Arayuz API istekleri icin `public/index.html` icindeki `window.APP_CONFIG.apiBaseUrl` degerini kullanir.

Yerelde otomatik olarak:

```js
http://localhost:8000
```

Hosting'de ise su placeholder kullanilir:

```js
https://YOUR_BACKEND_URL
```

Python/FastAPI backend Firebase Hosting icinde calismaz. Backend'i Cloud Run, Firebase Functions veya baska bir sunucuya deploy ettikten sonra `https://YOUR_BACKEND_URL` degerini gercek backend URL'siyle degistirin.

## Deploy

Firebase CLI kurulu degilse:

```bash
npm install -g firebase-tools
```

Giris yapin:

```bash
firebase login
```

Deploy edin:

```bash
firebase deploy --only hosting
```
