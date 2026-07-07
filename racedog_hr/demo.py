# Copyright (c) 2026, RaceDog Technologies and contributors
"""Idempotent demo-data seeder.

Run:  bench --site <site> console  then  `from racedog_hr.demo import seed; seed()`

Creates a company, staffing masters, consultants on the bench, open client
requirements, a couple of submissions, and two demo logins (a recruiter who
cannot see rates, and a manager who can) so the app is immediately explorable.

Commits after every phase and tolerates per-record errors, so a partial failure
never rolls the whole thing back.
"""

import frappe
from frappe.utils import add_days, nowdate

COMPANY = "RaceDog Technologies"
DEMO_PASSWORD = "racedog123"

WORK_AUTHS = [
	("USC", 0),
	("GC", 0),
	("GC-EAD", 0),
	("H1B", 1),
	("OPT-EAD", 1),
	("H4-EAD", 1),
	("TN", 1),
]
SKILLS = [
	("Java", "Language"),
	("Python", "Language"),
	("React", "Framework"),
	("AWS", "Cloud"),
	("Salesforce", "ERP / CRM"),
	("Data Engineer", "Data / ML"),
	("DevOps", "DevOps"),
	("SAP", "ERP / CRM"),
]
CLIENTS = ["Meridian Health", "Cobalt Financial", "Northwind Retail", "Vertex Logistics"]
VENDORS = [
	("Apex Global", "Prime Vendor"),
	("BlueBridge Partners", "Implementation Partner"),
	("TriState Staffing", "Sub Vendor"),
]

# first, last, gender, skill, visa, deployment_status, days_until_available, bill, pay
CONSULTANTS = [
	("Priya", "Nair", "Female", "Python", "H1B", "On Bench", -12, 92, 68),
	("Marcus", "Bell", "Male", "Java", "USC", "On Bench", -5, 105, 80),
	("Wei", "Zhang", "Male", "React", "OPT-EAD", "Marketing", 3, 88, 60),
	("Sofia", "Reyes", "Female", "AWS", "GC", "Marketing", 0, 110, 82),
	("Dev", "Patel", "Male", "Data Engineer", "H1B", "Interviewing", -20, 98, 70),
	("Hana", "Okafor", "Female", "Salesforce", "GC-EAD", "On Bench", 7, 95, 72),
	("Liam", "Novak", "Male", "DevOps", "TN", "Rolling-Off", 21, 100, 76),
	("Aisha", "Rahman", "Female", "SAP", "USC", "Billing", 45, 120, 90),
]

# title, client, skill, priority, location, work_mode, max_bill
REQUIREMENTS = [
	("Senior Python Engineer", "Meridian Health", "Python", "High", "Austin, TX", "Hybrid", 100),
	("React Front-End Developer", "Northwind Retail", "React", "Urgent", "Remote", "Remote", 95),
	("AWS DevOps Engineer", "Cobalt Financial", "AWS", "Medium", "New York, NY", "Onsite", 115),
	("Salesforce Consultant", "Vertex Logistics", "Salesforce", "High", "Chicago, IL", "Hybrid", 105),
	("Data Engineer (Spark)", "Cobalt Financial", "Data Engineer", "Medium", "Remote", "Remote", 108),
]

DEMO_USERS = [
	("recruiter@racedog.test", "Rhea", "Recruiter", ["Recruiter", "Bench Sales"]),
	("manager@racedog.test", "Marco", "Manager", ["Recruiting Manager"]),
]


def seed():
	frappe.set_user("Administrator")
	_run("prereqs", _prereqs)
	_run("company", _company)
	_run("masters", _masters)
	consultants = _run("consultants", _consultants) or []
	requirements = _run("requirements", _requirements) or []
	_run("submissions", lambda: _submissions(consultants, requirements))
	_run("users", _users)
	summary = {
		"company": frappe.db.count("Company"),
		"consultants": frappe.db.count("Employee", {"status": "Active"}),
		"requirements": frappe.db.count("Client Requirement"),
		"submissions": frappe.db.count("Submission"),
		"users": [u[0] for u in DEMO_USERS if frappe.db.exists("User", u[0])],
		"password": DEMO_PASSWORD,
	}
	print("SEED DONE:", summary)
	return summary


def _run(label, fn):
	"""Run a phase, commit it, and never let one phase abort the rest."""
	try:
		result = fn()
		frappe.db.commit()
		print(f"SEED phase ok: {label}")
		return result
	except Exception as e:
		frappe.db.rollback()
		print(f"SEED phase FAILED: {label}: {repr(e)[:300]}")
		return None


def _company():
	if frappe.db.exists("Company", COMPANY):
		return
	# Fresh ERPNext site never ran the setup wizard, so a default record the
	# Company's warehouse creation references is missing. Create it first.
	if not frappe.db.exists("Warehouse Type", "Transit"):
		frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": COMPANY,
			"abbr": "RDT",
			"default_currency": "USD",
			"country": "United States",
		}
	).insert(ignore_permissions=True)


def _masters():
	for name, sponsor in WORK_AUTHS:
		_safe_insert("Work Authorization", {"work_auth": name, "requires_sponsorship": sponsor}, name)
	for name, category in SKILLS:
		_safe_insert("Skill", {"skill_name": name, "category": category}, name)
	for name in CLIENTS:
		_safe_insert("Client", {"client_name": name, "status": "Active"}, name)
	for name, vtype in VENDORS:
		_safe_insert("Vendor", {"vendor_name": name, "vendor_type": vtype, "status": "Active"}, name)


def _consultants():
	created = []
	for first, last, gender, skill, visa, status, avail_offset, bill, pay in CONSULTANTS:
		existing = frappe.db.get_value("Employee", {"employee_name": f"{first} {last}"})
		if existing:
			created.append(existing)
			continue
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": first,
					"last_name": last,
					"company": COMPANY,
					"gender": gender,
					"date_of_birth": "1990-01-15",
					"date_of_joining": "2023-02-01",
					"status": "Active",
					"deployment_status": status,
					"primary_skill": skill,
					"consultant_skills": [{"skill": skill}],
					"visa_status": visa,
					"visa_expiry": add_days(nowdate(), 120),
					"availability_date": add_days(nowdate(), avail_offset),
					"bench_start_date": add_days(nowdate(), min(avail_offset, 0)),
					"current_bill_rate": bill,
					"current_pay_rate": pay,
				}
			).insert(ignore_permissions=True)
			created.append(doc.name)
		except Exception as e:
			print(f"  consultant {first} {last} skipped: {repr(e)[:160]}")
	return created


def _requirements():
	created = []
	for title, client, skill, priority, location, work_mode, max_bill in REQUIREMENTS:
		existing = frappe.db.get_value("Client Requirement", {"title": title, "client": client})
		if existing:
			created.append(existing)
			continue
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Client Requirement",
					"title": title,
					"client": client,
					"primary_skill": skill,
					"skills": [{"skill": skill}],
					"status": "Open",
					"priority": priority,
					"location": location,
					"work_mode": work_mode,
					"positions": 1,
					"bill_rate": max_bill - 8,
					"max_bill_rate": max_bill,
					"jd_text": f"<p>Looking for a strong {skill} consultant for {client}.</p>",
				}
			).insert(ignore_permissions=True)
			created.append(doc.name)
		except Exception as e:
			print(f"  requirement {title} skipped: {repr(e)[:160]}")
	return created


def _submissions(consultants, requirements):
	if not consultants or not requirements:
		return
	pairs = [(consultants[0], requirements[0])]
	if len(consultants) > 2 and len(requirements) > 1:
		pairs.append((consultants[2], requirements[1]))
	for consultant, requirement in pairs:
		if frappe.db.exists("Submission", {"consultant": consultant, "requirement": requirement}):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Submission",
					"consultant": consultant,
					"requirement": requirement,
					"status": "Submitted",
				}
			).insert(ignore_permissions=True)
		except Exception as e:
			print(f"  submission skipped: {repr(e)[:160]}")


def _users():
	for email, first, last, roles in DEMO_USERS:
		if frappe.db.exists("User", email):
			continue
		try:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first,
					"last_name": last,
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": r} for r in roles],
				}
			)
			user.new_password = DEMO_PASSWORD
			user.insert(ignore_permissions=True)
		except Exception as e:
			print(f"  user {email} skipped: {repr(e)[:160]}")


def _safe_insert(doctype, values, key):
	if frappe.db.exists(doctype, key):
		return
	try:
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)
	except Exception as e:
		print(f"  {doctype} {key} skipped: {repr(e)[:160]}")


def _prereqs():
	"""Records a fresh ERPNext site (setup wizard never run) is missing."""
	for gender in ("Male", "Female", "Other"):
		_safe_insert("Gender", {"gender": gender}, gender)


def verify():
	"""Prove the rate/margin firewall: recruiter can't see rates, manager can.

	Run: from racedog_hr.demo import verify; verify()
	"""
	report = {}

	frappe.set_user("recruiter@racedog.test")
	from racedog_hr.api import get_bench

	bench = get_bench()
	report["recruiter_bench_rows"] = len(bench["data"])
	report["recruiter_api_leaks_rate"] = any(
		"rate" in key for row in bench["data"] for key in row
	)
	report["recruiter_getlist_rate"] = _peek_rate()

	frappe.set_user("manager@racedog.test")
	report["manager_getlist_rate"] = _peek_rate()

	frappe.set_user("Administrator")
	print("VERIFY:", report)
	return report


def _peek_rate():
	"""Return the current_bill_rate the current user can read (or how it was blocked)."""
	try:
		rows = frappe.get_list(
			"Employee", fields=["name", "current_bill_rate"], limit=1, order_by="creation asc"
		)
	except Exception as e:
		return f"BLOCKED({type(e).__name__})"
	if not rows:
		return "no-rows"
	value = rows[0].get("current_bill_rate")
	return "hidden" if value in (None, 0) else f"VISIBLE({value})"
