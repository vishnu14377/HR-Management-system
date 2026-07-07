# Copyright (c) 2026, RaceDog Technologies and contributors
"""Idempotent demo-data seeder. Run: bench --site <site> execute racedog_hr.demo.seed

Creates a company, staffing masters, consultants on the bench, open client
requirements, a couple of submissions, and two demo logins (a recruiter who
cannot see rates, and a manager who can) so the app is immediately explorable.
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

# name, gender, skill, visa, deployment_status, days_until_available, bill, pay
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
	_company()
	_masters()
	consultants = _consultants()
	requirements = _requirements()
	_submissions(consultants, requirements)
	_users()
	frappe.db.commit()
	summary = {
		"company": COMPANY,
		"consultants": len(consultants),
		"requirements": len(requirements),
		"users": [u[0] for u in DEMO_USERS],
		"password": DEMO_PASSWORD,
	}
	print("SEED DONE:", summary)
	return summary


def _company():
	if not frappe.db.exists("Company", COMPANY):
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
		if not frappe.db.exists("Work Authorization", name):
			frappe.get_doc(
				{"doctype": "Work Authorization", "work_auth": name, "requires_sponsorship": sponsor}
			).insert(ignore_permissions=True)
	for name, category in SKILLS:
		if not frappe.db.exists("Skill", name):
			frappe.get_doc({"doctype": "Skill", "skill_name": name, "category": category}).insert(
				ignore_permissions=True
			)
	for name in CLIENTS:
		if not frappe.db.exists("Client", name):
			frappe.get_doc({"doctype": "Client", "client_name": name, "status": "Active"}).insert(
				ignore_permissions=True
			)
	for name, vtype in VENDORS:
		if not frappe.db.exists("Vendor", name):
			frappe.get_doc(
				{"doctype": "Vendor", "vendor_name": name, "vendor_type": vtype, "status": "Active"}
			).insert(ignore_permissions=True)


def _consultants():
	created = []
	for first, last, gender, skill, visa, status, avail_offset, bill, pay in CONSULTANTS:
		existing = frappe.db.get_value("Employee", {"employee_name": f"{first} {last}"})
		if existing:
			created.append(existing)
			continue
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
	return created


def _requirements():
	created = []
	for title, client, skill, priority, location, work_mode, max_bill in REQUIREMENTS:
		existing = frappe.db.get_value("Client Requirement", {"title": title, "client": client})
		if existing:
			created.append(existing)
			continue
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
	return created


def _submissions(consultants, requirements):
	if not consultants or not requirements:
		return
	pairs = [(consultants[0], requirements[0]), (consultants[2], requirements[1])]
	for consultant, requirement in pairs:
		if frappe.db.exists("Submission", {"consultant": consultant, "requirement": requirement}):
			continue
		frappe.get_doc(
			{
				"doctype": "Submission",
				"consultant": consultant,
				"requirement": requirement,
				"status": "Submitted",
			}
		).insert(ignore_permissions=True)


def _users():
	for email, first, last, roles in DEMO_USERS:
		if frappe.db.exists("User", email):
			continue
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
