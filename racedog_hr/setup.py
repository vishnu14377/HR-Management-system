# Copyright (c) 2026, RaceDog Technologies and contributors
"""Self-healing install/migrate setup.

Runs AFTER fixtures on every install/migrate (idempotent): applies permissions +
indexes, remaps legacy status values, surfaces dashboard columns, and de-bloats the
ERPNext surface down to what an IT-outsourcing recruiting team actually uses.
"""

import frappe

from racedog_hr.patches.v0_0_1.add_indexes import execute as _add_indexes
from racedog_hr.patches.v0_0_1.setup_roles_and_permissions import execute as _setup_permissions

RECRUITING_ROLES = ("Recruiter", "Bench Sales", "Recruiting Manager", "Account Manager")

# Old deployment_status values -> new (Working / On Bench / Marketing).
STATUS_REMAP = {
	"Billing": "Working",
	"Placed": "Working",
	"Interviewing": "Marketing",
	"Rolling-Off": "Marketing",
	"Do-Not-Market": "On Bench",
}

# ERPNext/HRMS workspaces a pure IT-outsourcing firm never uses — hidden globally.
HIDE_WORKSPACES = (
	"Manufacturing", "Stock", "Selling", "Buying", "Assets", "Quality", "Projects",
	"CRM", "Support", "Loans", "Loan", "Payables", "Receivables", "Point of Sale",
	"Retail", "Telephony", "Education", "Healthcare", "Agriculture", "Non Profit",
	"Hospitality", "ERPNext Integrations", "Payroll", "Shift & Attendance",
	"Performance", "Leaves", "Expense Claims",
)

# Native Employee fields to surface in the list view (dashboard columns).
LIST_FIELDS = ("company_email", "cell_number")

# Our workspace — the one thing recruiters/managers should see.
OUR_WORKSPACE = "Bench & Requirements"
TEAM_ROLES = ("System Manager", "HR Manager", *RECRUITING_ROLES)


def after_install() -> None:
	_apply()


def after_migrate() -> None:
	_apply()


def _apply() -> None:
	_setup_permissions()
	_add_indexes()
	_migrate_status()
	_surface_list_fields()
	_debloat()
	frappe.db.commit()
	frappe.clear_cache()


def _migrate_status() -> None:
	"""Remap any legacy deployment_status values to the new three-state model."""
	if not frappe.db.has_column("Employee", "deployment_status"):
		return
	for old, new in STATUS_REMAP.items():
		frappe.db.sql(
			"update `tabEmployee` set deployment_status=%s where deployment_status=%s",
			(new, old),
		)


def _surface_list_fields() -> None:
	"""Show email + phone in the native Employee list (upgrade-safe Property Setters)."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for field in LIST_FIELDS:
		try:
			make_property_setter(
				"Employee", field, "in_list_view", 1, "Check", validate_fields_for_doctype=False
			)
		except Exception:
			frappe.log_error(f"racedog_hr: could not surface Employee.{field}", "racedog_hr setup")


def _debloat() -> None:
	"""Give the recruiting team a single-workspace experience.

	Never-used modules are hidden globally; every other standard workspace is
	restricted to admins, so recruiters/managers see ONLY our workspace and land
	on it. Idempotent and self-healing (re-applied every migrate).
	"""
	for ws in HIDE_WORKSPACES:
		if frappe.db.exists("Workspace", ws):
			frappe.db.set_value("Workspace", ws, "is_hidden", 1)

	# Restrict every other public workspace to admins.
	for ws in frappe.get_all("Workspace", filters={"public": 1}, pluck="name"):
		if ws == OUR_WORKSPACE:
			continue
		if not frappe.db.exists("Has Role", {"parent": ws, "parenttype": "Workspace"}):
			_add_workspace_role(ws, "System Manager")

	# Make sure the whole team can see our workspace.
	for role in TEAM_ROLES:
		_add_workspace_role(OUR_WORKSPACE, role)

	# Land recruiting roles on the board.
	for role in RECRUITING_ROLES:
		if frappe.db.exists("Role", role):
			frappe.db.set_value("Role", role, "home_page", "app/bench-board")


def _add_workspace_role(workspace: str, role: str) -> None:
	if not frappe.db.exists("Workspace", workspace) or not frappe.db.exists("Role", role):
		return
	if frappe.db.exists("Has Role", {"parent": workspace, "parenttype": "Workspace", "role": role}):
		return
	doc = frappe.get_doc("Workspace", workspace)
	doc.append("roles", {"role": role})
	doc.save(ignore_permissions=True)
