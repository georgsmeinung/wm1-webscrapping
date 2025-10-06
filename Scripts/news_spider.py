# -*- coding: utf-8 -*-
import re
from pathlib import Path
from urllib import parse as urlparse

import scrapy
from scrapy import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.http import HtmlResponse


class Pagina12Spider(CrawlSpider):
    name = "pagina12"
    allowed_domains = ("www.pagina12.com.ar", "pagina12.com.ar")

    # Índices base de las 4 secciones del TP
    start_urls = [
        "https://www.pagina12.com.ar/secciones/economia",
        "https://www.pagina12.com.ar/secciones/el-pais",
        "https://www.pagina12.com.ar/secciones/el-mundo",
        "https://www.pagina12.com.ar/secciones/sociedad",
    ]

    # Ajustes: ritmo conservador, AutoThrottle, retries y SIN límite de profundidad
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 2.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408, 403],
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "DEPTH_LIMIT": 0,  # <--- importante para que no corte la paginación
        "LOG_LEVEL": "INFO",
        "USER_AGENT": "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "FEED_EXPORT_ENCODING": "utf-8",
        "DEPTH_PRIORITY": 1,  # prioriza niveles superficiales → BFS
        "SCHEDULER_DISK_QUEUE": "scrapy.squeues.PickleFifoDiskQueue",
        "SCHEDULER_MEMORY_QUEUE": "scrapy.squeues.FifoMemoryQueue",
    }

    def __init__(self, base_dir=None, max_pages=None, *args, **kwargs):
        """
        base_dir: carpeta base para guardar HTMLs (por defecto <repo>/data/raw)
        max_pages: entero opcional; si se pasa, sembramos /secciones/... ?page=0..max_pages
        """
        super().__init__(*args, **kwargs)
        default_base = Path.cwd().parents[2] / "data" / "raw"
        self.base_dir = Path(base_dir) if base_dir else default_base
        self.max_pages = int(max_pages) if max_pages is not None else None
        for s in ("economia", "elpais", "elmundo", "sociedad", "otros"):
            (self.base_dir / s).mkdir(parents=True, exist_ok=True)

    # -------- Si se pasa max_pages, "sembramos" /secciones/... ?page=0..N ----------
    def start_requests(self):
        # siempre pedimos las 4 secciones base (page=0)
        for url in self.start_urls:
            yield Request(url, dont_filter=True)
        # si max_pages está definido, agregamos /?page=1..N para cada sección
        if self.max_pages:
            seeds = [
                "https://www.pagina12.com.ar/secciones/economia",
                "https://www.pagina12.com.ar/secciones/el-pais",
                "https://www.pagina12.com.ar/secciones/el-mundo",
                "https://www.pagina12.com.ar/secciones/sociedad",
            ]
            for base in seeds:
                for i in range(1, self.max_pages + 1):
                    yield Request(f"{base}?page={i}", dont_filter=True)

    # ---------------------- Utilidades de sección ----------------------
    @staticmethod
    def _normalize_section(sec: str) -> str:
        if not sec:
            return "otros"
        sec = sec.strip().lower()
        mapping = {
            "economia": "economia",
            "el-pais": "elpais",
            "el mundo": "elmundo",
            "el-mundo": "elmundo",
            "sociedad": "sociedad",
        }
        return mapping.get(sec, "otros")

    @staticmethod
    def _section_from_referer(referer_url: str) -> str | None:
        if not referer_url:
            return None
        m = re.search(r"/secciones/(economia|el-pais|el-mundo|sociedad)", referer_url, flags=re.IGNORECASE)
        return m.group(1).lower() if m else None

    @staticmethod
    def _section_from_breadcrumb(response: HtmlResponse) -> str | None:
        for href in response.css('a[href^="/secciones/"]::attr(href)').getall():
            m = re.search(r"/secciones/(economia|el-pais|el-mundo|sociedad)", href, flags=re.IGNORECASE)
            if m:
                return m.group(1).lower()
        return None

    # -------------------------- Reglas --------------------------
    rules = (
        # Seguir índices de las 4 secciones (y su paginación ?page=N)
        Rule(
            LinkExtractor(
                allow=(r"/secciones/(economia|el-pais|el-mundo|sociedad)(\?page=\d+)?$"),
                deny_domains=["auth.pagina12.com.ar", "socios.pagina12.com.ar"],
                canonicalize=True,
            ),
            follow=True,
        ),
        # Capturar solo artículos reales en la raíz: /<id>-<slug>
        Rule(
            LinkExtractor(
                allow=(r"^https?://(?:www\.)?pagina12\.com\.ar/\d{3,}-[^/?#]+$"),
                deny=(r"/(autores|autor|tags|tag|temas|ediciones|edicion-impresa|"
                      r"suplementos|contratapa|dialogo|videos|audios|podcasts)/"),
                deny_domains=["auth.pagina12.com.ar", "socios.pagina12.com.ar"],
                canonicalize=True,
            ),
            callback="parse_article",
            follow=False,
        ),
    )

    # ------------------------ Callback artículo ------------------------
    def parse_article(self, response: HtmlResponse):
        url = response.url

        # Guard 1: og:type debe ser 'article' si existe
        og_type = response.css('meta[property="og:type"]::attr(content)').get()
        if og_type and og_type.strip().lower() != "article":
            self.logger.info(f"Skip no-article (og:type={og_type}): {url}")
            return

        # Guard 2: URL debe cumplir patrón de artículo en raíz
        if not re.search(r"^https?://(?:www\.)?pagina12\.com\.ar/\d{3,}-[^/?#]+$", url):
            self.logger.info(f"Skip no-article by URL: {url}")
            return

        # Sección preferida desde el Referer del índice; fallback a breadcrumb del HTML
        referer = response.request.headers.get("Referer", b"").decode("utf-8", errors="ignore")
        section = self._section_from_referer(referer) or self._section_from_breadcrumb(response)
        sec_norm = self._normalize_section(section)

        # Nombre de archivo: cola de la URL (id-slug.html)
        tail = url[url.rfind("/") + 1 :]
        if not tail.endswith(".html"):
            tail += ".html"

        destino_dir = self.base_dir / sec_norm
        destino_dir.mkdir(parents=True, exist_ok=True)
        filepath = destino_dir / urlparse.quote(tail, safe=".-_")

        self.logger.info(f"URL: {url} → {filepath}")
        with open(filepath, "wb") as f:
            f.write(response.body)

        # Si quisieras cortar por ITEMCOUNT, podés emitir un item mínimo:
        # yield {"url": url, "section": sec_norm, "path": str(filepath)}
        return
