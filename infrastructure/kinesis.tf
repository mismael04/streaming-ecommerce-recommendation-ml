resource "aws_kinesis_stream" "events" {
  name             = "${local.name_prefix}-events"
  shard_count      = 8
  retention_period = 24

  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis"

  shard_level_metrics = [
    "IncomingBytes",
    "IncomingRecords",
    "OutgoingBytes",
    "OutgoingRecords",
  ]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-events"
  })
}