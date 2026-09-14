# Cross-account roles (FD-08 §4). Applied in Accounts A and B; both trust the
# Account C principal by ARN plus an external ID — no AWS Organization required.
#
# INV-5 (FD-01, FD-08 §4.1) holds *by construction*: the harvest role is granted
# only read policies and contains zero write actions, so Agent 2 cannot write
# even if compromised. The provision role (Account A only) is applied separately
# and enabled only during the demo window.

# --- Harvest role: read-only, every review run -------------------------------

data "aws_iam_policy_document" "harvest_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.security_account_principal_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.harvest_external_id]
    }
  }
}

resource "aws_iam_role" "harvest_read_only" {
  name                 = "KGCRHarvestReadOnly"
  assume_role_policy   = data.aws_iam_policy_document.harvest_trust.json
  max_session_duration = 3600
  tags                 = var.tags
}

# AWS-managed read policies (FD-08 §4.1): SecurityAudit + ViewOnlyAccess.
# Deliberately no inline write statements — the zero-write property is the
# load-bearing control.
resource "aws_iam_role_policy_attachment" "harvest_security_audit" {
  role       = aws_iam_role.harvest_read_only.name
  policy_arn = "arn:aws:iam::aws:policy/SecurityAudit"
}

resource "aws_iam_role_policy_attachment" "harvest_view_only" {
  role       = aws_iam_role.harvest_read_only.name
  policy_arn = "arn:aws:iam::aws:policy/job-function/ViewOnlyAccess"
}

# --- Provision role: write path, Account A only, demo window only ------------
# Guarded by var.enable_provision_role so it is absent until a demo is imminent,
# and scoped to var.provision_resource_types (empty grants nothing).

variable "enable_provision_role" {
  description = "Create KGCRProvisionApply. Keep false outside the demo window (FD-08 §4.1, §6)."
  type        = bool
  default     = false
}

data "aws_iam_policy_document" "provision_trust" {
  count = var.enable_provision_role ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.security_account_principal_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.provision_external_id]
    }
  }
}

resource "aws_iam_role" "provision_apply" {
  count = var.enable_provision_role ? 1 : 0

  name                 = "KGCRProvisionApply"
  assume_role_policy   = data.aws_iam_policy_document.provision_trust[0].json
  max_session_duration = 3600
  tags                 = var.tags
}

# The write grant is intentionally minimal and data-driven. With an empty
# provision_resource_types the role can assume but do nothing — the "wired, not
# yet exercised" state the Phase 0 exit gate requires (FD-08 §10 item 4).
data "aws_iam_policy_document" "provision_permissions" {
  count = var.enable_provision_role && length(var.provision_resource_types) > 0 ? 1 : 0

  statement {
    effect    = "Allow"
    actions   = ["ec2:*", "s3:*", "iam:PassRole"]
    resources = var.provision_resource_types
  }
}

resource "aws_iam_role_policy" "provision_permissions" {
  count = var.enable_provision_role && length(var.provision_resource_types) > 0 ? 1 : 0

  name   = "kgcr-provision-scope"
  role   = aws_iam_role.provision_apply[0].id
  policy = data.aws_iam_policy_document.provision_permissions[0].json
}
