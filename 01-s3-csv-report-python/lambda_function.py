import boto3
import pandas as pd
import io
import urllib.parse
from datetime import datetime, timezone

s3 = boto3.client('s3')

def lambda_handler(event, context):
    record = event["Records"][0]["s3"]
    bucket_name = record["bucket"]["name"]
    # El key llega URL-encoded (espacios como "+", acentos como %XX) — hay que decodificarlo
    key = urllib.parse.unquote_plus(record["object"]["key"])

    response = s3.get_object(Bucket=bucket_name, Key=key)
    # El dataset viene en latin1/Windows-1252, no UTF-8 (común en exports de Excel)
    df = pd.read_csv(io.BytesIO(response["Body"].read()), encoding="latin1")

    summary_df = df.groupby('Category')['Sales'].sum().reset_index().sort_values(by='Sales', ascending=False)
    summary_df['Sales'] = summary_df['Sales'].round(2)
    summary_df['processed_at'] = datetime.now(timezone.utc).isoformat()

    output_key = key.replace("input/", "output/").replace(".csv", "-report.csv")
    output_buffer = io.StringIO()
    summary_df.to_csv(output_buffer, index=False)

    s3.put_object(Bucket=bucket_name, Key=output_key, Body=output_buffer.getvalue())
    return {"statusCode": 200, "body": f"Reporte generado: {output_key}"}