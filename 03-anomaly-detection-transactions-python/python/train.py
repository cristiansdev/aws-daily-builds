import numpy as np
import pandas as pd

import joblib
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_curve

from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "create-model" / "data" / "creditcard.csv"
df = pd.read_csv(DATA_PATH)

features = [f"V{i}" for i in range(1, 29)] + ["Amount"]
X = df[features].values

modelo = IsolationForest(random_state=42)
modelo.fit(X)

scores = modelo.decision_function(X)

precision, recall, thresholds = precision_recall_curve(df['Class'], -scores)

f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)
mejor_idx = np.argmax(f1_scores)
UMBRAL_OPTIMO = thresholds[mejor_idx]

artefacto = {
    "modelo": modelo,
    "umbral": UMBRAL_OPTIMO,
    "features": features,  # V1-V28 + Amount, para no depender del orden a mano
}

joblib.dump(artefacto, "isolation_forest.joblib")

print(f"Umbral óptimo: {UMBRAL_OPTIMO:.4f}")
print(f"Precision: {precision[mejor_idx]:.2f}, Recall: {recall[mejor_idx]:.2f}")
print(f"Modelo guardado en: isolation_forest.joblib")