# Run-artifact bucket and contested-run topic: the AWS targets of the two
# interfaces in src/backend/kgcr/orchestration/aws.py (S3ArtifactStore,
# SnsNotifier). Applied in Account C (shared-security) alongside the analysis
# platform. Free-tier shaped: kilobyte-sized JSON and Markdown per run, expired
# after a short retention window; a handful of SNS publishes per day.
#
# Status: authored, not applied, and not yet run through `terraform validate`
# (Terraform is not installed where this was written). See README.md.

resource "aws_s3_bucket" "runs" {
  bucket_prefix = "kgcr-runs-"
  tags          = var.tags
}

resource "aws_s3_bucket_public_access_block" "runs" {
  bucket                  = aws_s3_bucket.runs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "runs" {
  bucket = aws_s3_bucket.runs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Run records are reproducible from (spec hash, graph version, model version,
# seed), so old artifacts can expire rather than accumulate storage cost.
resource "aws_s3_bucket_lifecycle_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    id     = "expire-run-artifacts"
    status = "Enabled"
    filter {}
    expiration {
      days = var.run_artifact_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = var.run_artifact_retention_days
    }
  }
}

data "aws_iam_policy_document" "runs_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.runs.arn,
      "${aws_s3_bucket.runs.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "runs" {
  bucket = aws_s3_bucket.runs.id
  policy = data.aws_iam_policy_document.runs_tls_only.json
}

resource "aws_sns_topic" "contested_runs" {
  name              = "kgcr-contested-runs"
  kms_master_key_id = "alias/aws/sns" # AWS-managed key: no monthly key charge
  tags              = var.tags
}

# Email subscriptions stay pending until the recipient confirms them.
resource "aws_sns_topic_subscription" "contested_runs_email" {
  topic_arn = aws_sns_topic.contested_runs.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Least privilege for whatever runs `kgcr review` against AWS: write run
# artifacts under runs/ and publish to the one topic. Nothing else. Attaching it
# to a runtime role is a Phase-II step, so it is exported rather than attached.
data "aws_iam_policy_document" "pipeline_publish" {
  statement {
    sid       = "PutRunArtifacts"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.runs.arn}/runs/*"]
  }
  statement {
    sid       = "PublishContestedRuns"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.contested_runs.arn]
  }
}

resource "aws_iam_policy" "pipeline_publish" {
  name        = "KGCRPipelinePublish"
  description = "Write kgcr run artifacts and publish contested-run notifications."
  policy      = data.aws_iam_policy_document.pipeline_publish.json
  tags        = var.tags
}
