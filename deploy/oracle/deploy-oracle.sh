#!/usr/bin/env bash
#
# One-shot production deploy of racedog_hr (Frappe + ERPNext + HRMS) onto a fresh
# Ubuntu 22.04 ARM VM — built for the Oracle Cloud Always-Free Ampere shape, but
# works on any Ubuntu 22.04 arm64/amd64 host.
#
# Run it AS the default 'ubuntu' user on the fresh box:
#     bash deploy-oracle.sh
#
# It is safe to re-run (idempotent-ish): it skips Docker if present, rebuilds the
# image, and only creates the site if it doesn't already exist.
#
# Uses `sudo docker` throughout so it works on the very first run, before your
# user's docker-group membership has taken effect.
set -euo pipefail

# ============================ EDIT THESE ============================
SITE="hr.racedogtechnologies.com"          # your subdomain (DNS A record -> this VM)
LE_EMAIL="admin@racedogtechnologies.com"   # for the free Let's Encrypt certificate
DB_PASSWORD="CHANGE_ME_db_password"        # MariaDB root password (make it strong)
ADMIN_PASSWORD="CHANGE_ME_admin_password"  # Frappe 'Administrator' login password
APP_REPO="https://github.com/vishnu14377/HR-Management-system"
APP_BRANCH="feat/racedog-hr-app"
# ===================================================================

FRAPPE_BRANCH="version-15"
IMAGE="racedog-hr"
TAG="latest"
COMPOSE="$HOME/racedog-compose.yml"
D="sudo docker"

if [[ "$DB_PASSWORD" == CHANGE_ME* || "$ADMIN_PASSWORD" == CHANGE_ME* ]]; then
  echo "!! Edit SITE / LE_EMAIL / DB_PASSWORD / ADMIN_PASSWORD at the top first." >&2
  exit 1
fi

echo "==> 1/7  Docker + system packages"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
sudo apt-get update -y
sudo apt-get install -y git netfilter-persistent iptables-persistent >/dev/null 2>&1 || true

echo "==> 2/7  Open ports 80/443 on the box (Oracle Ubuntu blocks them by default)"
sudo iptables -I INPUT -p tcp --dport 80  -j ACCEPT || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
sudo netfilter-persistent save || true

echo "==> 3/7  Fetch frappe_docker"
cd "$HOME"
[ -d frappe_docker ] || git clone --depth 1 https://github.com/frappe/frappe_docker
cd frappe_docker

echo "==> 4/7  Build the custom image (frappe+erpnext+hrms+racedog_hr, v15) — ~25-40 min"
# The custom Containerfile takes the app list as a BuildKit secret (apps.json),
# not a build-arg. Python/Node are pinned to v15-compatible versions (the image's
# defaults now target v16). This mirrors the proven recipe in deploy/local/README.md.
cat > apps.json <<EOF
[
  {"url": "https://github.com/frappe/erpnext", "branch": "$FRAPPE_BRANCH"},
  {"url": "https://github.com/frappe/hrms", "branch": "$FRAPPE_BRANCH"},
  {"url": "$APP_REPO", "branch": "$APP_BRANCH"}
]
EOF
# CACHE_BUST forces the app-install layer to re-run. Without it, BuildKit reuses a
# cached `bench init` layer even when apps.json changes (secret content is NOT part
# of the cache key), which would silently drop racedog_hr or ship stale app code.
sudo env DOCKER_BUILDKIT=1 docker build \
  --secret id=apps_json,src=apps.json \
  --build-arg FRAPPE_BRANCH="$FRAPPE_BRANCH" \
  --build-arg PYTHON_VERSION=3.11.9 \
  --build-arg NODE_VERSION=18.20.4 \
  --build-arg INSTALL_CHROMIUM=false \
  --build-arg CACHE_BUST="$(date +%s)" \
  --tag "$IMAGE:$TAG" \
  --file images/custom/Containerfile .

echo "==> 5/7  Generate compose (MariaDB + Redis + Traefik/HTTPS) and start"
# .env — note SITES uses literal backticks for Traefik's Host() rule.
{
  echo "DB_PASSWORD=$DB_PASSWORD"
  echo "CUSTOM_IMAGE=$IMAGE"
  echo "CUSTOM_TAG=$TAG"
  echo "PULL_POLICY=never"
  echo "SITES=\`$SITE\`"
  echo "LETSENCRYPT_EMAIL=$LE_EMAIL"
} > .env

sudo docker compose --project-name racedog \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.https.yaml \
  --env-file .env config > "$COMPOSE"

$D compose -f "$COMPOSE" up -d
echo "    waiting for the database to accept connections..."
sleep 25

echo "==> 6/7  Create the site + install apps (racedog_hr after_migrate hooks run here)"
if $D compose -f "$COMPOSE" exec -T backend test -d "sites/$SITE" 2>/dev/null; then
  echo "    site $SITE already exists — skipping create."
else
  $D compose -f "$COMPOSE" exec -T backend \
    bench new-site "$SITE" \
      --no-mariadb-socket \
      --mariadb-root-password "$DB_PASSWORD" \
      --admin-password "$ADMIN_PASSWORD" \
      --install-app erpnext --install-app hrms --install-app racedog_hr \
      --set-default
fi

echo "==> 7/7  Build racedog_hr assets (bundled BambooHR theme CSS) + reload"
# The site volume masks assets baked into the image, so (re)build racedog_hr's
# bundle into the shared volume and refresh the manifest, else app_include_css 404s.
$D compose -f "$COMPOSE" exec -T backend bench build --app racedog_hr || true
$D compose -f "$COMPOSE" exec -T backend bench --site "$SITE" clear-cache || true
$D compose -f "$COMPOSE" restart backend frontend || true

echo ""
echo "=========================================================="
echo " DONE.  Open:  https://$SITE"
echo " Login: Administrator  /  (the ADMIN_PASSWORD you set)"
echo " (First HTTPS load can take ~1-2 min while Let's Encrypt issues the cert.)"
echo "=========================================================="
