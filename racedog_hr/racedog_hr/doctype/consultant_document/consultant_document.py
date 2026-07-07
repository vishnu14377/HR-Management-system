# Copyright (c) 2026, RaceDog Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ConsultantDocument(Document):
	"""A typed document (resume, visa, DL, ...) attached to a consultant.

	The file attaches to the parent Employee, so any user with read on that
	Employee can download it — which is what lets recruiters pull resumes.
	"""

	pass
