# Copyright (c) 2026, RaceDog Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

# A submission in one of these statuses is "closed" and no longer blocks a re-submit.
INACTIVE_STATUSES = ("Rejected", "Withdrawn")

# Status changes worth pinging the consultant about (interviews book fast in staffing).
NOTIFY_CONSULTANT_STATUSES = ("Interview Scheduled", "Offer", "Placed")


class Submission(Document):
	"""A consultant (our bench) or an external candidate (middle-vendor) submitted
	to a client requirement.

	Bench submissions are deduped and RTR-checked; external candidates are captured
	inline (no master record) so they can't be double-submitted against the bench.
	When a submission is Placed, its requirement is auto-marked Filled with the right
	"Filled Via" so leadership can see internal-bench vs external placements.
	"""

	def before_insert(self) -> None:
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		if not self.submitted_on:
			self.submitted_on = now_datetime()

	def validate(self) -> None:
		self._block_double_submission()

	def after_insert(self) -> None:
		self._notify_consultant_submitted()

	def on_update(self) -> None:
		self._sync_requirement_on_placed()
		self._notify_consultant_status_change()

	# -- consultant-facing notifications -------------------------------------

	def _consultant_user(self) -> str | None:
		"""The login of the bench consultant on this submission, if any."""
		if self.source != "Bench Consultant" or not self.consultant:
			return None
		return frappe.db.get_value("Employee", self.consultant, "user_id")

	def _requirement_label(self) -> str:
		title = frappe.db.get_value("Client Requirement", self.requirement, "title")
		return title or self.requirement

	def _notify_consultant_submitted(self) -> None:
		user = self._consultant_user()
		if not user:
			return
		# Subject carries the role title only — never the end client or any rate.
		subject = _("You've been submitted for {0}").format(self._requirement_label())
		_notify_consultant(user, subject, self.name)

	def _notify_consultant_status_change(self) -> None:
		if not self.has_value_changed("status") or self.status not in NOTIFY_CONSULTANT_STATUSES:
			return
		user = self._consultant_user()
		if not user:
			return
		templates = {
			"Interview Scheduled": _("Interview scheduled for {0}"),
			"Offer": _("You have an offer on {0}"),
			"Placed": _("You've been placed on {0}"),
		}
		subject = templates[self.status].format(self._requirement_label())
		_notify_consultant(user, subject, self.name)

	def _block_double_submission(self) -> None:
		"""Reject a second active submission for the same bench consultant + requirement."""
		if self.status in INACTIVE_STATUSES:
			return
		if self.source != "Bench Consultant" or not self.consultant:
			# External candidates belong to another employer; nothing to dedupe.
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

	def _sync_requirement_on_placed(self) -> None:
		"""When a submission is Placed, mark its requirement Filled + record the source."""
		if self.status != "Placed" or not self.requirement:
			return

		req_status, filled_via = frappe.db.get_value(
			"Client Requirement", self.requirement, ["status", "filled_via"]
		)
		if req_status == "Filled":
			return

		req = frappe.get_doc("Client Requirement", self.requirement)
		req.status = "Filled"
		req.filled_via = (
			"Internal Bench" if self.source == "Bench Consultant" else "External Candidate"
		)
		if not req.closed_reason:
			req.closed_reason = _("Placed via submission {0}").format(self.name)
		req.save(ignore_permissions=True)


def _notify_consultant(user: str, subject: str, submission: str) -> None:
	"""Best-effort in-app alert to a consultant about their own submission."""
	from racedog_hr.tasks import _notify

	_notify({user}, subject, "Submission", submission)


def assign_followup(doc, method: str | None = None) -> None:
	"""Assign an interview follow-up ToDo to the submitter when one is scheduled.

	Wired via ``doc_events`` (after_insert / on_update). Idempotent.
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

	candidate = doc.consultant if doc.source == "Bench Consultant" else doc.external_name
	try:
		add_assignment(
			{
				"assign_to": [doc.submitted_by],
				"doctype": "Submission",
				"name": doc.name,
				"description": _("Interview scheduled for {0} — prep and follow up.").format(
					candidate or doc.name
				),
				"date": getdate(doc.interview_datetime) if doc.interview_datetime else None,
			}
		)
	except frappe.exceptions.DuplicateEntryError:
		pass
