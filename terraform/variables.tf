variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-north-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "devops-ai-platform"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  type        = string
  default     = "t3.large"
}

variable "node_count_min" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "node_count_max" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 6
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "project_tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    Project = "devops-ai-platform"
    Owner   = "platform-team"
  }
}
