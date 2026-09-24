resource "aws_s3_bucket" "features" {
  bucket        = "${local.name_prefix}-features-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-features"
    Zone = "features"
  })
}

resource "aws_s3_bucket_public_access_block" "features" {
  bucket = aws_s3_bucket.features.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "features" {
  bucket = aws_s3_bucket.features.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}