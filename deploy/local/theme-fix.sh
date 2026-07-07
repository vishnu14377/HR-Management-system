#!/usr/bin/env bash
# Re-link the racedog_hr assets after a full `docker compose up --force-recreate`.
# frappe_docker keeps app assets per-container under frappe-bench/assets (not the
# shared sites volume), so a custom app's asset symlink must be (re)created in both
# the backend (to resolve app_include_css) and the frontend (to serve it).
set -e
COMPOSE="${1:-racedog.yml}"
APP_PUBLIC=/home/frappe/frappe-bench/apps/racedog_hr/racedog_hr/public
LINK=/home/frappe/frappe-bench/sites/assets/racedog_hr

docker compose -f "$COMPOSE" exec -T backend bench build --app racedog_hr
docker compose -f "$COMPOSE" exec -T backend bash -c "ln -sfn $APP_PUBLIC $LINK"

# sync backend's freshly-built dist to the frontend so hashes match, + link it
TMP=$(mktemp -d)
docker cp "$(docker compose -f "$COMPOSE" ps -q backend):$APP_PUBLIC/dist/." "$TMP/"
docker cp "$TMP/." "$(docker compose -f "$COMPOSE" ps -q frontend):$APP_PUBLIC/dist/"
docker compose -f "$COMPOSE" exec -T frontend bash -c "ln -sfn $APP_PUBLIC $LINK"
docker compose -f "$COMPOSE" exec -T backend bench --site frontend clear-cache
rm -rf "$TMP"
echo "Theme assets re-linked. Hard-refresh the browser."
