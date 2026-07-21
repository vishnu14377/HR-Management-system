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
from frappe.utils import add_days, add_months, getdate, now_datetime, nowdate

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

# first, last, gender, skill, visa, status, hotlist, days_until_available, bill, pay, current_client
CONSULTANTS = [
	("Priya", "Nair", "Female", "Python", "H1B", "Marketing", "Red", -12, 92, 68, None),
	("Marcus", "Bell", "Male", "Java", "USC", "On Bench", "Orange", -5, 105, 80, None),
	("Wei", "Zhang", "Male", "React", "OPT-EAD", "Marketing", "Red", 3, 88, 60, None),
	("Sofia", "Reyes", "Female", "AWS", "GC", "Marketing", "Orange", 0, 110, 82, None),
	("Dev", "Patel", "Male", "Data Engineer", "H1B", "On Bench", "Red", -20, 98, 70, None),
	("Hana", "Okafor", "Female", "Salesforce", "GC-EAD", "On Bench", "Green", 7, 95, 72, None),
	("Liam", "Novak", "Male", "DevOps", "TN", "Working", "Green", 0, 100, 76, "Cobalt Financial"),
	("Aisha", "Rahman", "Female", "SAP", "USC", "Rolling-Off", "Red", 14, 120, 90, "Vertex Logistics"),
]

# All demo consultants are owned/marketed by the demo recruiter.
DEMO_MARKETING_OWNER = "recruiter@racedog.test"

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
	# HR reviews monthly timesheets + runs the compliance report.
	("hr@racedog.test", "Harper", "HR", ["HR Manager"]),
]

# A consultant login so the self-service Consultant Home is explorable. Linked to
# the first seeded consultant (Priya Nair) — she lands on /app/consultant-home and
# sees only her own record (rate/margin never exposed).
DEMO_CONSULTANT = ("priya@racedog.test", "Priya", "Nair", "Priya Nair")


def seed():
	frappe.set_user("Administrator")
	_run("prereqs", _prereqs)
	_run("company", _company)
	_run("finish_setup", _finish_setup)
	_run("masters", _masters)
	_run("users", _users)  # before consultants so marketing_owner resolves
	consultants = _run("consultants", _consultants) or []
	_run("documents", lambda: _documents(consultants))
	requirements = _run("requirements", _requirements) or []
	_run("submissions", lambda: _submissions(consultants, requirements))
	_run("users", _users)
	_run("consultant_login", _consultant_login)
	_run("timesheets", _timesheets)
	summary = {
		"company": frappe.db.count("Company"),
		"consultants": frappe.db.count("Employee", {"status": "Active"}),
		"requirements": frappe.db.count("Client Requirement"),
		"submissions": frappe.db.count("Submission"),
		"users": [u[0] for u in DEMO_USERS if frappe.db.exists("User", u[0])],
		"consultant_login": DEMO_CONSULTANT[0] if frappe.db.exists("User", DEMO_CONSULTANT[0]) else None,
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
	for i, row in enumerate(CONSULTANTS):
		first, last, gender, skill, visa, status, hotlist, avail_offset, bill, pay, client = row
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
					"personal_email": f"{first.lower()}.{last.lower()}@example.com",
					"cell_number": f"+1 (312) 555-01{i:02d}",
					"deployment_status": status,
					"hotlist": hotlist,
					"current_client": client,
					"marketing_owner": DEMO_MARKETING_OWNER
					if frappe.db.exists("User", DEMO_MARKETING_OWNER)
					else None,
					"primary_skill": skill,
					"consultant_skills": [{"skill": skill}],
					"visa_status": visa,
					"visa_expiry": add_days(nowdate(), 120),
					"availability_date": add_days(nowdate(), avail_offset),
					"bench_start_date": add_days(nowdate(), min(avail_offset, 0)),
				}
			).insert(ignore_permissions=True)
			created.append(doc.name)
			# Rates live on the manager-only Consultant Billing DocType, not Employee.
			if not frappe.db.exists("Consultant Billing", doc.name):
				frappe.get_doc(
					{
						"doctype": "Consultant Billing",
						"consultant": doc.name,
						"bill_rate": bill,
						"pay_rate": pay,
					}
				).insert(ignore_permissions=True)
		except Exception as e:
			print(f"  consultant {first} {last} skipped: {repr(e)[:160]}")
	return created


def _documents(consultants):
	"""Attach sample private docs (resume, work-auth) to a few consultants so the
	recruiter download flow has something real to pull."""
	if not consultants:
		return
	samples = (
		("Resume", "resume.txt", "SAMPLE RESUME\n8+ yrs, cloud + backend engineering. (demo file)"),
		("Work Authorization (EAD/I-797)", "work_auth.txt", "SAMPLE I-797 approval notice. (demo file)"),
	)
	for emp in consultants[:3]:
		doc = frappe.get_doc("Employee", emp)
		if doc.get("documents"):
			continue
		try:
			for dtype, fname, content in samples:
				f = frappe.get_doc(
					{
						"doctype": "File",
						"file_name": f"{emp}-{fname}",
						"attached_to_doctype": "Employee",
						"attached_to_name": emp,
						"is_private": 1,
						"content": content,
					}
				).insert(ignore_permissions=True)
				doc.append(
					"documents",
					{"document_type": dtype, "document": f.file_url, "uploaded_on": nowdate()},
				)
			doc.save(ignore_permissions=True)
		except Exception as e:
			print(f"  documents for {emp} skipped: {repr(e)[:160]}")


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
	# bench consultant submissions
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
					"source": "Bench Consultant",
					"consultant": consultant,
					"requirement": requirement,
					"status": "Submitted",
				}
			).insert(ignore_permissions=True)
		except Exception as e:
			print(f"  submission skipped: {repr(e)[:160]}")

	# external candidate (middle-vendor) submission
	if len(requirements) > 2 and not frappe.db.exists("Submission", {"external_name": "Ganesh Iyer"}):
		try:
			frappe.get_doc(
				{
					"doctype": "Submission",
					"source": "External Candidate",
					"requirement": requirements[2],
					"external_name": "Ganesh Iyer",
					"external_email": "ganesh.iyer@example.com",
					"external_phone": "+1 (469) 555-0142",
					"external_work_auth": "H1B",
					"external_employer": "Third-Party Tek LLC",
					"status": "Submitted",
				}
			).insert(ignore_permissions=True)
		except Exception as e:
			print(f"  external submission skipped: {repr(e)[:160]}")


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


# consultant, months back, status, hours — seeded so HR has something to review and
# the compliance report shows a real mix (submitted vs missing).
DEMO_TIMESHEETS = [
	("Priya Nair", 2, "Approved", 168),
	("Priya Nair", 1, "Submitted", 160),
	("Sofia Reyes", 1, "Approved", 176),
]


def _timesheets():
	"""Seed monthly timesheets (real PDFs) for the HR review + compliance demo.

	Also places Sofia on a client so the compliance report has two deployed
	consultants — one who submitted and one (Liam) who hasn't = a MISSING row.
	"""
	try:
		import base64
		import io

		from pypdf import PdfWriter

		writer = PdfWriter()
		writer.add_blank_page(width=200, height=200)
		buf = io.BytesIO()
		writer.write(buf)
		pdf_b64 = base64.b64encode(buf.getvalue()).decode()
	except Exception as e:
		print(f"  timesheets skipped (no pypdf): {repr(e)[:120]}")
		return

	# Deploy Sofia so the compliance report isn't a single row.
	sofia = frappe.db.get_value("Employee", {"employee_name": "Sofia Reyes"}, "name")
	if sofia and frappe.db.exists("Client", "Meridian Health"):
		frappe.db.set_value(
			"Employee", sofia, {"deployment_status": "Working", "current_client": "Meridian Health"}
		)

	first_of_month = getdate(nowdate()).replace(day=1)
	for name, months_back, status, hours in DEMO_TIMESHEETS:
		emp = frappe.db.get_value("Employee", {"employee_name": name}, "name")
		if not emp:
			continue
		period = getdate(add_months(first_of_month, -months_back)).strftime("%Y-%m")
		if frappe.db.exists("Consultant Timesheet", {"consultant": emp, "period_month": period}):
			continue
		try:
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"TS-{emp}-{period}.pdf",
					"is_private": 1,
					"content": pdf_b64,
					"decode": True,
				}
			).insert(ignore_permissions=True)
			ts = frappe.get_doc(
				{
					"doctype": "Consultant Timesheet",
					"consultant": emp,
					"period_month": period,
					"signed_pdf": file_doc.file_url,
					"total_hours": hours,
					"status": status,
				}
			).insert(ignore_permissions=True)
			file_doc.db_set(
				{"attached_to_doctype": "Consultant Timesheet", "attached_to_name": ts.name}
			)
			if status == "Approved":
				frappe.db.set_value(
					"Consultant Timesheet",
					ts.name,
					{"reviewed_by": "hr@racedog.test", "reviewed_on": now_datetime()},
				)
		except Exception as e:
			print(f"  timesheet {name} {period} skipped: {repr(e)[:160]}")


def _consultant_login():
	"""Create a consultant login (Employee role) and link it to Priya Nair.

	Proves the self-service surface end to end: this user lands on
	/app/consultant-home, sees only her own record, and can never read a rate.
	"""
	email, first, last, emp_name = DEMO_CONSULTANT
	if not frappe.db.exists("User", email):
		try:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first,
					"last_name": last,
					"send_welcome_email": 0,
					"user_type": "System User",
					"roles": [{"role": "Employee"}],
				}
			)
			user.new_password = DEMO_PASSWORD
			user.insert(ignore_permissions=True)
		except Exception as e:
			print(f"  consultant user {email} skipped: {repr(e)[:160]}")
	emp = frappe.db.get_value("Employee", {"employee_name": emp_name}, "name")
	if emp and frappe.db.exists("User", email):
		frappe.db.set_value("Employee", emp, "user_id", email)


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


def _finish_setup():
	"""Mark ERPNext setup complete so the (janky) setup wizard never blocks login.

	The site is created with desktop:home_page = "setup-wizard"; since we bypass the
	wizard, that default routes every login through the wizard (the "flashing"). Point
	it at the board and mark onboarding complete so nothing flashes.
	"""
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_single_value("Global Defaults", "default_currency", "USD")
	frappe.db.set_default("currency", "USD")
	frappe.db.set_default("desktop:home_page", "bench-board")
	frappe.db.sql("update `tabModule Onboarding` set is_complete=1")
	if not frappe.db.exists("Fiscal Year", "2026"):
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": "2026",
				"year_start_date": "2026-01-01",
				"year_end_date": "2026-12-31",
			}
		).insert(ignore_permissions=True)
	if frappe.db.exists("Company", COMPANY):
		frappe.db.set_single_value("Global Defaults", "default_company", COMPANY)


def verify():
	"""Prove the rate firewall: ONLY managers read rates (Consultant Billing), and the
	permlevel WHERE/ORDER-BY side-channel is closed (rate fields no longer on Employee).

	Run: from racedog_hr.demo import verify; verify()
	"""
	report = {}

	frappe.set_user("recruiter@racedog.test")
	from racedog_hr.api import get_bench

	bench = get_bench()
	report["recruiter_bench_rows"] = len(bench["data"])
	report["recruiter_api_leaks_rate"] = any("rate" in key for row in bench["data"] for key in row)
	report["recruiter_billing_read"] = _peek_rate()  # expect BLOCKED
	report["recruiter_sidechannel"] = _sidechannel_status()  # expect closed

	frappe.set_user("hr@racedog.test")
	report["hr_billing_read"] = _peek_rate()  # expect BLOCKED (HR no longer sees rates)

	frappe.set_user("manager@racedog.test")
	report["manager_billing_read"] = _peek_rate()  # expect VISIBLE

	if frappe.db.exists("User", DEMO_CONSULTANT[0]):
		frappe.set_user(DEMO_CONSULTANT[0])
		from racedog_hr.api import get_my_profile, get_bench as _get_bench

		try:
			profile = get_my_profile()["data"]
			report["consultant_profile_name"] = profile.get("employee_name")
			report["consultant_profile_leaks_rate"] = any("rate" in k or k == "margin" for k in profile)
		except Exception as e:
			report["consultant_profile"] = f"ERROR({type(e).__name__})"
		report["consultant_employees_visible"] = len(frappe.get_list("Employee", limit=0))
		report["consultant_billing_read"] = _peek_rate()  # expect BLOCKED
		report["consultant_sidechannel"] = _sidechannel_status()  # expect closed
		try:
			_get_bench()
			report["consultant_board_blocked"] = False
		except frappe.exceptions.PermissionError:
			report["consultant_board_blocked"] = True

	frappe.set_user("Administrator")
	print("VERIFY:", report)
	return report


def _peek_rate():
	"""What bill_rate the current user can read from Consultant Billing (or how blocked)."""
	try:
		rows = frappe.get_list(
			"Consultant Billing", fields=["name", "bill_rate"], limit=1, order_by="creation asc"
		)
	except frappe.exceptions.PermissionError:
		return "BLOCKED(PermissionError)"
	except Exception as e:
		return f"BLOCKED({type(e).__name__})"
	if not rows:
		return "no-rows"
	value = rows[0].get("bill_rate")
	return "hidden" if value in (None, 0) else f"VISIBLE({value})"


def _sidechannel_status():
	"""Confirm the old permlevel WHERE side-channel is dead: filtering Employee by a
	rate field must now error (the column no longer exists). 'closed' = good.
	"""
	try:
		frappe.get_list("Employee", filters={"current_bill_rate": [">=", 100]}, limit=1)
		return "OPEN(still filterable!)"
	except Exception:
		return "closed"


def reset():
	"""Wipe demo submissions + consultants and re-seed fresh (for a clean demo refresh).

	Run: from racedog_hr.demo import reset; reset()
	"""
	frappe.set_user("Administrator")
	frappe.db.delete("Submission")
	for name in frappe.get_all("Employee", pluck="name"):
		try:
			frappe.delete_doc("Employee", name, force=1, ignore_permissions=True)
		except Exception as ex:
			print(f"  could not delete {name}: {repr(ex)[:120]}")
	frappe.db.commit()
	return seed()
