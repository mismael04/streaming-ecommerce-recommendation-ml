# --- Kinesis Throttling Alarm ---
resource "aws_cloudwatch_metric_alarm" "kinesis_throttling" {
  alarm_name          = "${local.name_prefix}-kinesis-throttling"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "WriteProvisionedThroughputExceeded"
  namespace           = "AWS/Kinesis"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  unit                = "Count"

  dimensions = {
    StreamName = aws_kinesis_stream.events.name
  }

  tags = local.common_tags
}

# --- Glue ETL Job Failure Alarm ---
resource "aws_cloudwatch_metric_alarm" "glue_job_failure" {
  alarm_name          = "${local.name_prefix}-glue-job-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "failed"
  namespace           = "AWS/Glue"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  unit                = "Count"

  dimensions = {
    JobName = aws_glue_job.feature_pipeline.name
  }

  tags = local.common_tags
}