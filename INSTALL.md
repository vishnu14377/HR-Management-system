# Install & Run

`racedog_hr` is a Frappe app that installs on a bench that already has **Frappe** +
**Frappe HRMS**. Below: a local dev bench (Docker), a production self-host on a VPS,
and post-install setup + verification.

---

## Prerequisites

- A Frappe **v15** bench with `frappe` and `hrms` installed.
- Python ≥ 3.10, Node ≥ 18, MariaDB 10.6+, Redis.
- This repo pushed to `https://github.com/vishnu14377/HR-Management-system.git`
  (that's where `bench get-app` pulls the `racedog_hr` app from).

---

## Option A — Local dev bench with frappe_docker (fastest to try)

Requires Docker Desktop running.

```bash
# 1. Clone frappe_docker
git clone https://github.com/frappe/frappe_docker
cd frappe_docker

# 2. Bring up the dev containers (Frappe + MariaDB + Redis)
cp -R devcontainer-example .devcontainer
# open in VS Code devcontainer, OR run the pwd.yml compose for a quick single-site:
docker compose -f pwd.yml up -d
```

The `pwd.yml` image ships ERPNext, not our stack. For a HRMS + racedog_hr bench, use
the **dev container** flow and inside it:

```bash
bench init --frappe-branch version-15 frappe-bench && cd frappe-bench
bench new-site racedog.localhost --admin-password admin --mariadb-root-password root

# HRMS (use your fork so customizations track one HRMS source)
bench get-app --branch version-15 hrms https://github.com/vishnu14377/hrms.git
bench --site racedog.localhost install-app hrms

# racedog_hr
bench get-app racedog_hr https://github.com/vishnu14377/HR-Management-system.git
bench --site racedog.localhost install-app racedog_hr
bench --site racedog.localhost migrate

bench start   # http://racedog.localhost:8000
```

> Local-only convenience: from the repo you're reading, you can also symlink the app
> into an existing bench instead of `get-app`:
> `bench get-app /absolute/path/to/HR-Management-system` then `install-app racedog_hr`.

---

## Option B — Production self-host on a VPS (the plan's chosen path)

Baseline VM: **≥ 4 GB RAM / 2 vCPU** (8 GB comfortable at 25–100 users), Ubuntu 22.04+.

```bash
# 1. Provision the bench (frappe_docker production compose or a bare-metal bench).
#    frappe_docker production: https://github.com/frappe/frappe_docker/blob/main/docs/
git clone https://github.com/frappe/frappe_docker && cd frappe_docker
# configure env, then:
docker compose -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml up -d      # HTTPS via Traefik/Let's Encrypt

# 2. Create the site
bench new-site racedog.example.com --install-app erpnext

# 3. Install HRMS (your fork) and racedog_hr
bench get-app --branch version-15 hrms https://github.com/vishnu14377/hrms.git
bench --site racedog.example.com install-app hrms
bench get-app racedog_hr https://github.com/vishnu14377/HR-Management-system.git
bench --site racedog.example.com install-app racedog_hr
bench --site racedog.example.com migrate
```

**Self-host go-live obligations (from the plan — do these before real data):**

```bash
# Automated nightly backup incl. files, pushed OFF the box (S3/rclone/etc.)
bench --site racedog.example.com backup --with-files
# ... wire this into cron/systemd-timer + off-box upload, and REHEARSE a restore:
bench --site racedog.example.com --force restore /path/to/backup.sql.gz --with-public-files ... 

# TLS must be live before any rate/PII is entered (handled by compose.https override).
```

---

## Post-install setup

1. **Assign roles** to your users (Users → each user → Roles):
   `Recruiter`, `Bench Sales`, `Recruiting Manager`, `Account Manager`.
   Managers/HR who should see rates need `Recruiting Manager` or `HR Manager`.

2. **Seed masters** (Bench & Requirements workspace → Data):
   - `Work Authorization`: USC, GC, GC-EAD, H1B, H4-EAD, OPT-EAD, CPT, TN, L2-EAD.
   - `Skill`: your common tech stack.
   - `Client`, `Vendor`: as you go.

3. **Backfill consultants**: on each `Employee`, set `deployment_status`,
   `primary_skill`, `visa_status`/`visa_expiry`, `availability_date`, `marketing_owner`.
   Rates go in the manager-only section.

4. Open the **Bench & Requirements** workspace — the bench list, open-req board,
   and number cards are the recruiter landing surface.

---

## Verify (matches the plan's go-live gates)

Run `bench --site <site> console` or click through the Desk:

- **Fixtures re-apply**: `bench --site <site> migrate` twice — second run is clean.
- **Rate firewall (critical)**: log in as a `Recruiter` and confirm `Bill Rate`,
  `Pay Rate`, and margin are **absent** on the Employee form, Client Requirement,
  Submission, in list/report view, and via the REST API
  (`/api/method/frappe.client.get_list?doctype=Employee&fields=["current_bill_rate"]`
  should not return the value).
- **Double-submission**: create a `Submission`, then a second one with the same
  consultant + requirement → it is blocked. Same consultant + same client via a
  different requirement → RTR warning.
- **Soft-close**: set a `Client Requirement` to `Filled` → it leaves the Open board
  (status filter) but the record persists with `closed_on`.
- **Alerts**: set a `visa_expiry` 30 days out and run
  `bench --site <site> execute racedog_hr.tasks.check_visa_expiry` → owner + HR get a
  bell notification.
- **Indexes**: after migrate, `SHOW INDEX FROM tabSubmission;` includes
  `consultant_requirement`.

---

## Upgrading HRMS later

```bash
bench update --apps hrms          # racedog_hr is untouched; no merge conflicts
bench --site <site> migrate       # re-applies racedog_hr fixtures
```

Test upgrades on a staging bench first.
