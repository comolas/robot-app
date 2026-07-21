# Cloud Run Deploy

Bu backend FastAPI uygulamasi Cloud Run uzerinde container olarak calisacak sekilde hazirlandi.

## Eklenenler

- `Dockerfile`: Python/FastAPI backend container tanimi.
- `.dockerignore`: Gizli ve gereksiz dosyalari image disinda birakir.
- `app.py`: Cloud Run'in verdigi `PORT` ortam degiskenini destekler.

## Google Cloud Console ile deploy

Cloud Run ekraninda su seceneklerden birini kullanabilirsiniz:

1. GitHub repo baglayacaksaniz: `Continuously deploy from a repository`.
2. Hazir image kullanacaksaniz: `Deploy one revision from an existing container image`.

Bu proje icin GitHub'a yukledikten sonra repository secmek en pratik yoldur. Cloud Build, repo icindeki `Dockerfile` dosyasini kullanarak image olusturabilir.

Onerilen ayarlar:

- Service name: `robot-api`
- Region: `europe-west1` veya size yakin bir Avrupa bolgesi
- Authentication: `Allow unauthenticated invocations`
- Container port: `8080`

## Komut satirindan deploy

Google Cloud CLI kuruluysa veya Cloud Shell kullaniyorsaniz:

```bash
gcloud config set project temizle-49c5c
gcloud run deploy robot-api --source . --region europe-west1 --allow-unauthenticated
```

Deploy bittiginde Cloud Run bir URL verir. Ornek:

```text
https://robot-api-xxxxx-ew.a.run.app
```

Bu URL'yi `public/index.html` icindeki `https://YOUR_BACKEND_URL` yerine yazin ve Firebase Hosting'i yeniden deploy edin.

## Ortam degiskenleri

Cloud Run servis ayarlarinda en az sunu ekleyin:

```text
GOOGLE_API_KEY=...
```

Varsa:

```text
SCHOOL_WEBSITE_URL=...
```

Google Cloud TTS ve Speech icin en iyi yontem Cloud Run servis hesabina gerekli IAM izinlerini vermektir. Yerel `credentials.json` dosyasini container'a koymayin.
