resource "aws_s3_object" "recommender_model" {
  bucket = aws_s3_bucket.features.id
  key    = "models/recommender.tar.gz"
  source = "${path.module}/../build/model.tar.gz"

  etag = filemd5(
    "${path.module}/../build/model.tar.gz"
  )

  depends_on = [
    aws_s3_bucket.features
  ]
}

resource "aws_sagemaker_model" "recommender" {
  execution_role_arn = aws_iam_role.sagemaker.arn

  primary_container {
    image = "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1.0-cpu-py310"

    model_data_url = "s3://${aws_s3_bucket.features.bucket}/models/recommender.tar.gz"

    environment = {
      SAGEMAKER_PROGRAM             = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY    = "/opt/ml/model"
      SAGEMAKER_CONTAINER_LOG_LEVEL = "20"
      SAGEMAKER_REGION              = "us-east-1"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-recommender"
  })

  depends_on = [
    aws_s3_object.recommender_model,
    aws_iam_role_policy.sagemaker_s3
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint_configuration" "recommender" {
  production_variants {
    variant_name = "AllTraffic"

    model_name = aws_sagemaker_model.recommender.name

    initial_variant_weight = 1.0

    serverless_config {
      max_concurrency   = 5
      memory_size_in_mb = 2048
    }
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "recommender" {
  name = "${local.name_prefix}-recommender"

  endpoint_config_name = aws_sagemaker_endpoint_configuration.recommender.name

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-recommender"
  })

  lifecycle {
    create_before_destroy = true
  }
}