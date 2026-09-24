resource "aws_s3_bucket" "raw" {
  bucket        = "${local.name_prefix}-raw-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-raw"
    Zone = "raw"
  })
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}