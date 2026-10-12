output "harvest_role_arn" {
  description = "ARN of KGCRHarvestReadOnly — the role Account C assumes for every review run."
  value       = aws_iam_role.harvest_read_only.arn
}

output "provision_role_arn" {
  description = "ARN of KGCRProvisionApply when enabled, else null (demo window only)."
  value       = var.enable_provision_role ? aws_iam_role.provision_apply[0].arn : null
}

output "budget_names" {
  description = "Names of the budget alarms created in this account (FD-08 §6)."
  value       = [for b in aws_budgets_budget.cost : b.name]
}

output "run_bucket_name" {
  description = "S3 bucket for kgcr run artifacts: pass as `kgcr review --s3-bucket`."
  value       = aws_s3_bucket.runs.bucket
}

output "contested_runs_topic_arn" {
  description = "SNS topic for contested runs: pass as `kgcr review --sns-topic-arn`."
  value       = aws_sns_topic.contested_runs.arn
}

output "pipeline_publish_policy_arn" {
  description = "Least-privilege policy for the process that runs kgcr review against AWS."
  value       = aws_iam_policy.pipeline_publish.arn
}
