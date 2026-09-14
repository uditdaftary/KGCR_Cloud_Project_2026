# Budget alarms — "the single most important line in this document" (FD-08 §6).
# Created by IaC so they cannot be forgotten (FD-08 §8). Applied per account on
# day one, before any live-account work.
#
# Each threshold becomes a cost budget that emails var.alert_email when actual
# spend crosses it. Applying this stack in each of the three accounts satisfies
# the "alarms live on every account" half of the Phase 0 exit gate (FD-08 §10);
# the "verified by a test breach" half is a manual step, not IaC.

resource "aws_budgets_budget" "cost" {
  for_each = { for t in var.budget_thresholds_usd : tostring(t) => t }

  name         = "kgcr-budget-${each.key}usd"
  budget_type  = "COST"
  limit_amount = tostring(each.value)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Notify on both forecasted and actual breaches: forecast catches a runaway
  # always-on service before the month closes, actual is the hard signal.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
