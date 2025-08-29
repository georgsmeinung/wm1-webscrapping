# -*- coding: utf-8 -*-
"""
predecir_en_validacion.py
Aplica un modelo ya ENTRENADO a los HTMLs del grupo de Validación.
Imprime métricas y guarda un CSV con las predicciones.

Cómo usarlo:
1) Editar el bloque CONFIG con tus rutas.
2) Abrir este archivo en VS Code y presionar Run ▶️.
"""

import os
from pathlib import Path
from typing import List, Tuple, Dict
import joblib
import numpy as np

from bs4 import BeautifulSoup
from sklearn.preprocessing import LabelEncoder, label_binarize
from sklearn.metrics import (
    accuracy_score, confusion_matrix, classification_report,
    roc_auc_score
)

# ==========
# CONFIG (EDITAR ESTAS RUTAS)
# ==========
VALIDACION_DIR = Path(r"C:\Users\juanm\tp_web_mining1\data\raw\Validacion")
MODELO_PATH    = Path(r"C:\Users\juanm\tp_web_mining1\models\modelo_pipeline.joblib")
LABELENC_PATH  = Path(r"C:\Users\juanm\tp_web_mining1\models\label_encoder.joblib")
# (opcional/alternativo) solo si NO guardaste todo como pipeline:
VECTORIZER_PATH = Path(r"C:\Users\juanm\tp_web_mining1\models\vectorizer.joblib")   # opcional
SELECTOR_PATH   = Path(r"C:\Users\juanm\tp_web_mining1\models\selector.joblib")     # opcional

SALIDA_DIR  = Path(r"C:\Users\juanm\tp_web_mining1\reports")
CSV_SALIDA  = SALIDA_DIR / "predicciones_validacion.csv"

EXTS = {".html", ".htm"}  # extensiones válidas

# ===================================
# Utilitarios de lectura y preparación
# ===================================
def leer_html(path: Path) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = path.read_text(errors="ignore")
    soup = BeautifulSoup(txt, "lxml")
    # Extrae texto visible
    return soup.get_text(separator=" ", strip=True)

def cargar_docs_y_labels(base_validacion: Path) -> Tuple[List[str], List[str], List[Path]]:
    textos, labels, rutas = [], [], []
    for categoria_dir in sorted([d for d in base_validacion.iterdir() if d.is_dir()]):
        categoria = categoria_dir.name
        for p in categoria_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                textos.append(leer_html(p))
                labels.append(categoria)
                rutas.append(p)
    return textos, labels, rutas

def cargar_modelo_y_encoder() -> Tuple[object, LabelEncoder, object, object]:
    """
    Retorna (modelo_pipeline, label_encoder, vectorizer_opcional, selector_opcional).
    Si el pipeline no tiene vectorizador, intentamos cargar vectorizer/selector aparte.
    """
    if not MODELO_PATH.exists():
        raise FileNotFoundError(f"No se encontró el modelo entrenado: {MODELO_PATH}")
    modelo = joblib.load(MODELO_PATH)

    if not LABELENC_PATH.exists():
        raise FileNotFoundError(f"No se encontró el LabelEncoder: {LABELENC_PATH}")
    le: LabelEncoder = joblib.load(LABELENC_PATH)

    vectorizer, selector = None, None
    # Si tu pipeline NO incluye vectorizador/selector, cargalos aparte:
    if VECTORIZER_PATH.exists():
        try:
            vectorizer = joblib.load(VECTORIZER_PATH)
        except Exception:
            vectorizer = None
    if SELECTOR_PATH.exists():
        try:
            selector = joblib.load(SELECTOR_PATH)
        except Exception:
            selector = None

    return modelo, le, vectorizer, selector

def _tiene_metodo(modelo, nombre: str) -> bool:
    return hasattr(modelo, nombre) and callable(getattr(modelo, nombre))

def _obtener_scores(modelo, X):
    """
    Devuelve scores continuos para AUC:
    - usa predict_proba si existe
    - si no, usa decision_function si existe
    - si no, devuelve None
    """
    if _tiene_metodo(modelo, "predict_proba"):
        try:
            return modelo.predict_proba(X)
        except Exception:
            pass
    if _tiene_metodo(modelo, "decision_function"):
        try:
            return modelo.decision_function(X)
        except Exception:
            pass
    return None

def _topk(arr: np.ndarray, k: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Retorna (indices_topk, valores_topk) por fila."""
    k = min(k, arr.shape[1])
    idx = np.argpartition(arr, -k, axis=1)[:, -k:]
    # ordenar esos k desc
    row_indices = np.arange(arr.shape[0])[:, None]
    sorted_order = np.argsort(arr[row_indices, idx], axis=1)[:, ::-1]
    idx_sorted = idx[row_indices, sorted_order]
    vals_sorted = arr[row_indices, idx_sorted]
    return idx_sorted, vals_sorted

# ================
# Flujo principal
# ================
def main():
    print("[INFO] Cargando documentos de Validación...")
    X_textos, y_labels, rutas = cargar_docs_y_labels(VALIDACION_DIR)
    if not X_textos:
        raise SystemExit(f"[ERROR] No se encontraron HTMLs en {VALIDACION_DIR}")

    print(f"[INFO] Docs: {len(X_textos)} | Categorías reales: {len(set(y_labels))}")

    print("[INFO] Cargando modelo y LabelEncoder...")
    modelo, le, vectorizer, selector = cargar_modelo_y_encoder()

    # Codificar labels reales con el encoder del entrenamiento
    # (si aparece una clase no vista, la ignoramos en métricas agregadas)
    clases_entrenadas = set(le.classes_)
    mask_vistas = [lbl in clases_entrenadas for lbl in y_labels]
    unseen = sum(1 for m in mask_vistas if not m)
    if unseen > 0:
        print(f"[WARN] {unseen} documentos pertenecen a clases NO vistas en entrenamiento; "
              "se excluyen de ciertas métricas.")

    # Transformar textos -> features, de acuerdo a lo que tengamos guardado
    print("[INFO] Transformando textos...")
    use_pipeline_direct = hasattr(modelo, "named_steps") and ("tfidf" in getattr(modelo, "named_steps"))
    X = None
    if not use_pipeline_direct:
        if vectorizer is not None:
            X = vectorizer.transform(X_textos)
            if selector is not None:
                X = selector.transform(X)

    # Predicción y scores
    print("[INFO] Prediciendo...")
    if use_pipeline_direct:
        y_pred = modelo.predict(X_textos)              # <- texto crudo
        scores = _obtener_scores(modelo, X_textos)
    else:
        if X is None:
            raise SystemExit("[ERROR] No hay vectorizador/selector externo cargado y el modelo no es pipeline con tfidf.")
        y_pred = modelo.predict(X)                     # <- matriz vectorizada
        scores = _obtener_scores(modelo, X)

    # Métricas (sobre docs con clases vistas)
    y_labels_vistas = [lbl for lbl, ok in zip(y_labels, mask_vistas) if ok]
    y_pred_vistas   = [p   for p,   ok in zip(y_pred,   mask_vistas) if ok]

    # Si el modelo devuelve índices, mapear a nombres de clase
    if np.issubdtype(np.array(y_pred_vistas).dtype, np.number):
        # convertimos a nombres usando le.classes_
        y_pred_vistas = [le.classes_[int(i)] for i in y_pred_vistas]
        y_pred_nombres = [le.classes_[int(i)] for i in y_pred]
    else:
        y_pred_nombres = y_pred  # ya son nombres

    # Accuracy & reporte
    acc = accuracy_score(y_labels_vistas, y_pred_vistas) if y_labels_vistas else float("nan")
    print(f"\n[METRICAS] Accuracy (solo clases vistas) = {acc:.4f}")
    print("\n[METRICAS] Matriz de confusión (solo clases vistas):")
    print(confusion_matrix(y_labels_vistas, y_pred_vistas, labels=list(le.classes_)))
    print("\n[METRICAS] Classification report:")
    print(classification_report(y_labels_vistas, y_pred_vistas, labels=list(le.classes_), zero_division=0))

    # AUC macro/weighted si tenemos scores
    if scores is not None and len(set(y_labels_vistas)) > 1:
        # Convertir y reales a índices
        y_true_idx = le.transform(y_labels_vistas)
        y_true_bin = label_binarize(y_true_idx, classes=range(len(le.classes_)))
        # alineamos scores por fila
        scores_vistas = np.asarray([s for s, ok in zip(scores, mask_vistas) if ok])
        try:
            auc_macro = roc_auc_score(y_true_bin, scores_vistas, average="macro", multi_class="ovr")
            auc_weighted = roc_auc_score(y_true_bin, scores_vistas, average="weighted", multi_class="ovr")
            print(f"\n[METRICAS] ROC AUC macro     = {auc_macro:.4f}")
            print(f"[METRICAS] ROC AUC weighted  = {auc_weighted:.4f}")
        except Exception as e:
            print(f"[WARN] No se pudo calcular AUC multiclase: {e}")
    else:
        print("\n[INFO] No hay scores continuos disponibles; omito AUC.")

    # CSV de salida con top-3
    print(f"\n[INFO] Guardando CSV en {CSV_SALIDA}")
    SALIDA_DIR.mkdir(parents=True, exist_ok=True)

    # Preparar columnas
    rutas_str = [str(p) for p in rutas]
    verdaderas = y_labels
    predichas  = y_pred_nombres

    # Top-3
    top1, top2, top3 = [], [], []
    if scores is not None:
        scores = np.asarray(scores)
        idx_top3, vals_top3 = _topk(scores, k=3)
        clases = np.array(le.classes_)
        for ids, vals in zip(idx_top3, vals_top3):
            pares = [(clases[i], float(v)) for i, v in zip(ids, vals)]
            # normalizar a 3 elementos por si hay menos clases
            while len(pares) < 3:
                pares.append(("", float("nan")))
            (c1, v1), (c2, v2), (c3, v3) = pares[:3]
            top1.append(f"{c1}:{v1:.4f}")
            top2.append(f"{c2}:{v2:.4f}")
            top3.append(f"{c3}:{v3:.4f}")
    else:
        top1 = ["" for _ in rutas]
        top2 = ["" for _ in rutas]
        top3 = ["" for _ in rutas]

    # Escribir CSV (sin pandas para evitar dependencias)
    import csv
    with open(CSV_SALIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta_archivo", "label_real", "label_predicha", "top1", "top2", "top3"])
        for r, vr, vp, t1, t2, t3 in zip(rutas_str, verdaderas, predichas, top1, top2, top3):
            w.writerow([r, vr, vp, t1, t2, t3])

    print("[OK] Proceso finalizado.")

if __name__ == "__main__":
    # Evita que VS Code ejecute cosas al importar.
    main()
