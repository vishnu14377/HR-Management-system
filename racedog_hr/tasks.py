# Copyright (c) 2026, RaceDog Technologies and contributors
"""Daily scheduled jobs for racedog_hr (wired in hooks.scheduler_events)."""

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.utils import add_months, date_diff, getdate

# Day-counts before work-auth expiry at which we alert. Firing only on these exact
# thresholds (rather than every day inside a window) keeps the bell from spamming.
VISA_ALERT_THRESHOLDS = (90, 60, 30, 14, 7, 1)

# Consultant states that mean "market me" — used for the availability alert.
MARKETABLE_STATUSES = ("On Bench", "Rolling-Off", "Marketing")

# Days of the month on which to nudge consultants who haven't uploaded the prior
# month's timesheet yet (a few escalating pokes, not a daily nag).
TIMESHEET_REMINDER_DAYS = (3, 6, 9)

_SYSTEM_USERS = frozenset({"Administrator", "Guest"})


def check_visa_expiry() -> None:
	"""Alert HR + the marketing owner when a consultant's work auth nears expiry."""
	today = getdate()
	hr_managers = _users_with_role("HR Manager")

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "visa_expiry": ["is", "set"]},
		fields=["name", "employee_name", "visa_expiry", "marketing_owner", "user_id"],
	)
	for emp in employees:
		days_left = date_diff(emp.visa_expiry, today)
		if days_left not in VISA_ALERT_THRESHOLDS:
			continue

		subject = _("Work authorization for {0} expires in {1} day(s)").format(
			emp.employee_name, days_left
		)
		recipients = set(hr_managers)
		if emp.marketing_owner:
			recipients.add(emp.marketing_owner)
		# The consultant is the one who renews it — tell them directly too.
		if emp.user_id:
			recipients.add(emp.user_id)
		_notify(recipients, subject, "Employee", emp.name)


def check_bench_availability() -> None:
	"""Alert bench-sales + the marketing owner the day a consultant becomes free."""
	today = getdate()
	bench_sales = _users_with_role("Bench Sales")

	employees = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"availability_date": today,
			"deployment_status": ["in", MARKETABLE_STATUSES],
		},
		fields=["name", "employee_name", "marketing_owner"],
	)
	for emp in employees:
		subject = _("{0} is now available for placement").format(emp.employee_name)
		recipients = set(bench_sales)
		if emp.marketing_owner:
			recipients.add(emp.marketing_owner)
		_notify(recipients, subject, "Employee", emp.name)


def check_timesheet_reminders() -> None:
	"""Nudge deployed consultants who haven't uploaded last month's timesheet.

	Only the currently-deployed (Working, with a client) owe a timesheet; bench
	consultants are excluded. Fires on a few days early in the month, not daily.
	"""
	today = getdate()
	if today.day not in TIMESHEET_REMINDER_DAYS:
		return

	prior = getdate(add_months(today.replace(day=1), -1)).strftime("%Y-%m")
	employees = frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"deployment_status": "Working",
			"current_client": ["is", "set"],
		},
		fields=["name", "employee_name", "user_id"],
	)
	for emp in employees:
		if not emp.user_id:
			continue
		if frappe.db.exists("Consultant Timesheet", {"consultant": emp.name, "period_month": prior}):
			continue
		subject = _("Reminder: upload your {0} timesheet").format(prior)
		_notify({emp.user_id}, subject, "Employee", emp.name)


def _users_with_role(role: str) -> list[str]:
	if not frappe.db.exists("Role", role):
		return []
	return frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		pluck="parent",
	)


def _notify(recipients: Iterable[str], subject: str, doctype: str, docname: str) -> None:
	"""Drop an in-app (bell) alert for each real recipient. Best-effort."""
	for user in {r for r in recipients if r and r not in _SYSTEM_USERS}:
		try:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": subject,
					"email_content": subject,
					"document_type": doctype,
					"document_name": docname,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(f"racedog_hr: failed to notify {user}", "racedog_hr notify")
