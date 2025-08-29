# -*- coding: utf-8 -*-
"""
entrenar_y_guardar_modelo_pipeline.py
Entrena un pipeline TFIDF -> SelectKBest(chi2) -> OneVsRest(SVC) con TODO lo que NO está en Validacion/
y guarda: modelo_pipeline.joblib + label_encoder.joblib

Cómo usar:
1) Editá CONFIG con tus rutas.
2) Abrí en VS Code y Run ▶️.
"""

from pathlib import Path
from typing import List, Tuple
import joblib
from bs4 import BeautifulSoup

from sklearn.preprocessing import LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from collections import Counter

# ==========
# CONFIG (EDITAR)
# ==========
BASE_RAW = Path(r"C:\Users\juanm\tp_web_mining1\data\raw")  # contiene economia/, sociedad/, ... y la carpeta Validacion/
VALIDACION_DIRNAME = "Validacion"                           # nombre exacto de la carpeta de validación
MODELS_DIR = Path(r"C:\Users\juanm\tp_web_mining1\models")  # adonde guardar el modelo
MAX_FEATURES_TFIDF = 50000                                  # vocabulario máx TFIDF
K_SELECT = 150                                              # k para SelectKBest (se ajusta a min(k, n_feats))

EXTS = {".html", ".htm"}

def leer_html(path: Path) -> str:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(txt, "lxml")
    return soup.get_text(separator=" ", strip=True)

def cargar_textos_y_labels_entrenamiento(base_raw: Path, validacion_name: str) -> Tuple[List[str], List[str]]:
    textos, labels = [], []
    for cat_dir in sorted([d for d in base_raw.iterdir() if d.is_dir() and d.name != validacion_name]):
        categoria = cat_dir.name
        for p in cat_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                textos.append(leer_html(p))
                labels.append(categoria)
    return textos, labels

def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Leyendo entrenamiento desde: {BASE_RAW} (excluyendo '{VALIDACION_DIRNAME}/')")
    X_texts, y_labels = cargar_textos_y_labels_entrenamiento(BASE_RAW, VALIDACION_DIRNAME)
    if not X_texts:
        raise SystemExit("[ERROR] No se encontraron HTMLs de entrenamiento.")

    print(f"[INFO] Docs entrenamiento: {len(X_texts)} | Categorías: {len(set(y_labels))}")
    print(f"[INFO] Distribución por clase: {Counter(y_labels)}")

    # LabelEncoder
    le = LabelEncoder()
    y = le.fit_transform(y_labels)

    # Pipeline completo
    pipeline = Pipeline(steps=[
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=MAX_FEATURES_TFIDF,
            min_df=2,
            lowercase=True,
            strip_accents="unicode"
        )),
        ("selector", SelectKBest(score_func=chi2, k=K_SELECT)),
        ("clf", OneVsRestClassifier(SVC(kernel="linear", probability=True)))
    ])

    print("[INFO] Entrenando pipeline...")
    pipeline.fit(X_texts, y)

    # Guardar artefactos
    model_path = MODELS_DIR / "modelo_pipeline.joblib"
    le_path    = MODELS_DIR / "label_encoder.joblib"
    joblib.dump(pipeline, model_path)
    joblib.dump(le, le_path)

    # Info útil
    try:
        tfidf = pipeline.named_steps["tfidf"]
        selector = pipeline.named_steps["selector"]
        n_feats_total = len(tfidf.get_feature_names_out())
        n_feats_sel = selector.k if hasattr(selector, "k") else "?"
    except Exception:
        n_feats_total, n_feats_sel = "?", "?"

    print(f"[OK] Modelo guardado: {model_path}")
    print(f"[OK] LabelEncoder guardado: {le_path}")
    print(f"[INFO] Vocab TFIDF: {n_feats_total} | K SelectKBest: {n_feats_sel}")

if __name__ == "__main__":
    main()
