# Copyright (c) 2026, RaceDog Technologies and contributors
# For license information, please see license.txt
"""A consultant's monthly client-signed timesheet (a PDF), reviewed by HR.

Deliberately minimal and firewall-clean: it holds the signed PDF + period + status
and NO dollar/rate field of any kind (the rate firewall never touches this surface).
It is NOT the HRMS Timesheet — there is no hour-to-money arithmetic here. One row
per (consultant, period_month), enforced by the ``format:`` autoname.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Billing month, e.g. "2026-07".
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ConsultantTimesheet(Document):
	def validate(self) -> None:
		if not PERIOD_RE.match(self.period_month or ""):
			frappe.throw(_("Period must be in YYYY-MM format (e.g. 2026-07)."))
		if not self.submitted_on:
			self.submitted_on = now_datetime()
		# Stamp the client from the consultant's current placement (read-only,
		# non-rate field) so HR can slice compliance per client.
		if self.consultant and not self.client:
			self.client = frappe.db.get_value("Employee", self.consultant, "current_client")
