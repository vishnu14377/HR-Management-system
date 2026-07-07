# Copyright (c) 2026, RaceDog Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

# A submission in one of these statuses is "closed" and no longer blocks a re-submit.
INACTIVE_STATUSES = ("Rejected", "Withdrawn")


class Submission(Document):
	"""Tracks a consultant submitted to a client requirement through a vendor.

	The core value is preventing the two most damaging coordination failures:
	  * double-submitting the same consultant to the same requirement, and
	  * a right-to-represent (RTR) collision — the same consultant active with the
	    same end client through a different requirement/vendor.
	"""

	def before_insert(self) -> None:
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		if not self.submitted_on:
			self.submitted_on = now_datetime()

	def validate(self) -> None:
		self._block_double_submission()

	def _block_double_submission(self) -> None:
		"""Reject a second active submission for the same consultant + requirement."""
		if self.status in INACTIVE_STATUSES:
			return

		duplicate = frappe.db.exists(
			"Submission",
			{
				"consultant": self.consultant,
				"requirement": self.requirement,
				"name": ["!=", self.name or ""],
				"status": ["not in", INACTIVE_STATUSES],
			},
		)
		if duplicate:
			frappe.throw(
				_("{0} is already actively submitted to this requirement (see {1}).").format(
					frappe.bold(self.consultant), frappe.bold(duplicate)
				),
				title=_("Duplicate Submission"),
			)

		self._warn_right_to_represent()

	def _warn_right_to_represent(self) -> None:
		"""Non-blocking heads-up: same consultant already active with this client."""
		if not self.client:
			return

		conflict = frappe.get_all(
			"Submission",
			filters={
				"consultant": self.consultant,
				"client": self.client,
				"requirement": ["!=", self.requirement],
				"status": ["not in", INACTIVE_STATUSES],
				"name": ["!=", self.name or ""],
			},
			fields=["name", "requirement"],
			limit=1,
		)
		if conflict:
			frappe.msgprint(
				_(
					"Possible RTR conflict: {0} is already active with {1} on {2}. "
					"Confirm right-to-represent before submitting."
				).format(
					frappe.bold(self.consultant),
					frappe.bold(self.client),
					frappe.bold(conflict[0].requirement),
				),
				title=_("Right-to-Represent Check"),
				indicator="orange",
			)


def assign_followup(doc, method: str | None = None) -> None:
	"""Assign an interview follow-up ToDo to the submitter when one is scheduled.

	Wired via ``doc_events`` (after_insert / on_update). Idempotent — it will not
	create a second open ToDo for the same submission + assignee.
	"""
	if doc.status != "Interview Scheduled" or not doc.submitted_by:
		return

	already_assigned = frappe.db.exists(
		"ToDo",
		{
			"reference_type": "Submission",
			"reference_name": doc.name,
			"allocated_to": doc.submitted_by,
			"status": "Open",
		},
	)
	if already_assigned:
		return

	from frappe.desk.form.assign_to import add as add_assignment

	try:
		add_assignment(
			{
				"assign_to": [doc.submitted_by],
				"doctype": "Submission",
				"name": doc.name,
				"description": _("Interview scheduled for {0} — prep and follow up.").format(
					doc.consultant
				),
				"date": getdate(doc.interview_datetime) if doc.interview_datetime else None,
			}
		)
	except frappe.exceptions.DuplicateEntryError:
		# A concurrent save already created the assignment; safe to ignore.
		pass
