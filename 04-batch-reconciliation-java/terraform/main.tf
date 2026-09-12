terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_sqs_queue" "dlq" {
  name = "${var.project_name}-dlq"
}

resource "aws_sqs_queue" "main" {
  name                       = "${var.project_name}-queue"
  visibility_timeout_seconds = 60

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_dynamodb_table" "conciliadas" {
  name         = "${var.project_name}-transacciones"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id_transaccion"

  attribute {
    name = "id_transaccion"
    type = "S"
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.main.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.conciliadas.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "reconciliation" {
  function_name    = "${var.project_name}-handler"
  runtime          = "java21"
  handler          = "com.portfolio.reconciliation.ReconciliationHandler::handleRequest"
  role             = aws_iam_role.lambda_role.arn
  filename         = "../target/reconciliation-handler.jar"
  source_code_hash = filebase64sha256("../target/reconciliation-handler.jar")
  timeout          = 30
  memory_size      = 512

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.conciliadas.name
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.main.arn
  function_name    = aws_lambda_function.reconciliation.arn
  batch_size       = 1
}
