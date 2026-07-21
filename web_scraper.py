import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class WebScraper:
    def __init__(self, base_url: str, max_pages: int = 30):
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.visited = set()
        self._gallery_cache = None
        self._gallery_cache_time = 0
        self._gallery_cache_ttl = 3600  # 1 saat

    def scrape(self) -> str:
        """Web sitesini tarayıp tüm içeriği tek metin olarak döndür"""
        pages = self._crawl(self.base_url)
        all_text = []
        for url, text in pages.items():
            if text.strip():
                all_text.append(f"--- Sayfa: {url} ---\n{text}")
        return "\n\n".join(all_text)

    def scrape_gallery(self, gallery_path: str = "/data-galeri/") -> list[dict]:
        """Galeri sayfasından görselleri çek — 1 saat cache"""
        now = time.time()
        if self._gallery_cache and (now - self._gallery_cache_time) < self._gallery_cache_ttl:
            return self._gallery_cache

        url = self.base_url + gallery_path
        images = []
        try:
            r = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SchoolBot/1.0)"
            })
            soup = BeautifulSoup(r.text, "html.parser")
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if "gallery" in src or "galeri" in src:
                    full_url = urljoin(self.base_url + "/", src)
                    alt = img.get("alt", "").strip()
                    images.append({"url": full_url, "alt": alt})
        except Exception as e:
            print(f"Galeri tarama hatasi: {e}")

        self._gallery_cache = images
        self._gallery_cache_time = now
        return images

    def _crawl(self, start_url: str) -> dict:
        """Sitedeki sayfaları tara ve içeriklerini topla"""
        to_visit = [start_url]
        pages = {}

        while to_visit and len(self.visited) < self.max_pages:
            url = to_visit.pop(0)
            if url in self.visited:
                continue

            try:
                r = requests.get(url, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SchoolBot/1.0)"
                })
                if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                    continue

                self.visited.add(url)
                soup = BeautifulSoup(r.text, "html.parser")

                # Linkleri topla
                for a in soup.find_all("a", href=True):
                    link = urljoin(url, a["href"])
                    link = link.split("#")[0].split("?")[0].rstrip("/")
                    if (urlparse(link).netloc == self.domain
                            and link not in self.visited
                            and not link.endswith((".pdf", ".jpg", ".png", ".gif", ".zip", ".mp4", ".mp3"))):
                        to_visit.append(link)

                # İçeriği çıkar
                for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                # Çok kısa sayfaları atla
                if len(text) > 50:
                    pages[url] = text

                print(f"  [OK] {url} ({len(text)} karakter)")

            except Exception as e:
                print(f"  [HATA] {url}: {e}")

        print(f"Toplam {len(pages)} sayfa tarandı.")
        return pages
