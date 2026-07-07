# It's running — how to use it

A full stack (Frappe + ERPNext + HRMS + **racedog_hr**) is running locally in Docker,
seeded with demo data. Screenshots are on your Desktop in `racedog-demo-screenshots/`.

## Open it

**http://localhost:8080**

| Login | Password | Sees rates? |
|---|---|---|
| `Administrator` | `admin` | yes (admin) |
| `manager@racedog.test` | `racedog123` | **yes** (Recruiting Manager) |
| `recruiter@racedog.test` | `racedog123` | **no** (rate firewall) |

## Where to look

- **Bench Board** (the custom recruiter UI): http://localhost:8080/app/bench-board
  Consultant cards with status pills, skill/visa tags, filters, and drag-to-requirement.
- **Bench & Requirements** workspace (sidebar): number cards + shortcuts + doctype links.
- **Client Requirement**, **Submission**, **Employee**: standard Desk lists (try filtering
  Employee by Deployment Status).

## See the rate firewall yourself

1. Log in as `recruiter@racedog.test` → open any consultant (Employee) → there is **no**
   "Consultant Rates" section, and the Bench Board shows no rates.
2. Log in as `manager@racedog.test` → same consultant shows **Consultant Rates (Manager
   Only)** with Bill/Pay rate.

## Demo data loaded

1 company (RaceDog Technologies), 8 consultants across bench statuses, 5 open client
requirements, 2 submissions, plus the two demo logins.

Re-seed or re-verify anytime:
```bash
# from the frappe_docker dir that has racedog.yml (see deploy/local/)
docker compose -f racedog.yml exec backend bench --site frontend console
>>> from racedog_hr.demo import seed, verify
>>> seed(); verify()
```

## Manage the stack

```bash
docker ps                                   # see the fd-* containers
docker compose -f racedog.yml ps            # (from the frappe_docker dir)
docker compose -f racedog.yml stop          # pause
docker compose -f racedog.yml start         # resume
docker compose -f racedog.yml logs -f backend
```

Data persists in Docker volumes (`sites`, `db-data`) across stop/start.

## This is a local demo

It runs on **version-15** with upstream frappe/erpnext/hrms + `racedog_hr` from the
`feat/racedog-hr-app` branch. For production on your VPS with your own HRMS fork, follow
[INSTALL.md](INSTALL.md). Reproduce this local stack from [deploy/local/](deploy/local/).
