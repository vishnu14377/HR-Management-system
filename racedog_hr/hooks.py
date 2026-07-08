app_name = "racedog_hr"
app_title = "Racedog HR"
app_publisher = "RaceDog Technologies"
app_description = (
	"Recruiting-coordination layer on Frappe HRMS: bench list, client requirements, "
	"and submission tracking for IT staffing/consulting."
)
app_email = "hr@racedogtechnologies.com"
app_license = "mit"

# racedog_hr is an extension of HRMS; require it so Employee/HR modules exist.
required_apps = ["frappe/hrms"]

# Apply role/permlevel permissions and indexes after fixtures, every time — so a
# fixture hiccup during install can never leave the rate firewall half-applied.
after_install = "racedog_hr.setup.after_install"
after_migrate = "racedog_hr.setup.after_migrate"

# ---------------------------------------------------------------------------
# Fixtures — the whole config schema travels with the app and is re-applied on
# `bench migrate`. This is what keeps the customization upgrade-safe and
# reproducible (go-live gate #7 in the plan).
# ---------------------------------------------------------------------------
fixtures = [
	# Custom Fields we add to the standard Employee master (bench/availability).
	{"doctype": "Custom Field", "filters": [["module", "=", "Racedog HR"]]},
	# Any Property Setters (list settings, defaults) tagged to our module.
	{"doctype": "Property Setter", "filters": [["module", "=", "Racedog HR"]]},
	# Custom recruiting roles.
	{
		"doctype": "Role",
		"filters": [
			["name", "in", ["Recruiter", "Bench Sales", "Recruiting Manager", "Account Manager"]]
		],
	},
	# Event + scheduled notifications (new requirement, interview scheduled, etc.).
	{"doctype": "Notification", "filters": [["module", "=", "Racedog HR"]]},
	# Recruiter landing Workspace + its cards/charts.
	{"doctype": "Workspace", "filters": [["module", "=", "Racedog HR"]]},
	{"doctype": "Number Card", "filters": [["module", "=", "Racedog HR"]]},
	{"doctype": "Dashboard Chart", "filters": [["module", "=", "Racedog HR"]]},
]

# ---------------------------------------------------------------------------
# Scheduled jobs — visa/work-auth expiry and bench-availability alerts
# (go-live gate #3: visa expiry alerting is compliance-critical).
# ---------------------------------------------------------------------------
scheduler_events = {
	"daily": [
		"racedog_hr.tasks.check_visa_expiry",
		"racedog_hr.tasks.check_bench_availability",
		"racedog_hr.tasks.check_timesheet_reminders",
	],
}

# ---------------------------------------------------------------------------
# Document events — additive hooks on standard/own DocTypes. `validate` on our
# own DocTypes lives on the controller class; these are for cross-cutting reacts.
# ---------------------------------------------------------------------------
doc_events = {
	"Submission": {
		"after_insert": "racedog_hr.racedog_hr.doctype.submission.submission.assign_followup",
		"on_update": "racedog_hr.racedog_hr.doctype.submission.submission.assign_followup",
	},
	"Employee": {
		"validate": [
			"racedog_hr.employee_hooks.apply_status_rules",
			"racedog_hr.employee_hooks.link_user_id",
		],
	},
}

# ---------------------------------------------------------------------------
# Row-level access — a logged-in consultant sees only their OWN Employee record
# (self-service firewall), while recruiters/managers keep the roster-wide view.
# ---------------------------------------------------------------------------
permission_query_conditions = {
	"Employee": "racedog_hr.permissions.employee_query_conditions",
}
has_permission = {
	"Employee": "racedog_hr.permissions.employee_has_permission",
}

# Land pure consultants on their self-service portal (not the empty welcome page).
extend_bootinfo = "racedog_hr.boot.boot_session"

# Color the Employee list rows by deployment status (v15 has no native Select
# option colors, so this drives the list indicator).
doctype_list_js = {"Employee": "public/js/employee_list.js"}

# Form scripts: "Create Portal Login" on Employee; HR approve/reject on timesheets.
doctype_js = {
	"Employee": "public/js/employee.js",
	"Consultant Timesheet": "public/js/consultant_timesheet.js",
}

# BambooHR-inspired theme applied across the whole Desk (bundled -> shared assets).
app_include_css = "bamboo_theme.bundle.css"
