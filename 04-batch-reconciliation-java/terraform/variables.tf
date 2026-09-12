variable "aws_region" {
  description = "Región de AWS donde se despliega la infraestructura"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nombre base para los recursos de este build"
  type        = string
  default     = "batch-reconciliation"
}

variable "max_receive_count" {
  description = "Reintentos antes de mover el mensaje a la DLQ"
  type        = number
  default     = 3
}
