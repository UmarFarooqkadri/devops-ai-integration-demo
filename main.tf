# main.tf

provider "aws" {
  region = "us-west-2"
}

resource "aws_s3_bucket" "b" {
  bucket = "my-ai-model-bucket"
  acl    = "private"
}

resource "kubernetes_cluster" "example" {
  name     = "example-cluster"
  location = "us-west-2"
}
