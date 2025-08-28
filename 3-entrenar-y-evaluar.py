# -*- coding: utf-8 -*-
"""
Lee el dataset vectorizado y entrena/evalúa con CV.
"""
from typing import Dict

import joblib
import numpy as np
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.metrics import accuracy_score, auc, confusion_matrix, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import LabelEncoder, label_binarize
from sklearn.svm import SVC

VECTORS_FILE = "vectores.joblib"
TARGETS_FILE = "targets.joblib"
FEATURE_NAMES_FILE = "features.joblib"

def _calcular_auc_por_clase(targets_reales_bin, targets_scores) -> Dict[int, float]:
    """
    targets_reales_bin: (n_samples, n_clases) en 0/1
    targets_scores:     (n_samples, n_clases) scores continuos (prob o decision)
    """
    fpr, tpr, roc_auc = {}, {}, {}
    n_clases = targets_scores.shape[1]
    for i in range(n_clases):
        y_true = targets_reales_bin[:, i]
        y_score = targets_scores[:, i]
        # si en el fold no hay positivos o negativos para esa clase, ROC falla
        if y_true.max() == y_true.min():
            roc_auc[i] = float("nan")
            continue
        fpr[i], tpr[i], _ = roc_curve(y_true, y_score)
        roc_auc[i] = auc(fpr[i], tpr[i])
    return roc_auc

def calcular_e_imprimir_auc(clasificador, train_X, train_y, test_X, test_y, idx_a_clase):
    """
    Entrena OneVsRest y calcula AUC por clase usando scores continuos.
    """
    ovr = OneVsRestClassifier(clasificador)
    ovr.fit(train_X, train_y)

    if hasattr(ovr, "decision_function"):
        scores = ovr.decision_function(test_X)
    else:
        scores = ovr.predict_proba(test_X)

    n_clases = len(idx_a_clase)
    test_bin = label_binarize(test_y, classes=range(0, n_clases))
    for i, valor_auc in _calcular_auc_por_clase(test_bin, scores).items():
        print("\tAUC para la clase #{} ({}): {}".format(i, idx_a_clase[i], valor_auc))

def pesos_de_features(score_fn, train_fold, train_targets_fold) -> np.ndarray:
    # score_fn debe aceptar matriz 2D (todas las columnas a la vez), p.ej., chi2
    scores, _ = score_fn(train_fold, train_targets_fold)
    # scores viene como array shape (n_features,), lo aplanamos por las dudas
    return np.asarray(scores).ravel()


def imprimir_features_con_pesos(score_fn, train_fold, train_targets_fold, nombres_features, top_n=-1):
    pesos_features = pesos_de_features(score_fn, train_fold, train_targets_fold)
    idx_desc = np.argsort(pesos_features)[::-1]
    n_feats = train_fold.shape[1]
    if top_n == -1 or top_n > n_feats:
        top_n = n_feats
    for i in range(top_n):
        j = idx_desc[i]
        print(nombres_features[j], '\t', float(pesos_features[j]))


def nombres_features_seleccionadas(selector_features, nombres_features):
    cols = selector_features.get_support()
    return [feat for selected, feat in zip(cols, nombres_features) if selected]

# --- carga
vectores = joblib.load(VECTORS_FILE)
nombres_targets = joblib.load(TARGETS_FILE)
nombres_features = joblib.load(FEATURE_NAMES_FILE)

label_encoder = LabelEncoder()
targets = label_encoder.fit_transform(nombres_targets)
idx_a_clase = label_encoder.classes_
n_categorias = len(idx_a_clase)

clasificador = SVC(kernel='linear', probability=True)
MAX_FEATURES = 150
CANT_FOLDS_CV = 5

n_fold = 1
accuracy_promedio = 0.0

for train_index, test_index in StratifiedKFold(n_splits=CANT_FOLDS_CV, shuffle=True, random_state=None).split(vectores, targets):
    train_fold = vectores[train_index]
    train_targets_fold = targets[train_index]
    test_fold = vectores[test_index]
    test_targets_fold = targets[test_index]

    # Imprimir pesos (ojo: puede ser lento)
    imprimir_features_con_pesos(chi2, train_fold, train_targets_fold, nombres_features, MAX_FEATURES)

    k_sel = min(MAX_FEATURES, train_fold.shape[1])
    selector_features = SelectKBest(score_func=chi2, k=k_sel).fit(train_fold, train_targets_fold)

    train_fold_selected = selector_features.transform(train_fold)
    test_fold_selected = selector_features.transform(test_fold)

    # One-vs-Rest + scores para AUC
    ovr = OneVsRestClassifier(clasificador)
    ovr.fit(train_fold_selected, train_targets_fold)
    preds_fold = ovr.predict(test_fold_selected)  # para accuracy
    print("FOLD #{}, # train = {}, # test = {}".format(n_fold, train_fold.shape[0], test_fold_selected.shape[0]))

    print("FEATURES SELECCIONADAS:")
    print(nombres_features_seleccionadas(selector_features, nombres_features))

    accuracy_fold = accuracy_score(test_targets_fold, preds_fold)
    accuracy_promedio += accuracy_fold
    print("Accuracy del fold #{} = {}".format(n_fold, accuracy_fold))

    # AUC por clase con scores continuos
    calcular_e_imprimir_auc(clasificador, train_fold_selected, train_targets_fold, test_fold_selected, test_targets_fold, idx_a_clase)

    print("\tMatriz de confusion (filas=real, columnas=prediccion):")
    print(confusion_matrix(test_targets_fold, preds_fold))

    n_fold += 1

print("\nAccuracy promedio = {}".format(accuracy_promedio / (n_fold - 1)))
