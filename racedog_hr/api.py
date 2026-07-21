# Copyright (c) 2026, RaceDog Technologies and contributors
"""Whitelisted JSON API for the Bench Board (Desk page + any future SPA).

Reads go through ``frappe.get_list`` with an explicit non-rate field allowlist,
so rate/margin can never leak even if the caller has level-1 access. The write
path is field-allowlisted and role-gated, then saves with ``ignore_permissions``
so it stays safe under either permission model. Every response uses a
``{"data": ..., "meta": ...}`` envelope.
"""

import frappe
from frappe import _

RECRUITING_ROLES = frozenset(
	{"Recruiter", "Bench Sales", "Recruiting Manager", "Account Manager", "HR Manager", "System Manager"}
)

# The ONLY Employee fields a board read returns — deliberately no rate/PII-heavy columns.
BENCH_FIELDS = (
	"name",
	"employee_name",
	"designation",
	"department",
	"image",
	"deployment_status",
	"hotlist",
	"current_client",
	"primary_skill",
	"visa_status",
	"visa_expiry",
	"availability_date",
	"bench_start_date",
	"marketing_owner",
	"company_email",
	"personal_email",
	"cell_number",
)

# The ONLY Employee fields the board write may touch.
UPDATABLE_BENCH_FIELDS = frozenset(
	{
		"deployment_status",
		"hotlist",
		"current_client",
		"availability_date",
		"bench_start_date",
		"marketing_owner",
		"primary_skill",
	}
)

VALID_DEPLOYMENT_STATUSES = frozenset({"Working", "Rolling-Off", "On Bench", "Marketing"})
VALID_HOTLIST = frozenset({"Red", "Orange", "Green"})

# Consultants shown on the board by default: available to market now or soon
# (Rolling-Off = still on a project but ending, so market early).
DEFAULT_BENCH_STATUSES = ["Rolling-Off", "On Bench", "Marketing"]

# Sort order for the hotlist: Red (hottest) first.
_HOTLIST_ORDER = {"Red": 0, "Orange": 1, "Green": 2}

REQUIREMENT_FIELDS = (
	"name",
	"title",
	"client",
	"primary_skill",
	"location",
	"work_mode",
	"priority",
	"posted_by",
	"posted_on",
)

# ---------------------------------------------------------------------------
# Self-service (consultant) surface — everything below resolves the caller to
# their OWN Employee via user_id and reads through hardcoded non-rate allowlists,
# so a consultant can never see rates/margin (theirs or anyone else's).
# ---------------------------------------------------------------------------

# What a consultant may see about themselves. Deliberately NO rate/margin field.
MY_PROFILE_FIELDS = (
	"name",
	"employee_name",
	"designation",
	"department",
	"image",
	"deployment_status",
	"hotlist",
	"current_client",
	"primary_skill",
	"visa_status",
	"visa_expiry",
	"availability_date",
	"bench_start_date",
	"marketing_owner",
	"company_email",
	"personal_email",
	"cell_number",
	"consultant_note",
)

# The ONLY Submission fields any self/pipeline read returns — NEVER the
# permlevel-1 submitted_bill_rate.
# Recruiter/manager view of a submission — includes internal feedback (never rates).
SUBMISSION_SAFE_FIELDS = (
	"name",
	"requirement",
	"client",
	"status",
	"source",
	"submitted_by",
	"submitted_on",
	"interview_datetime",
	"feedback",
)
# Candidate self-view — status + schedule ONLY. NO feedback of any kind (the whole
# point: recruiters record client feedback the candidate must never see).
CANDIDATE_SUBMISSION_FIELDS = (
	"name",
	"requirement",
	"client",
	"status",
	"source",
	"submitted_on",
	"interview_datetime",
)
# Interview round fields the CANDIDATE may see — date/type/outcome, no feedback.
CANDIDATE_INTERVIEW_FIELDS = ("round_no", "interview_date", "mode", "outcome")
# Interview round fields the RECRUITER/MANAGER sees — includes client feedback.
INTERVIEW_FIELDS = (
	"round_no",
	"interview_date",
	"mode",
	"interviewer",
	"outcome",
	"weak_areas",
	"client_feedback",
)

# Before these stages the end-client name is hidden from the consultant
# (account protection — recruiters own the client relationship until interview).
PRE_INTERVIEW_STATUSES = frozenset({"Submitted", "Under Review"})

# The ONLY Employee fields a consultant may change about themselves.
SELF_UPDATABLE_FIELDS = frozenset(
	{
		"availability_date",
		"visa_status",
		"visa_expiry",
		"personal_email",
		"cell_number",
		"consultant_note",
	}
)

# Document types a consultant may self-upload (matches Consultant Document Select).
ALLOWED_DOCUMENT_TYPES = frozenset(
	{
		"Resume",
		"Visa",
		"Work Authorization (EAD/I-797)",
		"Driver License",
		"Passport",
		"Offer Letter",
		"Other",
	}
)
ALLOWED_DOC_EXTENSIONS = frozenset({"pdf", "doc", "docx", "png", "jpg", "jpeg"})
MAX_DOC_BYTES = 10 * 1024 * 1024  # 10 MB

# --- Monthly consultant timesheets ---
# The ONLY Consultant Timesheet fields any read returns. No dollar/rate field exists
# on that DocType, so there is nothing to leak — this is the firewall by construction.
TIMESHEET_SAFE_FIELDS = (
	"name",
	"period_month",
	"client",
	"status",
	"total_hours",
	"signed_pdf",
	"note",
	"review_note",
	"submitted_on",
	"reviewed_on",
)
TIMESHEET_STATUSES = frozenset({"Submitted", "Under Review", "Approved", "Rejected"})
# Months back the portal derives the consultant's "owed" list for.
TIMESHEET_OWED_LOOKBACK = 6
# Roles allowed to review (approve/reject) a timesheet — reuse native HR Manager.
HR_ACTION_ROLES = frozenset({"HR Manager", "Recruiting Manager", "System Manager"})
# Roles allowed to mint a consultant login (onboarding) — NOT plain recruiters.
MANAGER_ROLES = frozenset({"Recruiting Manager", "HR Manager", "System Manager"})
# Caps for user-supplied input at the API boundary (avoid raw DB errors on overflow).
MAX_NOTE_LEN = 2000
MAX_HOURS = 1000.0

# Statuses a recruiter may set from the pipeline rail.
SUBMISSION_STATUSES = frozenset(
	{
		"Submitted",
		"Under Review",
		"Interview Scheduled",
		"Interview Done",
		"Offer",
		"Placed",
		"Rejected",
		"Withdrawn",
	}
)
# Pipeline rail hides already-closed submissions.
PIPELINE_CLOSED_STATUSES = ("Rejected", "Withdrawn", "Placed")


@frappe.whitelist()
def get_bench(
	search: str | None = None,
	skill: str | None = None,
	visa: str | None = None,
	deployment_status: str | None = None,
	hotlist: str | None = None,
	available_by: str | None = None,
	start: int = 0,
	page_length: int = 100,
) -> dict:
	"""Return bench consultants (no rate fields), sorted Red→Orange→Green."""
	_require_recruiting_role()

	# Clamp pagination so a negative/garbage value can't reach SQL (LIMIT -5 → error).
	try:
		start = max(0, int(start))
		page_length = min(max(1, int(page_length)), 500)
	except (TypeError, ValueError):
		start, page_length = 0, 100

	filters: dict = {"status": "Active"}
	if deployment_status == "All":
		pass  # every active consultant, incl. Working
	elif deployment_status:
		filters["deployment_status"] = deployment_status
	else:
		filters["deployment_status"] = ["in", DEFAULT_BENCH_STATUSES]
	if hotlist:
		filters["hotlist"] = hotlist
	if skill:
		filters["primary_skill"] = skill
	if visa:
		filters["visa_status"] = visa
	if available_by:
		filters["availability_date"] = ["<=", available_by]

	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"employee_name": ["like", like], "primary_skill": ["like", like]}

	rows = frappe.get_list(
		"Employee",
		filters=filters,
		or_filters=or_filters,
		fields=list(BENCH_FIELDS),
		order_by="availability_date asc, modified desc",
		start=start,
		page_length=page_length,
	)
	rows.sort(key=lambda r: _HOTLIST_ORDER.get(r.get("hotlist"), 3))
	return {
		"data": rows,
		"meta": {"start": int(start), "page_length": int(page_length), "returned": len(rows)},
	}


@frappe.whitelist()
def get_open_requirements(search: str | None = None, skill: str | None = None) -> dict:
	"""Return Open client requirements (no rate fields) for the board's req column."""
	_require_recruiting_role()

	filters: dict = {"status": "Open"}
	if skill:
		filters["primary_skill"] = skill

	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"title": ["like", like], "client": ["like", like], "primary_skill": ["like", like]}

	rows = frappe.get_list(
		"Client Requirement",
		filters=filters,
		or_filters=or_filters,
		fields=list(REQUIREMENT_FIELDS),
		order_by="priority desc, posted_on desc",
		page_length=100,
	)
	return {"data": rows, "meta": {"returned": len(rows)}}


@frappe.whitelist(methods=["POST"])
def update_bench(employee: str, updates: str | dict) -> dict:
	"""Update a consultant's bench fields. Role-gated + field-allowlisted."""
	_require_recruiting_role()

	payload = frappe.parse_json(updates) if isinstance(updates, str) else (updates or {})
	if not isinstance(payload, dict) or not payload:
		frappe.throw(_("No updates provided."), frappe.exceptions.ValidationError)

	unknown = set(payload) - UPDATABLE_BENCH_FIELDS
	if unknown:
		frappe.throw(
			_("These fields cannot be updated from the board: {0}").format(", ".join(sorted(unknown))),
			frappe.exceptions.PermissionError,
		)

	status = payload.get("deployment_status")
	if status is not None and status not in VALID_DEPLOYMENT_STATUSES:
		frappe.throw(_("Invalid status: {0}").format(status), frappe.exceptions.ValidationError)
	hot = payload.get("hotlist")
	if hot is not None and hot not in VALID_HOTLIST:
		frappe.throw(_("Invalid hotlist value: {0}").format(hot), frappe.exceptions.ValidationError)

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Consultant {0} not found.").format(employee), frappe.exceptions.DoesNotExistError)

	doc = frappe.get_doc("Employee", employee)
	for field, value in payload.items():
		doc.set(field, value)
	doc.save(ignore_permissions=True)  # employee_hooks.apply_status_rules still runs

	return {
		"data": {
			"employee": doc.name,
			"deployment_status": doc.deployment_status,
			"hotlist": doc.hotlist,
			"current_client": doc.current_client,
			"availability_date": doc.availability_date,
		}
	}


@frappe.whitelist(methods=["POST"])
def create_submission(
	consultant: str | None = None, requirement: str | None = None, vendor: str | None = None
) -> dict:
	"""Create a bench-consultant Submission (drag consultant → requirement).

	Runs with the caller's own permissions so the double-submission / RTR
	validation still fires and blocks duplicates.
	"""
	_require_recruiting_role()

	if not consultant or not requirement:
		frappe.throw(_("Consultant and requirement are required."), frappe.exceptions.ValidationError)
	if not frappe.db.exists("Employee", consultant):
		frappe.throw(_("Consultant {0} not found.").format(consultant), frappe.exceptions.DoesNotExistError)
	if not frappe.db.exists("Client Requirement", requirement):
		frappe.throw(
			_("Requirement {0} not found.").format(requirement), frappe.exceptions.DoesNotExistError
		)

	doc = frappe.get_doc(
		{
			"doctype": "Submission",
			"source": "Bench Consultant",
			"consultant": consultant,
			"requirement": requirement,
			"vendor": vendor,
			"status": "Submitted",
		}
	)
	doc.insert()
	return {"data": {"name": doc.name}}


# ---------------------------------------------------------------------------
# Consultant self-service endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_my_profile() -> dict:
	"""Return the calling consultant's own profile (no rate/margin fields ever)."""
	emp = _resolve_my_employee()
	rows = frappe.get_all("Employee", filters={"name": emp}, fields=list(MY_PROFILE_FIELDS))
	if not rows:
		frappe.throw(_("Profile not found."), frappe.exceptions.DoesNotExistError)
	profile = rows[0]

	# Skills (child table) — names only.
	profile["skills"] = frappe.get_all(
		"RaceDog Skill Item",
		filters={"parent": emp, "parenttype": "Employee"},
		pluck="skill",
	)
	# The consultant's own documents (they may re-download their own files).
	profile["documents"] = frappe.get_all(
		"Consultant Document",
		filters={"parent": emp, "parenttype": "Employee"},
		fields=["document_type", "document", "expiry_date", "uploaded_on"],
		order_by="uploaded_on desc",
	)
	# Who markets me + how to reach them (kills the "who's my recruiter?" question).
	profile["marketing_owner_contact"] = _user_contact(profile.get("marketing_owner"))
	return {"data": profile}


@frappe.whitelist()
def get_my_submissions() -> dict:
	"""Return the calling consultant's own submissions — status + schedule ONLY.

	NO feedback of any kind (client feedback / weak areas are recruiter-only). Client
	name is masked until the interview stage (the recruiter owns the client
	relationship until an interview is booked). Interview rounds show date/type/
	outcome so the candidate knows where they stand — never the feedback.
	"""
	emp = _resolve_my_employee()
	rows = frappe.get_all(
		"Submission",
		filters={"source": "Bench Consultant", "consultant": emp},
		fields=list(CANDIDATE_SUBMISSION_FIELDS),
		order_by="submitted_on desc",
		page_length=200,
	)
	titles = _requirement_titles([r.get("requirement") for r in rows])
	for r in rows:
		r["requirement_title"] = titles.get(r.get("requirement"), r.get("requirement"))
		if r.get("status") in PRE_INTERVIEW_STATUSES:
			r["client"] = None  # hide the end client until interview stage
		# Candidate-safe interview rounds: date/type/outcome, NEVER feedback fields.
		r["interviews"] = frappe.get_all(
			"Submission Interview",
			filters={"parent": r["name"], "parenttype": "Submission"},
			fields=list(CANDIDATE_INTERVIEW_FIELDS),
			order_by="round_no asc",
		)
	return {"data": rows, "meta": {"returned": len(rows)}}


@frappe.whitelist(methods=["POST"])
def update_my_profile(updates: str | dict) -> dict:
	"""Let a consultant maintain their own availability / work-auth / skills / note.

	Strictly field-allowlisted (no status, hotlist, client, rate, or owner writes).
	Saves with ``ignore_permissions`` so apply_status_rules still runs.
	"""
	emp = _resolve_my_employee()

	payload = frappe.parse_json(updates) if isinstance(updates, str) else (updates or {})
	if not isinstance(payload, dict) or not payload:
		frappe.throw(_("No updates provided."), frappe.exceptions.ValidationError)

	allowed = SELF_UPDATABLE_FIELDS | {"consultant_skills"}
	unknown = set(payload) - allowed
	if unknown:
		frappe.throw(
			_("You cannot change these fields: {0}").format(", ".join(sorted(unknown))),
			frappe.exceptions.PermissionError,
		)

	doc = frappe.get_doc("Employee", emp)
	skills = payload.pop("consultant_skills", None)
	for field, value in payload.items():
		# Cap free-text so an oversized value can't overflow the column (raw DB 500).
		if field == "consultant_note" and isinstance(value, str):
			value = value[:MAX_NOTE_LEN]
		doc.set(field, value)

	if skills is not None:
		if not isinstance(skills, list):
			frappe.throw(_("Skills must be a list."), frappe.exceptions.ValidationError)
		doc.set("consultant_skills", [])
		for skill in skills:
			if frappe.db.exists("Skill", skill):
				doc.append("consultant_skills", {"skill": skill})

	doc.save(ignore_permissions=True)
	return {
		"data": {
			"availability_date": doc.availability_date,
			"visa_status": doc.visa_status,
			"visa_expiry": doc.visa_expiry,
			"cell_number": doc.cell_number,
			"personal_email": doc.personal_email,
			"consultant_note": doc.get("consultant_note"),
		}
	}


@frappe.whitelist(methods=["POST"])
def upload_my_document(
	document_type: str,
	file_name: str,
	content: str,
	expiry_date: str | None = None,
	notes: str | None = None,
) -> dict:
	"""Attach a private document (resume / work-auth) to the caller's own record.

	``content`` is base64. The File is created private + attached to the Employee,
	then a Consultant Document row is appended and the Employee saved with
	``ignore_permissions`` (the consultant never gets blanket Employee write).
	"""
	emp = _resolve_my_employee()

	if document_type not in ALLOWED_DOCUMENT_TYPES:
		frappe.throw(_("Unsupported document type: {0}").format(document_type), frappe.exceptions.ValidationError)

	ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").lower()
	if ext not in ALLOWED_DOC_EXTENSIONS:
		frappe.throw(
			_("Only these file types are allowed: {0}").format(", ".join(sorted(ALLOWED_DOC_EXTENSIONS))),
			frappe.exceptions.ValidationError,
		)

	# Validate the optional expiry date up front (a bad value would otherwise 500
	# at the DB layer). Normalize to an ISO date string.
	if expiry_date:
		try:
			expiry_date = frappe.utils.getdate(expiry_date).isoformat()
		except Exception:
			frappe.throw(_("Expiry date isn't a valid date."), frappe.exceptions.ValidationError)

	import base64
	import binascii

	raw = content.split(",", 1)[-1] if content.startswith("data:") else content
	try:
		decoded = base64.b64decode(raw, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The uploaded file could not be read."), frappe.exceptions.ValidationError)
	if not decoded:
		frappe.throw(_("The uploaded file is empty."), frappe.exceptions.ValidationError)
	if len(decoded) > MAX_DOC_BYTES:
		frappe.throw(_("File is too large (max 10 MB)."), frappe.exceptions.ValidationError)

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{emp}-{document_type}-{file_name}",
			"attached_to_doctype": "Employee",
			"attached_to_name": emp,
			"is_private": 1,
			"content": raw,
			"decode": True,
		}
	).insert(ignore_permissions=True)

	doc = frappe.get_doc("Employee", emp)
	doc.append(
		"documents",
		{
			"document_type": document_type,
			"document": file_doc.file_url,
			"expiry_date": expiry_date or None,
			"uploaded_on": frappe.utils.nowdate(),
			"notes": (notes or "")[:MAX_NOTE_LEN] or None,
		},
	)
	doc.save(ignore_permissions=True)
	return {"data": {"file_url": file_doc.file_url, "document_type": document_type}}


# ---------------------------------------------------------------------------
# Monthly consultant timesheets (employee upload + HR review)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def upload_my_timesheet(
	period_month: str, file_name: str, content: str, total_hours=None, note: str | None = None
) -> dict:
	"""Upload (or re-upload) the caller's signed monthly timesheet PDF.

	Upsert by (consultant, period_month): a re-upload replaces the file on the SAME
	row and re-opens it for review — never a duplicate. An Approved month is locked.
	"""
	import re

	emp = _resolve_my_employee()
	if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period_month or ""):
		frappe.throw(_("Pick a valid month (YYYY-MM)."), frappe.exceptions.ValidationError)

	ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "").lower()
	if ext != "pdf":
		frappe.throw(_("The timesheet must be a PDF."), frappe.exceptions.ValidationError)

	import base64
	import binascii

	raw = content.split(",", 1)[-1] if content.startswith("data:") else content
	try:
		decoded = base64.b64decode(raw, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read."), frappe.exceptions.ValidationError)
	if not decoded:
		frappe.throw(_("The file is empty."), frappe.exceptions.ValidationError)
	if len(decoded) > MAX_DOC_BYTES:
		frappe.throw(_("File is too large (max 10 MB)."), frappe.exceptions.ValidationError)

	existing = frappe.db.get_value(
		"Consultant Timesheet", {"consultant": emp, "period_month": period_month}, "name"
	)
	if existing and frappe.db.get_value("Consultant Timesheet", existing, "status") == "Approved":
		frappe.throw(
			_("This month is already approved and can't be changed."),
			frappe.exceptions.ValidationError,
		)

	# Create the private File first (signed_pdf is mandatory, so the row can't be
	# inserted without it). Attach it to the timesheet below so HR — who has read
	# on the timesheet — can view the PDF. Frappe scans the PDF (rejects embedded
	# JS / corrupt files); turn that into a friendly message.
	try:
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"TS-{emp}-{period_month}-{file_name}",
				"is_private": 1,
				"content": raw,
				"decode": True,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.throw(
			_("That PDF couldn't be read. Please upload a valid, unlocked PDF."),
			frappe.exceptions.ValidationError,
		)

	# Clamp hours to a sane range; the signed PDF is the source of truth anyway.
	hours = min(max(frappe.utils.flt(total_hours), 0.0), MAX_HOURS) if total_hours else None
	if existing:
		doc = frappe.get_doc("Consultant Timesheet", existing)
		old_file = doc.signed_pdf
		doc.signed_pdf = file_doc.file_url
		doc.total_hours = hours
		doc.note = (note or "")[:MAX_NOTE_LEN] or None
		doc.status = "Submitted"
		doc.review_note = None
		doc.reviewed_by = None
		doc.reviewed_on = None
		doc.save(ignore_permissions=True)
		# Remove the superseded File so old signed PDFs don't accumulate/stay reachable.
		if old_file and old_file != file_doc.file_url:
			_delete_file_by_url(old_file)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Consultant Timesheet",
				"consultant": emp,
				"period_month": period_month,
				"signed_pdf": file_doc.file_url,
				"total_hours": hours,
				"note": (note or "")[:MAX_NOTE_LEN] or None,
				"status": "Submitted",
			}
		)
		doc.insert(ignore_permissions=True)

	# Link the file to the timesheet for HR visibility + tidy cleanup.
	file_doc.db_set({"attached_to_doctype": "Consultant Timesheet", "attached_to_name": doc.name})

	return {"data": {"name": doc.name, "period_month": period_month, "status": doc.status}}


@frappe.whitelist()
def get_my_timesheets() -> dict:
	"""Return the caller's own timesheets + a derived list of months still owed."""
	emp = _resolve_my_employee()
	rows = frappe.get_all(
		"Consultant Timesheet",
		filters={"consultant": emp},
		fields=list(TIMESHEET_SAFE_FIELDS),
		order_by="period_month desc",
	)

	# "Owed" = recent prior months with no submission. Whether it's REQUIRED depends
	# on being currently deployed (Working with a client); on the bench, it's labeled
	# "not required" rather than "missing".
	info = frappe.db.get_value(
		"Employee", emp, ["deployment_status", "current_client"], as_dict=True
	)
	required = bool(info and info.current_client and info.deployment_status == "Working")
	submitted = {r["period_month"] for r in rows}
	first = frappe.utils.getdate(frappe.utils.nowdate()).replace(day=1)
	owed = []
	for i in range(1, TIMESHEET_OWED_LOOKBACK + 1):
		period = frappe.utils.getdate(frappe.utils.add_months(first, -i)).strftime("%Y-%m")
		if period not in submitted:
			owed.append({"period_month": period, "required": required})
	default_period = (
		owed[0]["period_month"]
		if owed
		else frappe.utils.getdate(frappe.utils.add_months(first, -1)).strftime("%Y-%m")
	)
	return {"data": rows, "owed": owed, "default_period": default_period}


@frappe.whitelist(methods=["POST"])
def approve_timesheet(timesheet: str) -> dict:
	"""HR approves a timesheet. The consultant is notified."""
	return _review_timesheet(timesheet, "Approved", None)


@frappe.whitelist(methods=["POST"])
def reject_timesheet(timesheet: str, note: str | None = None) -> dict:
	"""HR rejects a timesheet with a mandatory reason. The consultant is notified."""
	if not (note or "").strip():
		frappe.throw(_("Add a reason so the consultant knows what to fix."), frappe.exceptions.ValidationError)
	return _review_timesheet(timesheet, "Rejected", note.strip()[:MAX_NOTE_LEN])


def _review_timesheet(timesheet: str, status: str, note: str | None) -> dict:
	_require_hr_role()
	if not frappe.db.exists("Consultant Timesheet", timesheet):
		frappe.throw(_("Timesheet {0} not found.").format(timesheet), frappe.exceptions.DoesNotExistError)

	doc = frappe.get_doc("Consultant Timesheet", timesheet)
	# Approved is terminal — it can't be re-opened or flipped (would let the
	# consultant re-upload over a signed-off month). Re-approving is a no-op.
	if doc.status == "Approved":
		if status == "Approved":
			return {"data": {"name": doc.name, "status": doc.status}}
		frappe.throw(
			_("This timesheet is already approved and can't be changed."),
			frappe.exceptions.ValidationError,
		)
	doc.status = status
	doc.review_note = note
	doc.reviewed_by = frappe.session.user
	doc.reviewed_on = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)

	# Tell the consultant (in-app bell). Reject carries the reason.
	user = frappe.db.get_value("Employee", doc.consultant, "user_id")
	if user:
		if status == "Approved":
			subject = _("Your {0} timesheet was approved.").format(doc.period_month)
		else:
			subject = _("Your {0} timesheet needs changes: {1}").format(doc.period_month, note)
		from racedog_hr.tasks import _notify

		_notify({user}, subject, "Consultant Timesheet", doc.name)

	return {"data": {"name": doc.name, "status": doc.status}}


def _require_hr_role() -> None:
	if not (set(frappe.get_roles()) & HR_ACTION_ROLES):
		frappe.throw(_("Only HR can review timesheets."), frappe.exceptions.PermissionError)


# ---------------------------------------------------------------------------
# Recruiter pipeline rail
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_my_pipeline() -> dict:
	"""Return the caller's own active submissions (rate-excluded) for the board rail."""
	_require_recruiting_role()
	rows = frappe.get_list(
		"Submission",
		filters={
			"submitted_by": frappe.session.user,
			"status": ["not in", PIPELINE_CLOSED_STATUSES],
		},
		fields=list(SUBMISSION_SAFE_FIELDS),
		order_by="modified desc",
		page_length=100,
	)
	titles = _requirement_titles([r.get("requirement") for r in rows])
	names = _consultant_names([r.get("name") for r in rows])
	for r in rows:
		r["requirement_title"] = titles.get(r.get("requirement"), r.get("requirement"))
		r["candidate"] = names.get(r.get("name"))
	return {"data": rows, "meta": {"returned": len(rows)}}


@frappe.whitelist()
def get_candidate_pipeline(consultant: str) -> dict:
	"""Recruiter/manager view of ONE candidate: every submission with its full
	round-by-round interview history AND the client feedback per round.

	Recruiter/manager-only — this is the surface that carries the client feedback a
	candidate must never see. No rate field is ever included.
	"""
	_require_recruiting_role()
	if not frappe.db.exists("Employee", consultant):
		frappe.throw(_("Consultant {0} not found.").format(consultant), frappe.exceptions.DoesNotExistError)

	candidate_name = frappe.db.get_value("Employee", consultant, "employee_name")
	subs = frappe.get_all(
		"Submission",
		filters={"consultant": consultant},
		fields=list(SUBMISSION_SAFE_FIELDS),
		order_by="submitted_on desc",
		page_length=200,
	)
	titles = _requirement_titles([s.get("requirement") for s in subs])
	for s in subs:
		s["requirement_title"] = titles.get(s.get("requirement"), s.get("requirement"))
		# Full interview rounds INCLUDING weak_areas + client_feedback (internal).
		s["interviews"] = frappe.get_all(
			"Submission Interview",
			filters={"parent": s["name"], "parenttype": "Submission"},
			fields=list(INTERVIEW_FIELDS),
			order_by="round_no asc",
		)
	return {"data": {"consultant": consultant, "candidate": candidate_name, "submissions": subs}}


@frappe.whitelist(methods=["POST"])
def add_interview(
	submission: str | None = None,
	interview_date: str | None = None,
	mode: str | None = None,
	interviewer: str | None = None,
	outcome: str | None = None,
	weak_areas: str | None = None,
	client_feedback: str | None = None,
) -> dict:
	"""Append an interview round (with client feedback) to a submission. Recruiter/
	manager-only; the next round number is assigned automatically."""
	_require_recruiting_role()
	if not submission or not frappe.db.exists("Submission", submission):
		frappe.throw(_("Submission not found."), frappe.exceptions.DoesNotExistError)

	doc = frappe.get_doc("Submission", submission)
	next_round = max((row.round_no or 0 for row in doc.interviews), default=0) + 1
	doc.append(
		"interviews",
		{
			"round_no": next_round,
			"interview_date": interview_date or None,
			"mode": mode or "Technical",
			"interviewer": (interviewer or "")[:140] or None,
			"outcome": outcome or "Scheduled",
			"weak_areas": (weak_areas or "")[:MAX_NOTE_LEN] or None,
			"client_feedback": (client_feedback or "")[:MAX_NOTE_LEN] or None,
		},
	)
	# Keep the header "next interview" pointer + status roughly in step.
	if interview_date:
		doc.interview_datetime = interview_date
		if doc.status in ("Submitted", "Under Review"):
			doc.status = "Interview Scheduled"
	doc.save(ignore_permissions=True)
	return {"data": {"submission": doc.name, "round_no": next_round}}


@frappe.whitelist(methods=["POST"])
def create_consultant_login(employee: str) -> dict:
	"""Give a consultant portal access in one click (manager/recruiter action).

	Creates (or links) a User with the ``Employee`` role and connects it to the
	Employee via ``user_id`` — after which the boot hook lands them on their
	consultant portal. Returns the login email and, for a freshly created user, a
	temporary password to hand over (they change it on first login).

	Manager-gated: this mints a System User account, so a plain recruiter (who can
	edit a consultant's email) must not be able to chain it into an account they
	control. Onboarding is a manager/HR action.
	"""
	_require_manager()

	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Consultant {0} not found.").format(employee), frappe.exceptions.DoesNotExistError)

	emp = frappe.get_doc("Employee", employee)
	if emp.user_id:
		return {"data": {"user": emp.user_id, "created": False, "temp_password": None}}

	email = emp.get("company_email") or emp.get("personal_email") or emp.get("prefered_email")
	if not email:
		frappe.throw(
			_("Add a company or personal email to this consultant first, then create the login."),
			frappe.exceptions.ValidationError,
		)

	# Creating a User + the Employee's User Permission needs elevated rights that a
	# recruiting manager doesn't hold directly. The action is already role-gated
	# above, so run the privileged writes as Administrator and always restore.
	actor = frappe.session.user
	try:
		frappe.set_user("Administrator")
		temp_password = None
		if not frappe.db.exists("User", email):
			temp_password = "Rdg-" + frappe.generate_hash(length=8)
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": emp.get("first_name") or emp.employee_name,
					"last_name": emp.get("last_name") or "",
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": "Employee"}],
				}
			)
			user.new_password = temp_password
			user.insert(ignore_permissions=True)

		# Save through the controller so Frappe assigns the Employee role + user
		# permission, and our link/status hooks run.
		emp = frappe.get_doc("Employee", employee)
		emp.user_id = email
		emp.save(ignore_permissions=True)
	finally:
		frappe.set_user(actor)

	return {"data": {"user": email, "created": temp_password is not None, "temp_password": temp_password}}


@frappe.whitelist(methods=["POST"])
def update_submission_status(
	submission: str | None = None, status: str | None = None, feedback: str | None = None
) -> dict:
	"""Advance a submission's stage from the pipeline rail. Role-gated, allowlisted.

	Only ``status`` + ``feedback`` can change — never a rate. Saves through the
	controller so dedupe / placed-sync / notifications still fire.
	"""
	_require_recruiting_role()

	if not submission or not status:
		frappe.throw(_("Submission and status are required."), frappe.exceptions.ValidationError)
	if status not in SUBMISSION_STATUSES:
		frappe.throw(_("Invalid status: {0}").format(status), frappe.exceptions.ValidationError)
	if not frappe.db.exists("Submission", submission):
		frappe.throw(_("Submission {0} not found.").format(submission), frappe.exceptions.DoesNotExistError)

	doc = frappe.get_doc("Submission", submission)
	doc.status = status
	if feedback is not None:
		doc.feedback = feedback
	doc.save(ignore_permissions=True)
	return {"data": {"name": doc.name, "status": doc.status, "feedback": doc.feedback}}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _delete_file_by_url(file_url: str) -> None:
	"""Best-effort delete of a private File by its URL (replacing a prior upload)."""
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return
	try:
		frappe.delete_doc("File", name, ignore_permissions=True, force=True)
	except Exception:
		pass


def _resolve_my_employee() -> str:
	"""Resolve the logged-in user to their own Employee, or throw a friendly error."""
	emp = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"
	)
	if not emp:
		frappe.throw(
			_(
				"Your login isn't linked to a consultant profile yet. "
				"Ask your recruiting manager to connect your account."
			),
			frappe.exceptions.PermissionError,
		)
	return emp


def _requirement_titles(requirements) -> dict:
	"""Map requirement name -> title for a batch of submission rows."""
	names = {r for r in requirements if r}
	if not names:
		return {}
	rows = frappe.get_all(
		"Client Requirement", filters={"name": ["in", list(names)]}, fields=["name", "title"]
	)
	return {r["name"]: r["title"] for r in rows}


def _consultant_names(submissions) -> dict:
	"""Map submission name -> a display candidate name (bench consultant or external)."""
	names = {s for s in submissions if s}
	if not names:
		return {}
	rows = frappe.get_all(
		"Submission",
		filters={"name": ["in", list(names)]},
		fields=["name", "consultant", "external_name", "source"],
	)
	result: dict = {}
	for r in rows:
		if r["source"] == "Bench Consultant" and r["consultant"]:
			result[r["name"]] = frappe.db.get_value("Employee", r["consultant"], "employee_name")
		else:
			result[r["name"]] = r["external_name"]
	return result


def _user_contact(user: str | None) -> dict | None:
	"""Public contact card for a marketing owner (name + email + phone)."""
	if not user or not frappe.db.exists("User", user):
		return None
	row = frappe.db.get_value("User", user, ["full_name", "email", "mobile_no"], as_dict=True)
	return {"name": row.full_name, "email": row.email, "phone": row.mobile_no} if row else None


def _require_recruiting_role() -> None:
	if not (set(frappe.get_roles()) & RECRUITING_ROLES):
		frappe.throw(
			_("You do not have access to the Bench Board."), frappe.exceptions.PermissionError
		)


def _require_manager() -> None:
	if not (set(frappe.get_roles()) & MANAGER_ROLES):
		frappe.throw(
			_("Only a manager can do this."), frappe.exceptions.PermissionError
		)
