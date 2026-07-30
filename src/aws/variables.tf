# Inputs to the Phase 0 bootstrap (FD-08 §8). Account IDs and external IDs are
# variables, never hard-committed (FD-08 §8, §9): the environment is
# standable-from-scratch and holds no secrets in code.

variable "region" {
  description = "Single region for the estate (FD-08 §11: single region is the default)."
  type        = string
  default     = "eu-west-1"
}

variable "alert_email" {
  description = "Email address that budget alarms notify (FD-08 §6)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "budget_thresholds_usd" {
  description = "Budget alarm thresholds in USD (FD-08 §6: $5 / $15 / $30, day one)."
  type        = list(number)
  default     = [5, 15, 30]

  validation {
    condition     = length(var.budget_thresholds_usd) > 0
    error_message = "Provide at least one budget threshold."
  }
}

variable "security_account_principal_arn" {
  description = <<-EOT
    ARN of the principal in Account C (shared-security) that the harvest and
    provision roles trust (FD-08 §4). Cross-account trust names this principal
    directly rather than relying on an AWS Organization.
  EOT
  type        = string
}

variable "harvest_external_id" {
  description = "External ID on the harvest role's trust policy (FD-08 §4, §9: confused-deputy defence)."
  type        = string
  sensitive   = true
}

variable "provision_external_id" {
  description = "External ID on the provision role's trust policy (FD-08 §4, §9)."
  type        = string
  sensitive   = true
}

variable "provision_resource_types" {
  description = <<-EOT
    Resource-type ARN patterns the KGCRProvisionApply role may write, scoped
    to what the corpus/demo provisions (FD-08 §4.1). Empty by default: the
    write path is wired but grants nothing until a demo scope is supplied.
  EOT
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource, for the weekly cost sweep (FD-08 §6)."
  type        = map(string)
  default = {
    project = "kgcr"
    phase   = "P0"
  }
}
