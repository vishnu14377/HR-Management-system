# It's running — how to use it

A full stack (Frappe + ERPNext + HRMS + **racedog_hr**) is running locally in Docker,
tailored for a pure IT-outsourcing consulting firm, given a **BambooHR-inspired green
theme**, and seeded with demo data. Screenshots are on your Desktop in
`racedog-demo-screenshots/`.

> The old "setup wizard flashing" is fixed for good — the site's home page was pointing
> at the wizard; it now lands on the Bench Board. If the theme ever looks unstyled after
> a full container **recreate**, run `deploy/local/theme-fix.sh` once (frappe_docker keeps
> custom-app assets per-container). Normal stop/start keeps everything.

## Open it

**http://localhost:8080**

| Login | Password | Sees rates/margin? | Lands on |
|---|---|---|---|
| `recruiter@racedog.test` | `racedog123` | **no** (firewall) | Bench Board |
| `manager@racedog.test` | `racedog123` | **yes** | Bench Board |
| `hr@racedog.test` | `racedog123` | **no** (HR — reviews timesheets) | Desk |
| `priya@racedog.test` | `racedog123` | **no** (own record only) | My Home (consultant portal) |
| `Administrator` | `admin` | yes (admin) | full desk |

> If a page ever flickers or looks stale, hard-refresh (`Cmd+Shift+R`) or log out/in —
> that's browser cache, not the app.

### Give a consultant a login (onboarding)

A consultant can only reach their self-service portal once their Employee record is
linked to a user account. To do it in one click: open the consultant's **Employee**
record as a manager/recruiter → **Actions → Create Portal Login**. That creates the
login (with the Employee role), links it, and shows a temporary password to share.
On next login they land straight on their **My Home** portal. (Only `priya@racedog.test`
is pre-linked in the demo; use the button to onboard the rest.)

## What the recruiting team gets

- **Bench Board** (`/app/bench-board`) — the daily dashboard. Consultant cards show
  **name, email, phone, current client, status**, with a **hotlist traffic light**:
  🔴 Red = top priority (market now), 🟠 Orange = has bandwidth / casual, 🟢 Green = not
  looking. Sorted Red→Orange→Green. Filter by status (Bench / All / Working / On Bench /
  Marketing), hotlist, skill, work-auth. "Market" a consultant onto an open requirement.
- **Common Job Board** — `Client Requirement`. **Any recruiter can post / edit / delete /
  update any requirement.** `Filled Via` records Internal Bench vs External Candidate.
- **Employee (consultant) master** — managers create/update/delete; **documents** (resume,
  visa, DL, ...) attach here and **recruiters can download them**. Rates (bill/pay/margin)
  are manager-only. Status = Working / On Bench / Marketing; hotlist auto-locks to Green
  while Working.
- **Submissions** — bench consultant *or* external candidate (middle-vendor) via a `Source`
  flag; blocks double-submission; auto-fills the requirement when Placed.
- **Monthly timesheets** — a consultant uploads their client-signed timesheet **PDF** from
  the *My Timesheets* section of their portal (one per month; re-upload replaces in place).
  It routes to **HR** (`hr@racedog.test`), who Approves or Rejects-with-reason from the
  `Consultant Timesheet` form; the consultant is notified either way and can resubmit. HR
  runs the **Timesheet Compliance** report to see, per client, who's submitted vs **missing**
  for a month. No rates ever appear on this surface; consultants see only their own.

Recruiters see **only** the "Bench & Requirements" workspace — all the ERPNext/HRMS
clutter (Accounting, Projects, Manufacturing, Stock, Payroll, etc.) is hidden.

## See the model working

- Log in as **recruiter** → Bench Board shows 6 bench consultants, hotlist-colored, **no
  rates**. Click "All" to see Working consultants with their current client.
- Log in as **manager** → open a consultant → **Billing (Manager Only)** shows Bill Rate,
  Pay Rate, and auto-computed **Margin**; the **Documents** table is uploadable.

## Demo data

1 company, 8 consultants (mix of Working / On Bench / Marketing, red/orange/green hotlist),
5 open requirements, 3 submissions (2 bench + 1 external candidate).

Refresh it anytime (from the frappe_docker dir with `racedog.yml`):
```bash
docker compose -f racedog.yml exec backend bench --site frontend console
>>> from racedog_hr.demo import reset, verify
>>> reset()    # clean wipe + reseed for the current model
>>> verify()   # proves the rate firewall (recruiter hidden / manager visible)
```

## Manage the stack

```bash
docker ps                                   # the fd-* containers
docker compose -f racedog.yml stop|start    # pause / resume (data persists in volumes)
docker compose -f racedog.yml logs -f backend
```

## Production

Local demo runs on **version-15** (upstream frappe/erpnext/hrms + `racedog_hr`). For your
VPS with your own HRMS fork, see [INSTALL.md](INSTALL.md); reproduce this stack from
[deploy/local/](deploy/local/). Security model + go-live gates: [SECURITY.md](SECURITY.md).
