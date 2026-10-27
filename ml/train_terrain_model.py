"""Train the large terrain-only landslide susceptibility model.

This model uses the 18,109 labeled NER terrain records. Rainfall remains
handled by the existing rainfall-aware model at inference time.
"""

from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "landslides" / "NER_Landslide_ML_Dataset.csv"
OUTPUT_DIR = PROJECT_ROOT / "ml" / "outputs"
MODEL_FILE = OUTPUT_DIR / "terrain_model.pkl"
METRICS_FILE = OUTPUT_DIR / "reports" / "terrain_metrics.json"

TARGET_COLUMN = "label"
NUMERIC_FEATURES = ["elevation", "slope", "aspect"]
CATEGORICAL_FEATURES = ["soil_id", "landcover_class"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def main() -> None:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Terrain dataset not found: {DATA_FILE}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(DATA_FILE)
    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing required terrain columns: {missing_columns}")

    data = data[required_columns].dropna().drop_duplicates().copy()
    data["soil_id"] = data["soil_id"].astype(str)
    data["landcover_class"] = data["landcover_class"].astype(str)
    data[TARGET_COLUMN] = data[TARGET_COLUMN].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        data[FEATURE_COLUMNS],
        data[TARGET_COLUMN],
        test_size=0.20,
        random_state=42,
        stratify=data[TARGET_COLUMN],
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    x_train_processed = preprocessor.fit_transform(x_train)
    x_test_processed = preprocessor.transform(x_test)

    model = ExtraTreesClassifier(
        n_estimators=400,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train_processed, y_train)

    probabilities = model.predict_proba(x_test_processed)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "source_dataset": DATA_FILE.name,
        "total_records": int(len(data)),
        "training_records": int(len(x_train)),
        "test_records": int(len(x_test)),
        "positive_records": int(data[TARGET_COLUMN].sum()),
        "negative_records": int((data[TARGET_COLUMN] == 0).sum()),
        "feature_count": int(x_train_processed.shape[1]),
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
    }

    joblib.dump(
        {
            "model": model,
            "preprocessor": preprocessor,
            "feature_columns": FEATURE_COLUMNS,
            "metrics": metrics,
        },
        MODEL_FILE,
        compress=3,
    )
    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"Saved terrain model: {MODEL_FILE}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
