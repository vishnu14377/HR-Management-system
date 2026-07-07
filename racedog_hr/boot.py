# Copyright (c) 2026, RaceDog Technologies and contributors
"""Boot-time overrides (wired via the ``extend_bootinfo`` hook)."""

import frappe


def boot_session(bootinfo) -> None:
	"""Land pure consultants on their self-service portal instead of a blank page.

	Frappe's ``boot.add_home_page`` reads the *global* ``desktop:home_page``
	(= ``bench-board``). A consultant can't access the recruiter board, so that
	resolution 403s and falls back to ``"Workspaces"`` — and since a consultant
	has no workspace, the desk lands them on the empty Welcome Workspace (the
	"blank screen"). Neither ``Role.home_page`` nor a per-user default overrides
	this (boot reads the global one). Overriding ``bootinfo.home_page`` here does:
	the empty ``/app`` route renders whatever page ``home_page`` names.
	"""
	from racedog_hr.permissions import _is_pure_consultant

	if not _is_pure_consultant(frappe.session.user):
		return
	# Only if the portal exists and the consultant may see it.
	if not frappe.db.exists("Page", "consultant-home"):
		return
	try:
		if frappe.get_doc("Page", "consultant-home").is_permitted():
			bootinfo.home_page = "consultant-home"
	except frappe.PermissionError:
		frappe.clear_last_message()
