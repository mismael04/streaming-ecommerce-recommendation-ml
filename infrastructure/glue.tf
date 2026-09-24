resource "aws_s3_object" "feature_pipeline_script" {
  bucket = aws_s3_bucket.features.id
  key    = "scripts/feature_pipeline.py"
  source = "${path.module}/../src/etl/feature_pipeline.py"
  etag   = filemd5("${path.module}/../src/etl/feature_pipeline.py")
}

resource "aws_glue_job" "feature_pipeline" {
  name     = "${local.name_prefix}-feature-pipeline"
  role_arn = aws_iam_role.glue.arn

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.features.bucket}/scripts/feature_pipeline.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"

    "--RAW_PATH" = "s3://${aws_s3_bucket.raw.bucket}/events/"

    "--FEATURES_PATH" = "s3://${aws_s3_bucket.features.bucket}/features/"

    "--enable-metrics" = "true"
  }

  depends_on = [
    aws_s3_object.feature_pipeline_script
  ]

  tags = local.common_tags
}