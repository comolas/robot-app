import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class WebScraper:
    STAFF_PATHS = [
        "/ovacik-kampusu-egitim-kadrosu/",
        "/mamak-kampusu-egitim-kadrosu/",
        "/baglica-kampusu-egitim-kadrosu/",
    ]

    def __init__(self, base_url: str, max_pages: int = 120):
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.visited = set()
        self._gallery_cache = None
        self._gallery_cache_time = 0
        self._gallery_cache_ttl = 3600

    def scrape(self) -> str:
        """Web sitesini tarayıp tüm içeriği tek metin olarak döndür."""
        pages = self._crawl(self.base_url)
        all_text = []
        for url, text in pages.items():
            if text.strip():
                all_text.append(f"--- Sayfa: {url} ---\n{text}")
        return "\n\n".join(all_text)

    def scrape_gallery(self, gallery_path: str = "/data-galeri/") -> list[dict]:
        """Galeri sayfasından görselleri çek. Sonuç 1 saat cache'lenir."""
        now = time.time()
        if self._gallery_cache and (now - self._gallery_cache_time) < self._gallery_cache_ttl:
            return self._gallery_cache

        url = self.base_url + gallery_path
        images = []
        try:
            response = requests.get(url, timeout=10, headers=self._headers())
            soup = BeautifulSoup(response.text, "html.parser")
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if "gallery" in src or "galeri" in src:
                    images.append({
                        "url": urljoin(self.base_url + "/", src),
                        "alt": img.get("alt", "").strip(),
                    })
        except Exception as exc:
            print(f"Galeri tarama hatasi: {exc}")

        self._gallery_cache = images
        self._gallery_cache_time = now
        return images

    def _crawl(self, start_url: str) -> dict:
        """Sitedeki sayfaları tara ve içeriklerini topla."""
        staff_links = [urljoin(self.base_url + "/", path).rstrip("/") for path in self.STAFF_PATHS]
        sitemap_links = self._load_sitemap_links()
        priority_sitemap_links = [link for link in sitemap_links if self._is_priority_link(link)]
        other_sitemap_links = [link for link in sitemap_links if not self._is_priority_link(link)]
        to_visit = [start_url] + staff_links + priority_sitemap_links + other_sitemap_links
        to_visit = list(dict.fromkeys(to_visit))
        queued = set(to_visit)
        pages = {}

        while to_visit and len(self.visited) < self.max_pages:
            url = to_visit.pop(0)
            if url in self.visited:
                continue

            try:
                response = requests.get(url, timeout=10, headers=self._headers())
                content_type = response.headers.get("content-type", "")
                if response.status_code != 200 or "text/html" not in content_type:
                    continue

                self.visited.add(url)
                soup = BeautifulSoup(response.text, "html.parser")

                priority_links = []
                normal_links = []
                for a in soup.find_all("a", href=True):
                    link = urljoin(url, a["href"]).split("#")[0].split("?")[0].rstrip("/")
                    if not self._should_visit(link, queued):
                        continue
                    queued.add(link)
                    if self._is_priority_link(link):
                        priority_links.append(link)
                    else:
                        normal_links.append(link)
                to_visit = priority_links + to_visit + normal_links

                for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
                    tag.decompose()

                table_text = self._extract_tables(soup)
                text = soup.get_text(separator="\n", strip=True)
                if table_text:
                    text = f"{text}\n\nTablo içerikleri:\n{table_text}"

                if len(text) > 50:
                    pages[url] = text

                print(f"  [OK] {url} ({len(text)} karakter)")
            except Exception as exc:
                print(f"  [HATA] {url}: {exc}")

        print(f"Toplam {len(pages)} sayfa tarandı.")
        return pages

    def _should_visit(self, link: str, queued: set[str]) -> bool:
        parsed = urlparse(link)
        if parsed.netloc != self.domain:
            return False
        if link in self.visited or link in queued:
            return False
        return not link.lower().endswith((
            ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".mp4", ".mp3"
        ))

    def _load_sitemap_links(self) -> list[str]:
        links = []
        for path in ("/sitemap.xml", "/sitemap_index.xml"):
            try:
                response = requests.get(self.base_url + path, timeout=10, headers=self._headers())
                if response.status_code != 200:
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                for loc in soup.find_all("loc"):
                    link = loc.get_text(strip=True).split("#")[0].split("?")[0].rstrip("/")
                    if self._should_visit(link, set(links)):
                        links.append(link)
            except Exception as exc:
                print(f"Sitemap okunamadi ({path}): {exc}")
        return links

    @staticmethod
    def _is_priority_link(link: str) -> bool:
        value = link.lower()
        keywords = [
            "egitim-kadromuz",
            "ogretmen",
            "öğretmen",
            "kadromuz",
            "zumre",
            "zümre",
            "mudur",
            "rehberlik",
        ]
        return any(keyword in value for keyword in keywords)

    @staticmethod
    def _extract_tables(soup: BeautifulSoup) -> str:
        rows = []
        for table_index, table in enumerate(soup.find_all("table"), start=1):
            rows.append(f"Tablo {table_index}:")
            for tr in table.find_all("tr"):
                cells = [
                    cell.get_text(" ", strip=True)
                    for cell in tr.find_all(["th", "td"])
                    if cell.get_text(" ", strip=True)
                ]
                if cells:
                    rows.append(" | ".join(cells))
        return "\n".join(rows)

    @staticmethod
    def _headers() -> dict:
        return {"User-Agent": "Mozilla/5.0 (compatible; SchoolBot/1.0)"}
