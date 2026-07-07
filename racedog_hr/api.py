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

VALID_DEPLOYMENT_STATUSES = frozenset({"Working", "On Bench", "Marketing"})
VALID_HOTLIST = frozenset({"Red", "Orange", "Green"})

# Consultants shown on the board by default: not currently placed = available to market.
DEFAULT_BENCH_STATUSES = ["On Bench", "Marketing"]

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
		start=int(start),
		page_length=int(page_length),
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
def create_submission(consultant: str, requirement: str, vendor: str | None = None) -> dict:
	"""Create a bench-consultant Submission (drag consultant → requirement).

	Runs with the caller's own permissions so the double-submission / RTR
	validation still fires and blocks duplicates.
	"""
	_require_recruiting_role()

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


def _require_recruiting_role() -> None:
	if not (set(frappe.get_roles()) & RECRUITING_ROLES):
		frappe.throw(
			_("You do not have access to the Bench Board."), frappe.exceptions.PermissionError
		)
