# Copyright (c) 2026, RaceDog Technologies and contributors
"""Confidential consultant billing — bill/pay/margin, manager-roles-only.

Kept in its OWN DocType (not permlevel-1 fields on Employee) because Frappe's
permlevel firewall strips sensitive fields from query *output* but still lets a
non-privileged user place them in WHERE / ORDER BY (recovering exact values by
binary search, or the ranking via order-by). A separate DocType that only manager
roles can access at the doctype level removes the field from every surface a
recruiter/consultant/HR can query at all — closing that side-channel.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ConsultantBilling(Document):
	def validate(self) -> None:
		self.margin = flt(self.bill_rate) - flt(self.pay_rate)
