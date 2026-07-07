# Copyright (c) 2026, RaceDog Technologies and contributors
"""Grant recruiting roles the right access to the Employee master.

The rate/margin fields on Employee live at permlevel 1, so only manager roles get
level-1 access; recruiters get level-0 read/write (bench fields) but never see the
rate section. Idempotent — safe to re-run on every `bench migrate`.
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

RECRUITING_ROLES = ("Recruiter", "Bench Sales", "Recruiting Manager", "Account Manager")

# (role, permlevel, [ptypes]) grants applied to the standard Employee DocType.
EMPLOYEE_GRANTS = (
	("Recruiter", 0, ("read", "write")),
	("Bench Sales", 0, ("read", "write")),
	# The manager owns the consultant master — full CRUD, incl. create + delete.
	("Recruiting Manager", 0, ("read", "write", "create", "delete")),
	("Recruiting Manager", 1, ("read", "write")),
	("Account Manager", 0, ("read",)),
	("Account Manager", 1, ("read",)),
	("HR Manager", 1, ("read", "write")),
)


def execute() -> None:
	_ensure_roles_exist()
	for role, permlevel, ptypes in EMPLOYEE_GRANTS:
		_ensure_permission("Employee", role, permlevel, ptypes)
	# HRMS's Employee form reads the HR Settings singleton; without read the
	# recruiting roles get a "No permission for HR Settings" popup on every open.
	for role in RECRUITING_ROLES:
		_ensure_permission("HR Settings", role, 0, ("read",))
	frappe.clear_cache(doctype="Employee")
	frappe.clear_cache(doctype="HR Settings")


def _ensure_roles_exist() -> None:
	for role in RECRUITING_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc(
				{"doctype": "Role", "role_name": role, "desk_access": 1}
			).insert(ignore_permissions=True)


def _ensure_permission(doctype: str, role: str, permlevel: int, ptypes: tuple[str, ...]) -> None:
	if not frappe.db.exists("Role", role):
		# e.g. HR Manager only exists once HRMS is installed; skip quietly otherwise.
		return

	has_row = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": doctype, "role": role, "permlevel": permlevel},
		limit=1,
	)
	if not has_row:
		add_permission(doctype, role, permlevel)

	for ptype in ptypes:
		update_permission_property(doctype, role, permlevel, ptype, 1, validate=False)
