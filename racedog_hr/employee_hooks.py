# Copyright (c) 2026, RaceDog Technologies and contributors
"""Additive validation on the standard Employee (wired via doc_events).

Encodes the bench-sales rule: Status is *what they're doing*, Hotlist is *how hard
we push*. A billing (Working) consultant is never on the market, so Hotlist locks to
Green; Marketing defaults to Red, On Bench to Orange. Margin is derived from the
manager-only rates.
"""

import frappe
from frappe.utils import flt


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

	# Margin is a manager-only computed number (server bypasses permlevel).
	doc.margin = flt(doc.get("current_bill_rate")) - flt(doc.get("current_pay_rate"))
