# Copyright (c) 2026, RaceDog Technologies and contributors
"""Additive validation on the standard Employee (wired via doc_events).

Encodes the bench-sales rule: Status is *what they're doing*, Hotlist is *how hard
we push*. A billing (Working) consultant is never on the market, so Hotlist locks to
Green; Marketing defaults to Red, On Bench to Orange. (Bill/pay/margin now live on
the separate manager-only Consultant Billing DocType, not on Employee.)
"""

import frappe


def apply_status_rules(doc, method: str | None = None) -> None:
	status = doc.get("deployment_status")

	if status == "Working":
		# On a billing project -> not on the market.
		doc.hotlist = "Green"
	elif not doc.get("hotlist"):
		# Marketing = market hard (Red); On Bench / Rolling-Off default to Orange.
		doc.hotlist = "Red" if status == "Marketing" else "Orange"

	# Only actively-placed states keep a current client (Rolling-Off is still on a
	# project, just ending — so it keeps its client and gets marketed early).
	if status not in ("Working", "Rolling-Off"):
		doc.current_client = None


def link_user_id(doc, method: str | None = None) -> None:
	"""Auto-link a consultant's Employee record to their login (self-service key).

	Every self-scoped feature resolves ``session.user -> Employee`` via ``user_id``,
	so an unlinked record is invisible to its own consultant. If ``user_id`` is
	empty, match an existing (enabled) User by company/personal email and link it.
	Never creates a User — only connects to one that already exists.
	"""
	if doc.get("user_id"):
		return

	for email in (doc.get("company_email"), doc.get("personal_email"), doc.get("prefered_email")):
		if not email:
			continue
		user = frappe.db.get_value("User", {"email": email, "enabled": 1}, "name")
		if user:
			doc.user_id = user
			return
