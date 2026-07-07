# Deploy RaceDog HR on Oracle Cloud (Always Free) — $0/month

Puts the full stack (Frappe + ERPNext + HRMS + `racedog_hr`) on a free Oracle ARM
server with automatic HTTPS, reachable worldwide at `https://hr.racedogtechnologies.com`.
Your team, managers, and consultants log in from any browser, anywhere — no VPN, no install.

**Total cost:** $0 (Oracle Always-Free Ampere shape + free Let's Encrypt certificate).
**Your effort:** ~20 min of browser clicks (Part 1), then one command (Part 3).

---

## Part 1 — Things only you can do (browser, ~20 min)

> These need your identity, a card, and your domain login, so they can't be scripted.

1. **Create an Oracle Cloud account** — <https://cloud.oracle.com> → *Start for free*.
   A card is required for verification; **Always-Free resources never charge.**
   Choose a **home region near your team** (e.g. US East Ashburn / US West Phoenix).

2. **Create the server** — *Compute → Instances → Create instance*
   - **Image:** Canonical **Ubuntu 22.04** — the **ARM / aarch64** build
   - **Shape:** *Change shape → Ampere → `VM.Standard.A1.Flex` →* **4 OCPU, 24 GB RAM** (free)
     - ⚠️ If it says *out of capacity*, try another Availability Domain or region.
   - **SSH key:** *Generate a key pair* → **download the private key**
   - **Boot volume:** 100 GB
   - Create, then copy the **public IP**.

3. **Open the cloud firewall** — *Networking → your VCN → Security List → Add Ingress Rules*:
   | Source | Protocol | Dest. Port |
   |---|---|---|
   | `0.0.0.0/0` | TCP | `80` |
   | `0.0.0.0/0` | TCP | `443` |

4. **Point your domain** — in your DNS provider for `racedogtechnologies.com`, add:
   - **A record**: `hr` → **your VM's public IP**
   - (Do this now so the certificate can be issued in Part 3.)

5. **Confirm the app repo is public** — <https://github.com/vishnu14377/HR-Management-system>
   must be **public** (the build pulls from it). Keeping it private? Ask me for the token variant.

---

## Part 2 — Log in to the server

From your Mac terminal (use the key you downloaded + your VM IP):
```bash
chmod 400 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<YOUR_VM_IP>
```

---

## Part 3 — One command does the rest

On the server:
```bash
git clone https://github.com/vishnu14377/HR-Management-system
nano HR-Management-system/deploy/oracle/deploy-oracle.sh
```
Edit **only the block at the top** — set `SITE`, `LE_EMAIL`, and strong `DB_PASSWORD`
+ `ADMIN_PASSWORD`. Save (`Ctrl+O`, `Enter`, `Ctrl+X`). Then:
```bash
bash HR-Management-system/deploy/oracle/deploy-oracle.sh
```
It installs Docker, opens the box's firewall (the Oracle Ubuntu gotcha), builds the
image (**~25–40 min** on the free 4-core ARM box — grab a coffee), starts MariaDB +
Redis + Traefik, creates your site, and builds the theme assets. When it prints
**DONE**, open **https://hr.racedogtechnologies.com** (first load waits ~1–2 min for
the certificate) and log in as `Administrator` with your `ADMIN_PASSWORD`.

Then create your real users (managers as *Recruiting Manager*, recruiters as
*Recruiter*/*Bench Sales*, consultants linked via `user_id` land on their portal).

---

## Part 4 — Turn on backups (do this before entering real data)

```bash
chmod +x ~/HR-Management-system/deploy/oracle/backup.sh
( crontab -l 2>/dev/null; echo "0 2 * * * $HOME/HR-Management-system/deploy/oracle/backup.sh >> $HOME/backup.log 2>&1" ) | crontab -
```
This backs up the database + files nightly and keeps 7 days on the box. To also copy
backups **off the box** (survives a VM loss — strongly recommended for real HR data):
create a free Object Storage bucket (*Storage → Buckets*), install the OCI CLI
(`bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"`,
then `oci setup config`), and fill in `OS_BUCKET` + `OS_NAMESPACE` at the top of `backup.sh`.

---

## Part 5 — Updating later

When new `racedog_hr` code is pushed to GitHub, on the server:
```bash
cd ~/HR-Management-system && git pull
bash deploy/oracle/deploy-oracle.sh          # rebuilds the image + restarts
sudo docker compose -f ~/racedog-compose.yml exec backend \
  bench --site hr.racedogtechnologies.com migrate
```

---

## Good to know
- **Free-tier reclaim:** Oracle can reclaim *idle* free VMs. A live HR app with daily
  use won't be idle; just don't leave it empty for weeks.
- **Capacity:** the free ARM shape is popular — retry across Availability Domains if needed.
- **Managed alternative:** if you'd rather never touch a server, Frappe Cloud (~$25–50/mo)
  pulls this same GitHub repo and handles backups/TLS/updates for you.
- **Stuck on any step?** Paste the command output to me and I'll fix it — same as we did locally.
