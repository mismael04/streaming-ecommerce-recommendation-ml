output "raw_bucket_name" {
  description = "S3 bucket receiving raw streaming events"
  value       = aws_s3_bucket.raw.bucket
}

output "kinesis_stream_name" {
  description = "Kinesis Data Stream receiving application events"
  value       = aws_kinesis_stream.events.name
}

output "kinesis_stream_arn" {
  description = "ARN of the Kinesis Data Stream"
  value       = aws_kinesis_stream.events.arn
}

output "firehose_name" {
  description = "Kinesis Data Firehose delivery stream"
  value       = aws_kinesis_firehose_delivery_stream.events_to_s3.name
}

output "aws_region" {
  description = "AWS region used by the project"
  value       = data.aws_region.current.name
}

output "features_bucket_name" {
  description = "S3 bucket containing ML feature datasets"
  value       = aws_s3_bucket.features.bucket
}

output "sagemaker_model_name" {
  description = "SageMaker recommendation model"
  value       = aws_sagemaker_model.recommender.name
}

output "sagemaker_endpoint_name" {
  description = "SageMaker serverless recommendation endpoint"
  value       = aws_sagemaker_endpoint.recommender.name
}

output "model_artifact_s3_uri" {
  description = "S3 location of the packaged recommendation model"
  value = (
    "s3://${aws_s3_bucket.features.bucket}/models/recommender.tar.gz"
  )
}