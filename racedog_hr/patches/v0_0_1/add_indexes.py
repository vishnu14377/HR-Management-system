# Copyright (c) 2026, RaceDog Technologies and contributors
"""Add DB indexes that back the bench-list filters and the dedupe lookup.

Single-column indexes come from ``search_index`` in the DocType JSON; this patch
adds the composite index the double-submission check relies on, plus indexes on
the Employee bench columns (custom fields don't carry ``search_index``).
Idempotent — ``add_index`` is a no-op if the index already exists.
"""

import frappe


def execute() -> None:
	# Composite index for the (consultant, requirement) double-submission lookup.
	frappe.db.add_index("Submission", ["consultant", "requirement"], index_name="consultant_requirement")

	# Bench-list filter columns on the Employee master.
	for column in ("deployment_status", "availability_date", "primary_skill", "visa_status", "visa_expiry"):
		try:
			frappe.db.add_index("Employee", [column])
		except Exception:
			# Column may be absent on a partially-migrated site; the fixture sync
			# that creates it runs in the same migrate, so a later run will index it.
			frappe.log_error(f"racedog_hr: could not index Employee.{column}", "racedog_hr add_indexes")
