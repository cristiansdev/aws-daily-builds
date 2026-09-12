output "queue_url" {
  value = aws_sqs_queue.main.id
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.id
}

output "table_name" {
  value = aws_dynamodb_table.conciliadas.name
}
