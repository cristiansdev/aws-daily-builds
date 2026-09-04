import boto3
import joblib
import pandas as pd
import io
import os
from urllib.parse import unquote_plus

s3 = boto3.client("s3")

MODEL_BUCKET = os.environ["MODEL_BUCKET"]
MODEL_KEY = "model/isolation_forest.joblib"

# --- Carga del artefacto FUERA del handler (warm start) ---
# Descarga el .joblib de S3 UNA VEZ cuando arranca el contenedor de Lambda,
# no en cada invocación. Pistas:
#   - s3.download_file(MODEL_BUCKET, MODEL_KEY, "/tmp/modelo.joblib")
#     (Lambda solo permite escribir en /tmp, no en el filesystem normal)
#   - luego joblib.load("/tmp/modelo.joblib")
#   - el resultado es tu diccionario {"modelo":..., "umbral":..., "features":...}
#     — el mismo que ya validaste en el notebook

s3.download_file(MODEL_BUCKET, MODEL_KEY, "/tmp/modelo.joblib")

artefacto = joblib.load("/tmp/modelo.joblib")

def lambda_handler(event, context):
    # 1. Sacar bucket y key del evento S3
    #    Recuerda el gotcha del build 1: el key llega URL-encoded,
    #    hay que aplicar unquote_plus() antes de usarlo
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])

    # 2. Descargar el CSV de input/ — puedes bajarlo a /tmp/ igual que el modelo,
    #    o leerlo directo a memoria con s3.get_object() + io.BytesIO()
    #    y pd.read_csv() sobre ese buffer (sin tocar disco)
    response = s3.get_object(Bucket=bucket, Key=key)
    contenido = response["Body"].read()
    df = pd.read_csv(io.BytesIO(contenido))

    # 3. Seleccionar EXACTAMENTE las columnas de artefacto["features"],
    #    en ese orden, y convertir a .values — el mismo patrón que en train.py.
    #    Si el CSV de entrada no trae esas columnas, aquí es donde vas a
    #    descubrirlo con un KeyError

    X = df[artefacto["features"]].values

    # 4. Aplicar el modelo: decision_function() + comparar contra artefacto["umbral"]
    #    (no uses .predict() directo — recuerda que el corte final lo decide
    #    el umbral calculado, no el contamination del modelo)

    scores = artefacto["modelo"].decision_function(X)
    etiquetas = (-scores > artefacto["umbral"]).astype(int)

    # 5. Armar el reporte: filas originales + columna de score + columna de etiqueta
    #    (normal/anómala) — piensa en qué le sirve más a quien lo va a revisar

    df["score_anomalia"] = scores
    df["es_anomalia"] = etiquetas

    df = df.sort_values("score_anomalia")
    # 6. Subir el reporte a output/ como CSV
    #    (buffer con io.StringIO() + reporte.to_csv(buffer) + s3.put_object())

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)

    output_key = key.replace("input/", "output/")
    s3.put_object(
        Bucket=bucket
        ,Key=output_key
        ,Body=buffer.getvalue()
    )

    return {
        "statusCode": 200,
        "body": f"Procesadas {len(df)} transacciones, {etiquetas.sum()} anómalas"
    }