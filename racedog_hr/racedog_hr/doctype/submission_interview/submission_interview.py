# Copyright (c) 2026, RaceDog Technologies and contributors
"""One interview round on a Submission (child table).

Tracks the multi-round interview loop per submission — round number, type, date,
outcome — plus the client feedback / weak areas the recruiter records. The feedback
fields are recruiter/manager-only and must NEVER surface to the candidate (served
through the recruiter-facing pipeline API, never the consultant self-service one).
"""

from frappe.model.document import Document


class SubmissionInterview(Document):
	pass
