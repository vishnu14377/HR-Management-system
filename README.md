# racedog_hr

A recruiting-coordination layer for **RaceDog Technologies**, built as a custom
[Frappe](https://frappeframework.com) app on top of [Frappe HRMS](https://github.com/frappe/hrms).

It turns two things every recruiter currently has to ask a manager for into shared,
live, filterable sources of truth:

- **Bench List** — every consultant with a deployment status (On Bench / Marketing /
  Interviewing / Placed / …), skills, work authorization, and availability date. It's a
  native filtered view of the HRMS `Employee` master, so no new data silo.
- **Open Requirements board** — client positions recruiters post and soft-close when
  filled (`Client Requirement`), with client/vendor chain, location, and skills.
- **Submission tracking** — `Submission` links a consultant to a requirement and
  **blocks double-submission** + warns on right-to-represent (RTR) conflicts.

Rate and margin fields live at **permission level 1** — recruiters never see them,
managers do. Work-authorization expiry and bench availability fire scheduled alerts.

## Why a separate app (not a fork of HRMS)

`racedog_hr` installs alongside `frappe` + `hrms`. It only adds custom DocTypes,
Custom Fields, permissions, notifications, and one workspace — it never edits HRMS
core. That keeps HRMS upgradeable (`bench update`) with zero merge conflicts, and the
whole customization travels as fixtures so it re-applies on `bench migrate`.

## What's in here

| Area | DocTypes / artifacts |
|---|---|
| Open positions | `Client Requirement` (+ `Requirement Vendor Chain` child) |
| Submissions | `Submission` (double-submission + RTR guard) |
| Bench / consultants | Custom Fields on `Employee` (`deployment_status`, `visa_status`, rates @permlevel 1, …) |
| Masters | `Client`, `Vendor`, `Skill`, `Work Authorization` |
| Roles | `Recruiter`, `Bench Sales`, `Recruiting Manager`, `Account Manager` |
| Surfaces | `Bench & Requirements` workspace, 3 number cards, 3 notifications |
| Alerts | daily `check_visa_expiry`, `check_bench_availability` |

## Install

See **[INSTALL.md](INSTALL.md)** for the full bench + Docker walkthrough and
**[SECURITY.md](SECURITY.md)** for the permission model and go-live verification.

Quick version, on an existing bench that has `hrms` installed:

```bash
cd frappe-bench
bench get-app racedog_hr https://github.com/vishnu14377/HR-Management-system.git
bench --site your-site.local install-app racedog_hr
bench --site your-site.local migrate
```

## License

MIT — see [LICENSE](LICENSE).
