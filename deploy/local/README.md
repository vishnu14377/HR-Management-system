# Local Docker run (version-15)

These files reproduce the full local stack (Frappe + ERPNext + HRMS + racedog_hr)
used to develop/verify the app. It runs on the **version-15** line for stability.

Files:
- `apps.base.json` — public apps baked into the base image (erpnext, hrms).
- `Dockerfile.racedog` — derived image: adds `racedog_hr` on top of the base via `bench get-app`.
- `racedog.yml` — compose stack (backend, frontend, workers, scheduler, db, redis) on port 8080.

## Build + run

```bash
# 1. Base image (Frappe v15 + ERPNext + HRMS). ~20-40 min the first time.
git clone --depth 1 https://github.com/frappe/frappe_docker && cd frappe_docker
cp /path/to/deploy/local/apps.base.json apps.json
DOCKER_BUILDKIT=1 docker build \
  --secret id=apps_json,src=apps.json \
  --build-arg FRAPPE_BRANCH=version-15 \
  --build-arg PYTHON_VERSION=3.11.9 \
  --build-arg NODE_VERSION=18.20.4 \
  --build-arg INSTALL_CHROMIUM=false \
  --tag racedog-base:latest --file images/custom/Containerfile .

# 2. Derived image (adds racedog_hr from the public repo). ~2-3 min.
mkdir -p /tmp/derived && cp /path/to/deploy/local/Dockerfile.racedog /tmp/derived/Dockerfile
docker build --no-cache -t racedog-hr:latest -f /tmp/derived/Dockerfile /tmp/derived

# 3. Bring up the stack + create the site (installs all three apps).
cp /path/to/deploy/local/racedog.yml .
docker compose -f racedog.yml up -d
docker compose -f racedog.yml logs -f create-site   # wait until it finishes
```

## First-run gotchas already handled in code

On a fresh ERPNext site the setup wizard hasn't run, so a few default records are
missing. The demo seeder (`racedog_hr/demo.py`) creates the `Transit` warehouse
type and `Gender` records before it needs them. If you seed manually:

```bash
docker compose -f racedog.yml exec backend bench --site frontend console
>>> from racedog_hr.demo import seed, verify
>>> seed()      # company, masters, 8 consultants, 5 requirements, 2 users
>>> verify()    # proves the rate firewall (recruiter hidden / manager visible)
```

## Notes

- This uses **upstream** frappe/erpnext/hrms at `version-15` for a stable demo.
  Production should install HRMS from your fork (`vishnu14377/hrms`) per the root
  `INSTALL.md`; the custom app is identical either way.
- `racedog_hr` is private-repo-safe: the derived image pulls it over HTTPS, so the
  repo must be public OR you supply a git credential to the build.
