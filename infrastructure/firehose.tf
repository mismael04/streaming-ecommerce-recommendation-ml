resource "aws_kinesis_firehose_delivery_stream" "events_to_s3" {
  name        = "${local.name_prefix}-firehose"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.events.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose.arn
    bucket_arn = aws_s3_bucket.raw.arn

    prefix = "events/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"

    error_output_prefix = "errors/"

    # Buffer for up to 128 MB or 15 minutes,
    # whichever condition triggers delivery first.
    buffering_size     = 128
    buffering_interval = 900

    compression_format = "GZIP"

    # Separate JSON records with newline delimiters
    # so Spark and Athena can read them as JSON Lines.
    processing_configuration {
      enabled = true

      processors {
        type = "AppendDelimiterToRecord"

        parameters {
          parameter_name  = "Delimiter"
          parameter_value = "\\n"
        }
      }
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = "/aws/kinesisfirehose/${local.name_prefix}"
      log_stream_name = "S3Delivery"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-firehose"
  })
}
