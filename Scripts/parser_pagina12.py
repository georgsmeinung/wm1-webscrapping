# parser_pagina12.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import json
import unicodedata
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

import datetime as _dt
import pandas as _pd

# =========================
# Utilidades
# =========================
def normalize_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s if s else None

def strip_accents_lower(s: str) -> str:
    """Minúsculas y sin acentos, colapsa espacios."""
    s_norm = ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'\s+', ' ', s_norm).strip()

def same_after_norm(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    return strip_accents_lower(a) == strip_accents_lower(b)

# =========================
# Configuración
# =========================
SECTION_MAP = {
    'economia': 'Economía',
    'el-pais': 'El País',
    'el pais': 'El País',
    'el-mundo': 'El Mundo',
    'el mundo': 'El Mundo',
    'sociedad': 'Sociedad',
    'politica': 'Política',
    'deportes': 'Deportes',
    'cultura': 'Cultura',
    'espectaculos': 'Espectáculos',
    'opinion': 'Opinión',
    'tecnologia': 'Tecnología',
    'portada': 'Portada',
}

DEFAULT_TAG_STOPLIST = {
    'pagina 12', 'pagina12', 'pagina/12', 'últimas noticias', 'ultimas noticias',
    'noticias', 'hoy', 'portada', 'inicio', 'edicion impresa', 'edición impresa',
    'suscripcion', 'suscripción', 'secciones',
    # Si querés mantener la sección como campo pero NO como tag, las filtramos:
    'argentina', 'política', 'politica', 'economía', 'economia', 'deportes',
    'cultura', 'sociedad', 'mundo', 'opinión', 'opinion'
}

def normalize_section_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    key = strip_accents_lower(s).replace('/', ' ').replace('|', ' ')
    key = re.sub(r'\s+', ' ', key).strip()
    if key in SECTION_MAP:
        return SECTION_MAP[key]
    # Title-case como último recurso
    return s.strip().title()

def _build_stoplist(extra: Optional[List[str]] = None) -> set[str]:
    base = {strip_accents_lower(x) for x in DEFAULT_TAG_STOPLIST}
    if extra:
        base |= {strip_accents_lower(x) for x in extra}
    return base

def clean_tags(raw_tags: List[str], stoplist_norm: set[str]) -> List[str]:
    seen = set()
    out = []
    for t in raw_tags:
        t_norm = normalize_text(t)
        if not t_norm:
            continue
        key = strip_accents_lower(t_norm)
        if key in stoplist_norm:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(t_norm)
    return out

# =========================
# Selectores
# =========================
def select_section(soup: BeautifulSoup, source_path: Optional[Path] = None) -> Optional[str]:
    # 1) Meta directa
    meta = soup.find('meta', attrs={'property': 'article:section'})
    if meta and meta.get('content'):
        sec = normalize_text(meta['content'])
        if sec:
            return normalize_section_name(sec)

    meta2 = soup.find('meta', attrs={'name': 'section'})
    if meta2 and meta2.get('content'):
        sec = normalize_text(meta2['content'])
        if sec:
            return normalize_section_name(sec)

    # 2) JSON-LD (NewsArticle / articleSection o BreadcrumbList)
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            raw = script.string or ''
            if not raw.strip():
                continue
            data = json.loads(raw)
        except Exception:
            continue

        def try_article_section(obj) -> Optional[str]:
            if not isinstance(obj, dict):
                return None
            sec = obj.get('articleSection')
            if isinstance(sec, str) and normalize_text(sec):
                return normalize_section_name(normalize_text(sec))
            if obj.get('@type') == 'BreadcrumbList':
                itm = obj.get('itemListElement') or []
                if isinstance(itm, list) and itm:
                    last = itm[-1]
                    if isinstance(last, dict):
                        name = last.get('name')
                        if name:
                            return normalize_section_name(normalize_text(name))
            return None

    #    data puede ser lista o dict
        if isinstance(data, list):
            for item in data:
                sec = try_article_section(item)
                if sec:
                    return sec
        elif isinstance(data, dict):
            sec = try_article_section(data)
            if sec:
                return sec

    # 3) Breadcrumbs en el DOM
    for sel in ('nav.breadcrumb a', 'ul.breadcrumb a', 'div.breadcrumb a', 'div.breadcrumbs a'):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return normalize_section_name(normalize_text(el.get_text()))

    # 4) Enlaces de sección en header
    for sel in ('a.section', 'a.o-section', 'span.section', 'div.section a'):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return normalize_section_name(normalize_text(el.get_text()))

    # 5) URL canónica / og:url → inferir slug del primer segmento
    def infer_from_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        m = re.search(r'pagina12\.com\.ar/([^/]+)/', url)
        if m:
            return normalize_section_name(m.group(1))
        return None

    link_canon = soup.find('link', attrs={'rel': 'canonical'})
    if link_canon and link_canon.get('href'):
        sec = infer_from_url(link_canon['href'])
        if sec:
            return sec

    og_url = soup.find('meta', attrs={'property': 'og:url'})
    if og_url and og_url.get('content'):
        sec = infer_from_url(og_url['content'])
        if sec:
            return sec

    # 6) Fallback: inferir desde el path local (.../data/raw/economia/nota.html)
    if source_path:
        for part in (p.name.lower() for p in source_path.parents):
            if part in SECTION_MAP:
                return SECTION_MAP[part]

    # 7) Último recurso
    return 'Portada'

def select_kicker(soup: BeautifulSoup) -> Optional[str]:
    candidates = [
        '.article-header h2.h4',              # típico Página/12
        '.article-header .ff-16px-w700',
        'h2.volanta', 'p.volanta', 'div.volanta',
        'h2.kicker', 'p.kicker', 'div.kicker',
        '.article-header .volanta', '.content-header .volanta',
        '.subhead.kicker', '.subtitle.kicker',
    ]
    for sel in candidates:
        el = soup.select_one(sel)
        if el and (txt := el.get_text(strip=True)):
            return normalize_text(txt)

    # Fallback: inferir de <title> u og:title con patrón "H1 | Kicker"
    doc_title = None
    if soup.title and soup.title.string:
        doc_title = normalize_text(soup.title.string)
    if not doc_title:
        meta = soup.find('meta', attrs={'property': 'og:title'})
        if meta and meta.get('content'):
            doc_title = normalize_text(meta['content'])
    if doc_title and ' | ' in doc_title:
        parts = [p.strip() for p in doc_title.split(' | ') if p.strip()]
        if len(parts) >= 2:
            return parts[-1]
    return None

def select_title(soup: BeautifulSoup) -> Optional[str]:
    for sel in ["h1", "h1.title", "h1.article-title", ".article-title h1", "header h1", "h1.hed"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return normalize_text(el.get_text())
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return normalize_text(meta["content"])
    return None

def select_tags(soup: BeautifulSoup) -> List[str]:
    out = []
    for cont in soup.select('ul.tags, .tags, .article-tags, .article__tags'):
        for a in cont.select('a'):
            txt = normalize_text(a.get_text())
            if txt:
                out.append(txt)
    for a in soup.find_all('a', attrs={'rel': 'tag'}):
        txt = normalize_text(a.get_text())
        if txt:
            out.append(txt)
    meta_kw = soup.find('meta', attrs={'name': 'keywords'})
    if meta_kw and meta_kw.get('content'):
        kws = [k.strip() for k in meta_kw['content'].split(',') if k.strip()]
        out.extend(kws)
    return out

def select_article_text(soup: BeautifulSoup) -> Optional[str]:
    candidates = [
        '.article-body', '.article-main-content__body', '.article-content',
        '.article-text', '.article__content', '.content-body', '.nota-body',
        'div[itemprop="articleBody"]',
    ]
    paragraphs = []
    for sel in candidates:
        container = soup.select_one(sel)
        if container:
            for p in container.select('p'):
                txt = normalize_text(p.get_text(" ", strip=True))
                if txt:
                    paragraphs.append(txt)
            if paragraphs:
                break
    if not paragraphs:
        article = soup.find('article')
        if article:
            for p in article.find_all('p'):
                txt = normalize_text(p.get_text(" ", strip=True))
                if txt:
                    paragraphs.append(txt)
    if not paragraphs:
        for p in soup.find_all('p')[:80]:
            txt = normalize_text(p.get_text(" ", strip=True))
            if txt:
                paragraphs.append(txt)
    if not paragraphs:
        return None
    text = "\n\n".join(paragraphs)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() if text.strip() else None

SPANISH_MONTHS = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12
}

def _to_iso(dt: _pd.Timestamp | None, tz_default: str = "America/Argentina/Buenos_Aires") -> Optional[str]:
    if dt is None or _pd.isna(dt):
        return None
    if dt.tzinfo is None:
        try:
            dt = dt.tz_localize(tz_default)  # asume hora Argentina si no viene tz
        except Exception:
            # si falla tz_localize con nombre, probar UTC sin tz
            return dt.isoformat()
    return dt.isoformat()

def _parse_spanish_date(text: str) -> Optional[_pd.Timestamp]:
    """
    Soporta formatos como:
    - '14 de noviembre de 2024'
    - '14 de noviembre de 2024, 09:30'
    - '14 noviembre 2024 09:30'
    """
    if not text:
        return None
    t = strip_accents_lower(text)
    # día de mes de año[, hh:mm]
    m = re.search(r'(\d{1,2})\s+de\s+([a-záéíóúü]+)\s+de\s+(\d{4})(?:[,\s]+(\d{1,2}):(\d{2}))?', t)
    if not m:
        # variante sin "de"
        m = re.search(r'(\d{1,2})\s+([a-záéíóúü]+)\s+(\d{4})(?:[,\s]+(\d{1,2}):(\d{2}))?', t)
    if m:
        d = int(m.group(1))
        month_name = m.group(2)
        y = int(m.group(3))
        hh = int(m.group(4)) if m.group(4) else 0
        mm = int(m.group(5)) if m.group(5) else 0
        mon = SPANISH_MONTHS.get(month_name, None)
        if mon:
            try:
                return _pd.Timestamp(_dt.datetime(y, mon, d, hh, mm))
            except Exception:
                return None
    # fallback: que intente pandas con dayfirst=True
    try:
        return _pd.to_datetime(text, dayfirst=True, errors="coerce")
    except Exception:
        return None

def select_pub_date(soup: BeautifulSoup, tz_default: str = "America/Argentina/Buenos_Aires") -> Optional[str]:
    # 0) <time datetime="..."> mostrado en la nota (lo más confiable)
    t = soup.select_one('time[datetime]')
    if t and t.get('datetime'):
        dt = _pd.to_datetime(t['datetime'], errors="coerce", utc=False)
        iso = _to_iso(dt, tz_default)
        if iso:
            return iso

    # 1) Meta de cXense (UTC ISO)
    cx = soup.find('meta', attrs={'name': 'cXenseParse:recs:publishtime'})
    if cx and cx.get('content'):
        dt = _pd.to_datetime(cx['content'], errors="coerce", utc=True)
        iso = _to_iso(dt, tz_default)
        if iso:
            return iso

    # 2) article:published_time (puede venir como epoch)
    art = soup.find('meta', attrs={'property': 'article:published_time'}) or \
          soup.find('meta', attrs={'name': 'article:published_time'})
    if art and art.get('content'):
        s = art['content'].strip()
        dt = None
        if re.fullmatch(r'\d{10,13}', s):  # epoch
            unit = 's' if len(s) == 10 else 'ms'
            dt = _pd.to_datetime(int(s), unit=unit, utc=True)
        else:
            dt = _pd.to_datetime(s, errors="coerce", utc=False)
        iso = _to_iso(dt, tz_default)
        if iso:
            return iso

    # 3) JSON-LD SOLO si es NewsArticle (último recurso)
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        raw = (script.string or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict):
                continue
            types = obj.get('@type', [])
            if isinstance(types, str):
                types = [types]
            types = [str(t).lower() for t in types]
            if 'newsarticle' not in types:
                continue
            val = obj.get('datePublished') or obj.get('dateCreated') or obj.get('uploadDate')
            if val:
                dt = _pd.to_datetime(val, errors="coerce", utc=False)
                iso = _to_iso(dt, tz_default)
                if iso:
                    return iso

    # 4) Texto en español dentro de nodos de fecha (fallback)
    for sel in ('.date', '.article-date', '.published', '.time'):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            dt = _parse_spanish_date(el.get_text(strip=True))
            if dt is not None and not _pd.isna(dt):
                return _to_iso(dt, tz_default)

    return None


# =========================
# Parser por archivo
# =========================
def parse_html_file(path: Path, stoplist_norm: set[str]) -> Dict[str, Any]:
    html = path.read_text(encoding='utf-8', errors='ignore')
    soup = BeautifulSoup(html, 'lxml')

    section = select_section(soup, source_path=path)
    kicker = select_kicker(soup)
    title = select_title(soup)
    text = select_article_text(soup)
    raw_tags = select_tags(soup)
    pub_date = select_pub_date(soup)

    tags_clean = clean_tags(raw_tags, stoplist_norm)

    # Evitar duplicaciones semánticas
    if same_after_norm(kicker, section):
        kicker = None
    if same_after_norm(kicker, title):
        kicker = None

    return {
        'file': str(path),
        'section': section,
        'tags': tags_clean,
        'tags_str': " | ".join(tags_clean),
        'kicker': kicker,
        'titulo': title,
        'text': text,
        'fecha_publicacion': pub_date, 
    }

# =========================
# Recorrer carpeta y armar DF
# =========================
def build_dataframe(
    html_dir: str | Path,
    patterns: Tuple[str, ...] = ('*.html', '*.htm'),
    extra_tag_stoplist: Optional[List[str]] = None,
) -> pd.DataFrame:
    html_dir = Path(html_dir)
    if not html_dir.exists():
        raise FileNotFoundError(f"No existe la carpeta: {html_dir}")

    stoplist_norm = _build_stoplist(extra_tag_stoplist)

    files: List[Path] = []
    for pat in patterns:
        files.extend(sorted(html_dir.rglob(pat)))

    rows = []
    for f in tqdm(files, desc="Procesando HTMLs", unit="file"):
        try:
            row = parse_html_file(f, stoplist_norm=stoplist_norm)
            rows.append(row)
        except Exception as e:
            rows.append({
                'file': str(f),
                'section': None, 'tags': [], 'tags_str': None,
                'kicker': None, 'titulo': None, 'text': None,
                'error': str(e),
            })

    df = pd.DataFrame(rows)

    # Normalizaciones finales
    for col in ['section', 'kicker', 'titulo', 'text']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: normalize_text(x) if isinstance(x, str) else x)

    # Quitar filas totalmente vacías (sin título y sin texto)
    df = df[~(df['titulo'].isna() & df['text'].isna())].reset_index(drop=True)
    return df

# =========================
# CLI
# =========================
if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description='Parsear HTMLs de Página/12 a DataFrame.')
    ap.add_argument('html_dir', help='Carpeta raíz con los HTMLs descargados.')
    ap.add_argument('--csv', default='pagina12_parsed.csv', help='Ruta de salida CSV.')
    ap.add_argument('--parquet', default=None, help='Ruta de salida Parquet (opcional).')
    ap.add_argument('--extra_stop', default=None,
                    help='Ruta a JSON con lista de palabras prohibidas extra para tags.')
    args = ap.parse_args()

    extra_stop = None
    if args.extra_stop:
        extra_stop = json.loads(Path(args.extra_stop).read_text(encoding='utf-8'))

    df = build_dataframe(args.html_dir, extra_tag_stoplist=extra_stop)
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.csv, index=False, encoding='utf-8')
    if args.parquet:
        Path(args.parquet).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(args.parquet, index=False)
    print(f"Listo. Filas: {len(df)} | CSV: {args.csv}" + (f" | Parquet: {args.parquet}" if args.parquet else ""))
