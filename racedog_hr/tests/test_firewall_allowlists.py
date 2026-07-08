# Copyright (c) 2026, RaceDog Technologies and contributors
"""Guardrail tests for the rate/margin firewall.

These lock the project's #1 invariant in place: rate/margin fields must never be
self-writable by a consultant, never appear in a consultant-facing or board read,
and never be writable from the recruiter board. The self-service write path saves
with ``ignore_permissions=True`` (so hooks run), which is safe ONLY because the
allowlists below are airtight — so if a future edit drifts a sensitive field into
one of them, this test fails loudly BEFORE it can leak.

Pure-logic (no DB), so it runs under `bench run-tests --app racedog_hr` or as a
plain `python -m unittest`.
"""

import unittest

from racedog_hr import api

# Any field whose name carries a rate, or the computed margin, is commercial and
# manager-only. It must never appear in a non-manager read or any self/board write.
RATE_LIKE = ("rate", "margin")

# Fields a consultant must never be able to self-write (pipeline / commercial control).
FORBIDDEN_SELF_WRITE = frozenset(
	{
		"deployment_status",
		"hotlist",
		"current_client",
		"marketing_owner",
		"current_bill_rate",
		"current_pay_rate",
		"margin",
		"submitted_bill_rate",
	}
)


def _rate_like(fields) -> list:
	return [f for f in fields if any(tok in f for tok in RATE_LIKE)]


class TestFirewallAllowlists(unittest.TestCase):
	def test_self_update_excludes_privileged_fields(self):
		leaked = api.SELF_UPDATABLE_FIELDS & FORBIDDEN_SELF_WRITE
		self.assertEqual(leaked, set(), f"SELF_UPDATABLE_FIELDS leaks privileged fields: {leaked}")

	def test_self_update_excludes_any_rate_field(self):
		self.assertEqual(_rate_like(api.SELF_UPDATABLE_FIELDS), [])

	def test_my_profile_read_has_no_rate_fields(self):
		self.assertEqual(_rate_like(api.MY_PROFILE_FIELDS), [])

	def test_my_submissions_read_excludes_bill_rate(self):
		self.assertNotIn("submitted_bill_rate", api.SUBMISSION_SAFE_FIELDS)
		self.assertEqual(_rate_like(api.SUBMISSION_SAFE_FIELDS), [])

	def test_board_read_has_no_rate_fields(self):
		self.assertEqual(_rate_like(api.BENCH_FIELDS), [])
		self.assertEqual(_rate_like(api.REQUIREMENT_FIELDS), [])

	def test_recruiter_board_write_excludes_rate_fields(self):
		# Recruiters may set status/hotlist/client on the board, but NEVER a rate.
		self.assertEqual(_rate_like(api.UPDATABLE_BENCH_FIELDS), [])

	def test_timesheet_read_has_no_rate_fields(self):
		# The monthly timesheet surface must never carry a dollar/rate/margin field.
		self.assertEqual(_rate_like(api.TIMESHEET_SAFE_FIELDS), [])
		self.assertNotIn("total_amount", api.TIMESHEET_SAFE_FIELDS)

	def test_privileged_roles_gate_is_non_empty(self):
		# A defensive empty gate would let anyone through the row-scope check.
		from racedog_hr import permissions

		self.assertIn("System Manager", permissions.PRIVILEGED_ROLES)
		self.assertIn("Recruiting Manager", permissions.PRIVILEGED_ROLES)
		self.assertNotIn("Employee", permissions.PRIVILEGED_ROLES)


if __name__ == "__main__":
	unittest.main()
