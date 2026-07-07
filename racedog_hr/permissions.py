# Copyright (c) 2026, RaceDog Technologies and contributors
"""Row-level scoping for the Employee master — the self-service firewall.

HRMS grants the base ``Employee`` role a broad read on the Employee master, so a
logged-in consultant could otherwise list the whole roster (name, visa, phone of
every colleague). We close that leak here: a *pure consultant* (holds the
``Employee`` role but none of the privileged recruiting/HR roles) is scoped to
their own record via ``user_id``. Everyone privileged is untouched.

This is the correct Frappe mechanism for "see only your own record": the
Employee record's ``owner`` is the HR user who created it, NOT the consultant, so
an ``if_owner`` DocPerm would match nothing. ``user_id`` is the real link.
"""

import frappe

# Roles that legitimately see the whole roster. Anyone holding one of these is
# never restricted to a single record.
PRIVILEGED_ROLES = frozenset(
	{
		"System Manager",
		"Administrator",
		"HR Manager",
		"HR User",
		"Recruiter",
		"Bench Sales",
		"Recruiting Manager",
		"Account Manager",
	}
)


def _is_pure_consultant(user: str) -> bool:
	"""True when the user is a consultant with no roster-wide read privilege."""
	if user in ("Administrator", "Guest"):
		return False
	roles = set(frappe.get_roles(user))
	return "Employee" in roles and not (roles & PRIVILEGED_ROLES)


def employee_query_conditions(user: str | None = None) -> str:
	"""Restrict list/report/get_list on Employee to the caller's own record.

	Returns a SQL WHERE fragment for pure consultants, empty string (no
	restriction) for privileged users. Wired via ``permission_query_conditions``.
	"""
	user = user or frappe.session.user
	if _is_pure_consultant(user):
		return f"`tabEmployee`.`user_id` = {frappe.db.escape(user)}"
	return ""


def employee_has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Guard single-record access so a consultant can't open a colleague by ID.

	Returning ``False`` denies; ``True`` falls through to standard permission
	checks. Only pure consultants are constrained — to their own linked record.
	Wired via ``has_permission``.
	"""
	user = user or frappe.session.user
	if _is_pure_consultant(user):
		return doc.get("user_id") == user
	return True
