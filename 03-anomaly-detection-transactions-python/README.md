# Detección de anomalías en transacciones

**Objetivo:** detectar transacciones bancarias anómalas usando un modelo de Isolation Forest (scikit-learn) entrenado sobre el dataset de fraude de tarjetas de crédito, servido de forma serverless en AWS Lambda.

**Servicios AWS:** S3 (input/output/modelo/Layer), Lambda, IAM, CloudWatch Logs.

**Lenguaje:** Python

**Estado:** ✅ funcionando de punta a punta — probado con trigger automático de S3, sin invocación manual.

## Arquitectura

```mermaid
flowchart LR
    A[CSV nuevo] -->|sube a| B["S3: input/"]
    B -->|evento ObjectCreated| C[Lambda inferencia]
    D[("S3: model/isolation_forest.joblib")] -.->|descarga 1 vez, warm start| C
    L[("Layer: scikit-learn + pandas + joblib")] -.->|adjunta| C
    C -->|decision_function + umbral| E["S3: output/reporte.csv"]
```

El modelo se entrena **fuera de AWS** (local, con `uv run train.py`) y solo el artefacto ya entrenado (`.joblib`) sube a S3 — separación clara entre entrenamiento e inferencia.

## Estructura de datos

**Dataset de entrenamiento:** [Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) (ULB) — no se incluye en el repo (licencia "Other" no clara), se referencia por link. 284,807 transacciones, 492 fraudes reales.

**Features del modelo:** `V1`-`V28` (componentes PCA) + `Amount`, sin transformar (se probó log-transform, sin mejora medible, descartado — ver notebook de exploración).

**Artefacto serializado (`isolation_forest.joblib`):** diccionario con tres claves:
```python
{
    "modelo": IsolationForest,   # ya entrenado
    "umbral": float,             # 0.1624, calculado vía curva precision-recall + F1
    "features": list[str],       # V1-V28 + Amount, en el orden exacto usado al entrenar
}
```

**Reporte de salida:** CSV con las columnas originales + `score_anomalia` (continuo, más bajo = más anómalo) + `es_anomalia` (0/1), ordenado por severidad (más sospechosas primero).

## Cómo correrlo

0. **Instalar dependencias:**
   ```bash
   uv sync
   ```

1. **Entrenar el modelo** (genera `isolation_forest.joblib`):
   ```bash
   uv run python/train.py
   ```

2. **Armar la Layer de dependencias:**
   ```bash
   uv pip install \
     --no-installer-metadata \
     --no-compile-bytecode \
     --python-platform x86_64-manylinux_2_28 \
     --python 3.13 \
     --prefix packages \
     scikit-learn==1.9.0 joblib==1.5.3 pandas==3.0.5

   mkdir -p layer/python
   cp -r packages/lib layer/python/

   find layer/python -type d \( -name "tests" -o -name "test" \) -exec rm -rf {} + 2>/dev/null
   find layer/python -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

   cd layer && zip -r ../layer_content.zip python && cd ..
   ```

3. **Crear el bucket y subir modelo + Layer:**
   ```bash
   aws s3 mb s3://__BUCKET_NAME__
   aws s3 cp isolation_forest.joblib s3://__BUCKET_NAME__/model/isolation_forest.joblib
   aws s3 cp layer_content.zip s3://__BUCKET_NAME__/layers/layer_content.zip
   ```

4. **Publicar la Layer** (guarda el `LayerVersionArn` del output):
   ```bash
   aws lambda publish-layer-version \
     --layer-name sklearn-anomaly-detection \
     --content S3Bucket=__BUCKET_NAME__,S3Key=layers/layer_content.zip \
     --compatible-runtimes python3.13 \
     --compatible-architectures x86_64
   ```

5. **Rol IAM** (reusa `trust-policy.json` del build 1; genera `lambda-policy.json` real a partir de `lambda-policy.template.json` con `sed`):
   ```bash
   aws iam create-role \
     --role-name anomaly-detection-lambda-role \
     --assume-role-policy-document file://trust-policy.json

   sed 's|__BUCKET_NAME__|tu-bucket-real|g' lambda-policy.template.json > lambda-policy.json

   aws iam put-role-policy \
     --role-name anomaly-detection-lambda-role \
     --policy-name anomaly-detection-s3-access \
     --policy-document file://lambda-policy.json
   ```

6. **Empaquetar y crear la Lambda:**
   ```bash
   cd python && zip function.zip lambda_function.py && cd ..

   aws lambda create-function \
     --function-name anomaly-detection-inference \
     --runtime python3.13 \
     --role arn:aws:iam::__ACCOUNT_ID__:role/anomaly-detection-lambda-role \
     --handler lambda_function.lambda_handler \
     --zip-file fileb://python/function.zip \
     --layers __LAYER_VERSION_ARN__ \
     --timeout 30 \
     --memory-size 512
   ```

7. **Conectar el trigger de S3** (permiso + notificación; genera `notification.json` real a partir de `notification.template.json` con `sed`):
   ```bash
   aws lambda add-permission \
     --function-name anomaly-detection-inference \
     --statement-id s3-trigger-permission \
     --action lambda:InvokeFunction \
     --principal s3.amazonaws.com \
     --source-arn arn:aws:s3:::__BUCKET_NAME__

   sed 's|__FUNCTION_ARN__|tu-function-arn-real|g' notification.template.json > notification.json

   aws s3api put-bucket-notification-configuration \
     --bucket __BUCKET_NAME__ \
     --notification-configuration file://notification.json
   ```

8. **Probar:** sube un CSV a `input/` y revisa que el reporte aparezca solo en `output/` (sin invocar nada manual):
   ```bash
   aws s3 cp tu_csv_de_prueba.csv s3://__BUCKET_NAME__/input/tu_csv_de_prueba.csv
   aws s3 ls s3://__BUCKET_NAME__/output/
   ```

9. **Limpieza:**
   ```bash
   aws lambda delete-function --function-name anomaly-detection-inference
   aws lambda delete-layer-version --layer-name sklearn-anomaly-detection --version-number __N__
   aws s3 rm s3://__BUCKET_NAME__ --recursive
   aws s3 rb s3://__BUCKET_NAME__
   aws iam delete-role-policy --role-name anomaly-detection-lambda-role --policy-name anomaly-detection-s3-access
   aws iam delete-role --role-name anomaly-detection-lambda-role
   ```

## Notas

- **Gotcha — versión de scikit-learn y etiqueta de plataforma:** `scikit-learn==1.9.0` solo publica wheels para la etiqueta `manylinux_2_28`, no `manylinux2014` (versiones ≤1.7.2 son las últimas con esa etiqueta vieja). Instalar cruzando de Windows/WSL a Linux requiere especificar la etiqueta correcta (`--python-platform x86_64-manylinux_2_28` en `uv pip install`).
- **Gotcha — estructura de una Lambda Layer:** usa `--prefix` (no `--target`) al instalar con `uv pip install`, y el `.zip` debe tener `python/` como carpeta raíz — distinto al empaquetado de una función normal.
- **Límite de tamaño:** Lambda permite 250 MB descomprimidos entre código + todas las Layers. La instalación inicial pesaba 241 MB; remover carpetas `tests/`/`__pycache__` la bajó a 195 MB.
- **Gotcha — consistencia de versiones entre entrenamiento e inferencia:** el artefacto `.joblib` es sensible a la versión exacta de scikit-learn. La Layer fija `scikit-learn==1.9.0` idéntico al de `train.py`, para evitar errores de deserialización o resultados silenciosamente incorrectos.
- **El umbral de decisión no es `contamination`:** se entrena con el default y se calcula un umbral óptimo después, vía `precision_recall_curve` + maximización de F1 sobre `decision_function()`. Ese umbral se guarda junto con el modelo y las features en el mismo `.joblib`.
- **Gotcha — el permiso de invocación es independiente del rol de ejecución:** el rol IAM (`anomaly-detection-lambda-role`) le dice a la Lambda qué puede hacer ella; `aws lambda add-permission` es un mecanismo aparte que le dice a Lambda quién tiene permiso de invocarla desde afuera (en este caso, S3, y solo desde el bucket específico vía `--source-arn`).
- **Gotcha — el filtro de prefijo en la notificación no es opcional:** sin `Filter.Key.FilterRules` limitando el trigger a `input/`, cualquier escritura al bucket (incluyendo el propio reporte que la Lambda escribe en `output/`) dispararía la función de nuevo — riesgo real de loop infinito y costo descontrolado.
- **Rendimiento medido en la prueba real** (CSV de 20 filas): cold start (`Init Duration`) ~6.3s (carga de scikit-learn/pandas desde la Layer + descarga y deserialización del modelo); ejecución del handler ya con todo cargado (`Duration`) ~217 ms; memoria usada ~303 MB de los 512 MB asignados.
- **Warning esperado en logs:** `joblib will operate in serial mode` — Lambda no tiene el recurso (`/dev/shm`) que `joblib` usa para paralelizar por default, así que cae a modo serial automáticamente. No afecta el resultado; irrelevante para el volumen de datos de este build.
- **`lambda-policy.json` y `notification.json` (reales) están excluidos del repo vía `.gitignore`** — contienen el nombre real del bucket y el ARN completo (que incluye el Account ID). Solo se versionan sus plantillas (`.template.json`).
- **Exploración completa del modelo** (intentos con distintos `contamination`, prueba de log-transform descartada, curva precision-recall) documentada en `create-model/notebooks/creation-model.ipynb`.