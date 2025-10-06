# -*- coding: utf-8 -*-
"""
Transforma páginas HTML (1 carpeta por categoría) en un dataset vectorizado.
Mantiene tu flujo y nombres, con fallbacks robustos y filtros de archivos.
"""
from sklearn.feature_extraction.text import CountVectorizer
from bs4 import BeautifulSoup, Comment
import re
import os
import joblib
from typing import Pattern, Optional, List, Tuple

# --- IMPORT DEL TOKENIZADOR: usa tu módulo local; si no existe, fallback simple
try:
    from pagina12_crawler.processing.tokenizers import tokenizador, tokenizador_con_stemming  # noqa
    mi_tokenizer = tokenizador
except Exception:
    def mi_tokenizer(texto: str) -> List[str]:
        return re.findall(r"\b\w+\b", texto.lower(), flags=re.UNICODE)

STOPWORDS_FILE = "stopwords_es.txt"
STOPWORDS_FILE_SIN_ACENTOS = "stopwords_es_sin_acentos.txt"
DIR_BASE_CATEGORIAS = r"C:\Users\juanm\tp_web_mining1\data\raw"

# Marcadores (flexibles). Si no están, habrá fallback con BS4.
MARCADOR_COMIENZO_INTERESANTE = r'<div[^>]*\bclass="[^"]*\barticle-main-content\b[^"]*\barticle-text\b[^"]*"[^>]*>'
MARCADOR_FIN_INTERESANTE = r'<!--\s*Live\s+Blog\s+Post\s*-->'
extractor_de_parte_de_html_que_interesa: Pattern = re.compile(
    MARCADOR_COMIENZO_INTERESANTE + r"(?P<body>.+?)" + MARCADOR_FIN_INTERESANTE,
    flags=re.DOTALL | re.IGNORECASE
)

BANNERS_REGEX = re.compile(
    r"(banner|ads?|advert|sponsor|share|related|subscribe|breadcrumb|author|comments?|footer|header|nav|slot|ad-slot|talkFireEvent)",
    re.IGNORECASE
)

MIN_DF = 3
MAX_DF = 0.8
MIN_NGRAMS = 1
MAX_NGRAMS = 2

VECTORS_FILE = "vectores.joblib"
TARGETS_FILE = "targets.joblib"
FEATURE_NAMES_FILE = "features.joblib"


# ---------- utilidades seguras ----------
def _es_html(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in {".html", ".htm"}

def leer_archivo(path: str) -> str:
    # Tolerante a encoding
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="ignore")

def leer_stopwords(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as stopwords_file:
        return [sw.strip().lower() for sw in stopwords_file if sw.strip()]

def extraer_parte_que_interesa_de_html(regex: Pattern, texto: str) -> Optional[str]:
    m = regex.search(texto)
    return m.group("body") if m else None

def _to_str_or_empty(x) -> str:
    # Convierte None/list/str a str seguro
    if x is None:
        return ""
    if isinstance(x, (list, tuple)):
        try:
            return " ".join([e for e in x if isinstance(e, str)])
        except Exception:
            return ""
    if isinstance(x, str):
        return x
    return str(x)

def _limpiar_ruido(nodo):
    # elimina scripts/styles/noscript/comentarios y contenedores típicos de ruido por class/id
    for tag in nodo.find_all(["script", "style", "noscript"]):
        tag.decompose()
    for c in nodo.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for tag in nodo.find_all(True):
        klass = _to_str_or_empty(tag.get("class"))
        id_ = _to_str_or_empty(tag.get("id"))
        if BANNERS_REGEX.search(klass) or BANNERS_REGEX.search(id_):
            tag.decompose()

def _texto_de_parrafos(nodo) -> str:
    ps = [p.get_text(" ", strip=True) for p in nodo.find_all("p")]
    ps = [t for t in ps if t and len(t.split()) >= 3]
    return "\n".join(ps).strip()

def _fallback_article_main_content(html_doc: str) -> Optional[str]:
    soup = BeautifulSoup(html_doc, "html.parser")
    cont = soup.select_one("div.article-main-content.article-text")
    if not cont:
        cont = soup.select_one('div[class*="article-main-content"][class*="article-text"]')
    if not cont:
        return None
    _limpiar_ruido(cont)
    txt = _texto_de_parrafos(cont)
    return txt if txt else None

def _fallback_generico(html_doc: str) -> Optional[str]:
    soup = BeautifulSoup(html_doc, "html.parser")
    _limpiar_ruido(soup)
    candidatos = soup.find_all(["article", "section", "main", "div"])
    mejor, L = "", 0
    for nodo in candidatos:
        klass = _to_str_or_empty(nodo.get("class"))
        id_ = _to_str_or_empty(nodo.get("id"))
        if BANNERS_REGEX.search(klass) or BANNERS_REGEX.search(id_):
            continue
        t = _texto_de_parrafos(nodo)
        if len(t) > L:
            mejor, L = t, len(t)
    return mejor if L >= 300 else None


# ---------- pipeline de extracción ----------
def pasar_html_a_texto(html_doc: str) -> Optional[str]:
    # 1) Intento por REGEX (si existen los marcadores)
    body_html = extraer_parte_que_interesa_de_html(extractor_de_parte_de_html_que_interesa, html_doc)
    if body_html:
        texto = BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True)
        if texto.strip():
            return texto

    # 2) Fallback específico: .article-main-content.article-text
    texto2 = _fallback_article_main_content(html_doc)
    if texto2:
        return texto2

    # 3) Fallback genérico: bloque con más párrafos
    texto3 = _fallback_generico(html_doc)
    if texto3:
        return texto3

    return None


def htmls_y_target(dir_de_1_categoria: str) -> Tuple[List[str], List[str]]:
    htmls: List[str] = []
    categoria = os.path.basename(os.path.normpath(dir_de_1_categoria))

    for archivo_html in os.listdir(dir_de_1_categoria):
        path_completo_html = os.path.join(dir_de_1_categoria, archivo_html)

        # Solo procesar HTMLs
        if not os.path.isfile(path_completo_html) or not _es_html(path_completo_html):
            continue

        try:
            html = leer_archivo(path_completo_html)
            texto = pasar_html_a_texto(html)
            if texto:
                htmls.append(texto)
            else:
                print(f"CUIDADO! No fue posible extraer el texto de la nota del archivo {path_completo_html}")
        except Exception as e:
            print(f"[ERROR] Leyendo {path_completo_html}: {e}")

    target_class = [categoria] * len(htmls)
    return htmls, target_class


# ---------- main ----------
if __name__ == "__main__":
    todos_los_htmls: List[str] = []
    todos_los_targets: List[str] = []

    if not os.path.isdir(DIR_BASE_CATEGORIAS):
        raise RuntimeError(f"No existe el directorio base: {DIR_BASE_CATEGORIAS}")

    un_dir_por_categoria = [
        subdir for subdir in os.listdir(DIR_BASE_CATEGORIAS)
        if os.path.isdir(os.path.join(DIR_BASE_CATEGORIAS, subdir))
    ]
    if not un_dir_por_categoria:
        raise RuntimeError(f"No se encontraron subdirectorios en {DIR_BASE_CATEGORIAS}")

    for dir_por_categoria in un_dir_por_categoria:
        full_dir = os.path.join(DIR_BASE_CATEGORIAS, dir_por_categoria)
        htmls, targets = htmls_y_target(full_dir)
        print(f"[INFO] {dir_por_categoria}: {len(htmls)} documentos válidos.")
        todos_los_htmls.extend(htmls)
        todos_los_targets.extend(targets)

    if not todos_los_htmls:
        raise RuntimeError("No se extrajo ningún texto. Revisar selectores/plantillas.")

    # Stopwords
    if os.path.isfile(STOPWORDS_FILE_SIN_ACENTOS):
        mi_lista_stopwords = leer_stopwords(STOPWORDS_FILE_SIN_ACENTOS)
    elif os.path.isfile(STOPWORDS_FILE):
        mi_lista_stopwords = leer_stopwords(STOPWORDS_FILE)
    else:
        print("[WARN] No se encontraron stopwords; se continúa sin ellas.")
        mi_lista_stopwords = None

    vectorizer = CountVectorizer(
        stop_words=mi_lista_stopwords,
        tokenizer=mi_tokenizer,   # pasar callable, NO llamar
        token_pattern=None,       # evita conflicto con tokenizer custom
        lowercase=True,
        strip_accents='unicode',
        decode_error='ignore',
        ngram_range=(MIN_NGRAMS, MAX_NGRAMS),
        min_df=MIN_DF,
        max_df=MAX_DF
    )

    X = vectorizer.fit_transform(todos_los_htmls)
    joblib.dump(X, VECTORS_FILE)
    joblib.dump(todos_los_targets, TARGETS_FILE)
    print("Finalizado, el dataset está en {} y {}.".format(VECTORS_FILE, TARGETS_FILE))

    try:
        nombres_features = vectorizer.get_feature_names_out().tolist()
    except AttributeError:
        nombres_features = vectorizer.get_feature_names()
    joblib.dump(nombres_features, FEATURE_NAMES_FILE)
    print("El nombre de cada columna de features esta en {}.".format(FEATURE_NAMES_FILE))
