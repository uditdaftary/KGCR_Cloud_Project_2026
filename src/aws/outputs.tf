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
