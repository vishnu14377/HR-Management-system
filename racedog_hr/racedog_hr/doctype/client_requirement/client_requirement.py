# Copyright (c) 2026, RaceDog Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Statuses that mean the requirement is no longer being actively worked.
CLOSED_STATUSES = ("Filled", "Closed")
ACTIVE_STATUSES = ("Open", "On-Hold")


class ClientRequirement(Document):
	"""An open client position recruiters post and soft-close when filled.

	We never hard-delete a filled requirement: closing sets ``status`` and stamps
	``closed_on`` so it drops off the Open board while preserving fill-rate and
	cycle-time history for later reporting.
	"""

	def before_insert(self) -> None:
		if not self.posted_by:
			self.posted_by = frappe.session.user
		if not self.posted_on:
			self.posted_on = now_datetime()

	def validate(self) -> None:
		self._sync_primary_skill()
		self._handle_closure()

	def _sync_primary_skill(self) -> None:
		"""Denormalize the first tagged skill so list/report filters stay fast."""
		if self.primary_skill or not self.skills:
			return
		self.primary_skill = self.skills[0].skill

	def _handle_closure(self) -> None:
		"""Stamp closure metadata on soft-close; clear it when reopened."""
		if self.status in CLOSED_STATUSES:
			if not self.closed_on:
				self.closed_on = now_datetime()
			if self.status == "Closed" and not self.closed_reason:
				frappe.throw(
					_("Please add a Closure Reason when closing a requirement."),
					title=_("Closure Reason Required"),
				)
			if self.status == "Filled" and not self.closed_reason:
				self.closed_reason = _("Position filled")
		elif self.status in ACTIVE_STATUSES:
			# Reopened: drop the stale closure stamp so it returns to the Open board.
			self.closed_on = None
			self.closed_reason = None
