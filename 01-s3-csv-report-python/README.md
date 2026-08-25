# S3 CSV Report (Python)

**Objetivo:** procesar un CSV subido a S3 y generar un reporte agregado, disparado por evento.
**Servicios AWS:** S3, Lambda (Layer AWSSDKPandas), IAM, CloudWatch Logs
**Lenguaje:** Python 3.13 (pandas, boto3)
**Estado:** ✅ funcionando de punta a punta

_Todo el pipeline se despliega y corre en AWS vía CLI — no necesitas Python ni un entorno virtual instalado localmente para reproducirlo._

## Estructura de datos

### CSV de entrada (esperado)

Basado en el dataset Sample - Superstore de Kaggle. El pipeline solo lee `Category` y `Sales` — el resto de columnas se ignora (queda disponible por si se extiende la agregación más adelante).

| Columna | Tipo | Ejemplo |
|---|---|---|
| Row ID | int | 1 |
| Order ID | string | CA-2024-100006 |
| Order Date / Ship Date | date | 2024-01-15 |
| Ship Mode | string | Standard Class |
| Customer ID / Customer Name | string | AB-10015 / ... |
| Segment | string | Consumer |
| Country / City / State / Postal Code / Region | string | ... |
| Product ID | string | FUR-BO-10001798 |
| **Category** | string | Furniture |
| Sub-Category | string | Bookcases |
| Product Name | string | ... |
| **Sales** | float | 261.96 |
| Quantity | int | 2 |
| Discount | float | 0.0 |
| Profit | float | 41.91 |

### CSV de salida (generado en `output/`)

| Columna | Tipo | Ejemplo |
|---|---|---|
| Category | string | Technology |
| Sales | float | 836154.03 |
| processed_at | ISO 8601 (UTC) | 2026-08-24T02:30:36.366922+00:00 |

Siempre 3 filas (una por categoría del dataset), ordenadas de mayor a menor venta. Nombre del archivo: `<nombre-original>-report.csv`.

## Cómo correrlo

### 0. Dataset

Descarga `Sample - Superstore.csv` desde [Kaggle](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final) y colócalo en esta carpeta (no se sube al repo, ver Notas).

### 1. Infraestructura — bucket (creado a mano vía AWS CLI)

Bucket: `<tu-bucket-unico>` (región: us-east-1) — reemplaza por tu nombre de bucket real al ejecutar.

```bash
aws s3 mb s3://<tu-bucket-unico> --region us-east-1
aws s3api put-object --bucket <tu-bucket-unico> --key input/
aws s3api put-object --bucket <tu-bucket-unico> --key output/
```

### 2. Infraestructura — rol de IAM para la Lambda

`trust-policy.json` (quién puede usar el rol) y `lambda-policy.template.json` (qué puede hacer, con `__BUCKET_NAME__` como placeholder) ya están en este repo. Genera el permiso real con tu bucket:

```bash
sed 's/__BUCKET_NAME__/<tu-bucket-unico>/g' lambda-policy.template.json > lambda-policy.json
```

Crea el rol y adjunta los permisos:

```bash
aws iam create-role \
  --role-name aws-daily-builds-01-role \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name aws-daily-builds-01-role \
  --policy-name aws-daily-builds-01-policy \
  --policy-document file://lambda-policy.json
```

`lambda-policy.json` no se sube al repo (contiene tu bucket real) — se regenera con el comando de arriba.

### 3. Lambda

Empaqueta el código (pandas no va en el zip, viene de un Layer):

```bash
zip lambda_function.zip lambda_function.py
```

Crea la función (espera ~10-15s después del paso 2 por propagación de IAM):

```bash
ROLE_ARN=$(aws iam get-role --role-name aws-daily-builds-01-role --query 'Role.Arn' --output text)

aws lambda create-function \
  --function-name aws-daily-builds-01-csv-report \
  --runtime python3.13 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 30 \
  --layers arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313:16
```

Verifica que quedó activa:

```bash
aws lambda get-function --function-name aws-daily-builds-01-csv-report --query 'Configuration.State' --output text
```

### 4. Trigger S3 → Lambda

Permiso para que S3 invoque la Lambda:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
FUNCTION_ARN=$(aws lambda get-function --function-name aws-daily-builds-01-csv-report --query 'Configuration.FunctionArn' --output text)

aws lambda add-permission \
  --function-name aws-daily-builds-01-csv-report \
  --statement-id s3-trigger-permission \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::<tu-bucket-unico> \
  --source-account "$ACCOUNT_ID"
```

Notificación del bucket, generada desde `notification.template.json` (usa `|` como delimitador de `sed` porque el ARN trae `/`), filtrada a `input/*.csv` para evitar loop infinito con lo que la Lambda escribe en `output/`:

```bash
sed "s|__FUNCTION_ARN__|$FUNCTION_ARN|g" notification.template.json > notification.json

aws s3api put-bucket-notification-configuration \
  --bucket <tu-bucket-unico> \
  --notification-configuration file://notification.json
```

### 5. Probar el pipeline

Sube el CSV a `input/` y espera unos segundos:

```bash
aws s3 cp "Sample - Superstore.csv" s3://<tu-bucket-unico>/input/
```

Verifica que se generó el reporte:

```bash
aws s3 ls s3://<tu-bucket-unico>/output/
```

Si algo falla, revisa los logs de CloudWatch:

```bash
aws logs tail /aws/lambda/aws-daily-builds-01-csv-report --since 5m
```

## Notas

- Bucket y rol creados a mano por AWS CLI (no Terraform) — se decidió terraformear este mismo build más adelante como ejercicio v2, una vez dominado el patrón manual.
- El dataset no se versiona en el repo por licencia — se descarga por separado (ver paso 0 y "Estructura de datos" arriba).
- `lambda_function.zip`, `lambda-policy.json` y `notification.json` son artefactos generados localmente a partir de sus `.template.json`/código fuente, ignorados por git.
- Trigger filtrado a `input/*.csv` para evitar que la Lambda se dispare a sí misma al escribir en `output/`.
- **Gotcha 1:** el `key` que llega en el evento de S3 viene URL-encoded — nombres de archivo con espacios rompen `get_object()` si no se decodifica con `urllib.parse.unquote_plus()`. El error que arroja (`AccessDenied` / `ListBucket`) es engañoso: S3 oculta el verdadero `404` por seguridad, no por falta real de permisos.
- **Gotcha 2:** el CSV de origen no está en UTF-8 (viene en `latin1`/Windows-1252, común en exports de Excel/Windows) — hubo que especificar `encoding="latin1"` en `pd.read_csv()`.