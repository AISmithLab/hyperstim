# Deploying (plan 010)

Prod is the frontend on GitHub Pages and the backend on our server, both at the latest release tag. `main` is the latest dev version; prod can be behind it.

| When | What you run |
|---|---|
| Once per server (again only when the server setup changes) | `sudo deploy/setup.sh` (this folder) |
| Every new version: frontend and backend together | `hyperstim-release` (the root README) |

## Server setup

1. Copy the config and fill in every `<...>`. It's the only file to edit, and it's git-ignored (it holds the YouTube key):

   ```sh
   cp deploy/server.env.example deploy/server.env
   editor deploy/server.env
   ```

2. Run the setup, from a clone of this repo on the server:

   ```sh
   sudo deploy/setup.sh
   ```

   It installs the tools in `tools.env`, then sets up the user, group, folders, clone, the API's settings, the systemd services (the API and the collector), the data bot (below), read access for the release group, nginx (under `/v2/` on the API host), the sudo rule for releasing, and the `hyperstim-release` command. It checks nginx and sudoers before using them.

   The first time, it prints the **data bot's key** and stops short of the daily commit: a repo admin adds the key (GitHub → Settings → Deploy keys → Add deploy key, "Allow write access" on), then run `sudo deploy/setup.sh` again. It then clones the repo for the bot and turns the daily commit on.

3. Run it again whenever you change `deploy/server.env` or pull a change to this folder or `tools.env`. It changes only what differs and lists what it changed.

Then make the first release with `hyperstim-release`.

## GitHub (once, by a repo admin)

0. Settings → Rules → Rulesets → New tag ruleset: target `v*`; restrict creations, updates and deletions; bypass: repository admins only. The data bot's deploy key can push to `main`, so this keeps it from starting a deployment (plan 013).

1. Settings → Pages → Build and deployment: source **GitHub Actions**.
2. Settings → Environments → `github-pages` → Deployment branches and tags: add the tag rule `v*` (by default only `main` may deploy).
3. Settings → Secrets and variables → Actions → Variables:
   - `NEXT_PUBLIC_API_BASE` = `https://<api-host>/v2`
   - `NEXT_PUBLIC_BASE_PATH` = `/<repo-name>`
   - `NEXT_PUBLIC_GA_ID` = the Google Analytics measurement ID (`G-…`). Optional: without it the site has no consent banner and no analytics. The GA property's settings are in plan 009.
   - `NEXT_PUBLIC_SITE_ORIGIN` = `https://<domain>` (no path, no trailing slash), for the sitemap and canonical URLs.
   - `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` = the token from Google Search Console's HTML tag. Optional: without it the pages have no verification tag. Search Console setup is in plan 011.

## Cloud firewall (once)

In the cloud provider's security group for the server, allow only SSH (22) and HTTP/HTTPS (80, 443) from the internet. The service itself listens on `127.0.0.1` only.

## What's on the server

```
<prod-dir>/                    owned by root
  repo/                        clone of this repo; fetches from GitHub without a login (service user)
  releases/<tag>/              one checkout per release, with its own .venv (last 5 kept)
  releases/current -> <tag>    what the service runs
  data/                        the service's only writable folder: analysis/, thumbnails/, caches (service user)
  bin/                         uv and deno at the versions in tools.env
  uv/                          uv's Python and cache (service user)
  env                          the API's settings and secrets (readable by the service only)
  instance.env                 what release.sh needs: service user, service name, port
  <service>.service            systemd unit, linked into systemd
  nginx-*.conf                 per-IP connection cap and the /v2/ locations, included by nginx
  releases.log                 one line per release: time, who, tag, commit, result
  data/collector/              the collector's database and exported files (collected/, which the API reads)
  data/usage/                  daily usage counts (plan 014)
  <service>-collector.service  systemd unit of the collector (plan 013)
  <service>-data.service/.timer  the data bot's daily commit of collected/ to GitHub, at 03:00 UTC
  data-bot/                    the data bot's home: its SSH key (data bot user)
  data-repo/                   the data bot's clone, pushed with the deploy key (data bot user)
<clips-dir>/                   COLLECTOR_CLIPS_DIR: the collector's clips, feature caches and daily database backups (7 kept)
```

All of these except `releases/`, `data/` and `releases.log` are written by `setup.sh` from the templates here (`*.template`) and `server.env`; edit those, not the files on the server. Outside `<prod-dir>`, `setup.sh` adds only a symlink for the unit and one for the nginx connection cap, one `include` line in the nginx site file (with a backup next to the instance), `/etc/sudoers.d/<service>`, and `/usr/local/bin/hyperstim-release`.

The service runs as its own system user, so it can't read anyone's home folder or credentials, and its sandbox (`service.template`) lets it write only to `data/`. The collector runs as the same user, on one core at low priority, and may write only to `data/` and the clips folder. Root owns everything the service user must not change.

The data bot is a separate system user (no login, no sudo) with the only key that can push. It runs the released `scripts/commit-data.sh`, reads only `data/collector/collected/`, and may write only to its home and clone. The release group can read `data/analysis/`, `data/usage/` and `data/collector/` (ACLs); nobody else can.

## Renaming the repo

The site's path is the repo's name (`<domain>/<repo-name>/`), so renaming the repo moves the site. It was renamed once: `hyperstimulation-website` → `hyperstim` (2026-10-17, plan 010). This repo never writes the name; it lives in:

1. GitHub: the repo name, and the Actions variable `NEXT_PUBLIC_BASE_PATH` (`/<new-name>`).
2. Each clone: `git remote set-url origin git@github.com:<owner>/<new-name>.git` (GitHub redirects the old URL, but don't rely on it).
3. The prod clone: run `sudo deploy/setup.sh` from an updated clone; it points the prod clone at the new URL.
4. A new release (`hyperstim-release`), so the frontend is built under the new path.

The old address then returns 404: GitHub doesn't redirect a renamed repo's Pages. Links elsewhere (other sites, papers, posts) need updating by hand. If something still points at the old name, it's one of the places above.

## Day to day

- **Logs:** `journalctl -u <service>`, `-u <service>-collector`, `-u <service>-data`; releases in `<prod-dir>/releases.log`.
- **The collector's health:** from `<prod-dir>/releases/current/backend`, as the service user: `sudo -u <service-user> sh -c 'set -a; . <prod-dir>/env; .venv/bin/python -m hyperstim_api.collector status'`.
- **What's live:** `readlink <prod-dir>/releases/current`.
- **Rollback:** `hyperstim-release <older tag>` releases that commit under a new tag.
- **A new releaser:** add their login to `RELEASERS` in `server.env` and run `sudo deploy/setup.sh`. They need push access to the GitHub repo and a clone of it on the server.
