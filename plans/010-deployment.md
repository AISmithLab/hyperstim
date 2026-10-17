# 010 — Deployment

**Area:** Environments, releases, and deploying the frontend (GitHub Pages) and the backend (our server).

## Goal

A lightweight release with one command: `main` is the latest dev version, prod runs the last release and can be behind `main`.

## Decisions

- **Two environments, no staging** (one-person team; add it if the team grows).

  | | Dev | Prod |
  |---|---|---|
  | Frontend | `next dev` (`./dev.sh`, plan 003) | GitHub Pages, built from a release tag |
  | Backend | any dev checkout, `uvicorn --reload`, localhost only _(human decision, 2026-10-17)_ | the prod instance (below) at the release commit, always-on systemd service behind nginx |
  | Config | `.env` / `.env.local` (dev values) | the instance's `env` file (analysis limits on, `YOUTUBE_API_KEY` set, `CORS_ORIGIN` = Pages origin); Actions variables for the frontend |
  | Data | `backend/analysis/` | the instance's `data/` |

- **Releases are tags** with the date: `vYYYY.MM.DD`, then `vYYYY.MM.DD.1`, `.2` for more releases the same day. One tag releases frontend and backend together (they share the API contract).
- **What is released: the latest `main` on GitHub** (`origin/main`) by default, whatever branch or uncommitted changes the local checkout has. No branch or working-tree checks.
- **Backend changes stay additive** (new fields/endpoints) within a release, so the old frontend keeps working for the minute between the backend and frontend deploys.
- **Only git, curl and uv needed** (no `gh`) _(human decision, 2026-10-17)_. GitHub's API is read without a login (public repo).
- **`release.sh [<commit or tag>]` at the repo root**, plain bash, run as `hyperstim-release`:
  1. `git fetch`; take `origin/main` (or the given commit, which must be on `main`). Stop if that commit is already the latest release, or if CI (`ci.yml`) didn't pass on it (read from GitHub's API with curl; still running or failed: say so and stop). One release at a time (a lock).
  2. **Backend first, in a fresh checkout per release** (a worktree `releases/<tag>/` of the instance's clone, with its own `.venv`), so testing never touches the running service: as the service user, check out the commit, `uv sync --locked`, run `pytest`; if either fails, remove the checkout and stop. Then point `releases/current` at it, restart the service, poll `GET /api/health`. If unhealthy: point `current` back at the previous release, restart, report, stop. No tag is pushed, so the frontend stays as it was. The newest 5 releases are kept.
  3. **Then the tag:** create the next tag on the commit and push it. The push starts `deploy.yml`; the script polls the run (curl) and prints the result and the site URL.
  4. Each step's outcome is appended to `releases.log`.
- **Rollback = a new release of an older commit:** `hyperstim-release v2026.10.16` releases that commit under a new tag (e.g. `v2026.10.18.1`), so the newest tag is always what's live.
- **Who can release:** anyone with a login on the server, in the release group, and with push access to the GitHub repo. They run `release.sh` from **any clone on the server** (their own included), not only the dev checkout, since it releases from GitHub's `main`, not from the clone it runs in.
- **One config file for the whole server setup** _(human decision, 2026-10-17: the step-by-step setup was too complicated)_: `deploy/server.env` (git-ignored; committed: `deploy/server.env.example` with placeholders and a comment per value). It holds every value that differs per server: instance directory, service name and user, release group and its members, local port, the nginx site file of the API host, `CORS_ORIGIN`, `YOUTUBE_API_KEY`, `YTDLP_COOKIES`, the limits. Nothing else is edited by hand.
- **One setup command:** `sudo deploy/setup.sh` reads `deploy/server.env` and does the whole server setup: installs the system packages and tools (below), creates the user, group and `<prod-dir>`, clones the repo, writes the API's `env` and `instance.env`, renders and installs the systemd unit, nginx files and sudoers rule from the templates, checks them (`nginx -t`, `visudo -c`) and reloads. It can be run again at any time (after editing `server.env` or when the templates change) and only changes what differs, listing what it changed; a failing `nginx -t` restores the site file. It also installs a `hyperstim-release` command (root-owned, knows `<prod-dir>`), so releasers need no config of their own: `release.env` and `release.env.example` go away.
- **System requirements in one place, for dev and the server** _(human decision, 2026-10-17: they were scattered; dev too)_: `tools.env` at the repo root pins uv, deno, nvm and the expected ffmpeg version, and lists the OS packages (apt; Homebrew on macOS for dev). One installer, `scripts/install-tools.sh`, installs exactly these and skips what's already there: uv and deno as release binaries checked against their published checksums, ffmpeg etc. from the OS packages (warning if ffmpeg isn't the dataset's version), and for dev nvm plus the Node in `frontend/.nvmrc`. Dev runs it as `./dev.sh --install-tools` (into `~/.local/bin`); `setup.sh` runs it for the server (into `<prod-dir>/bin/`, plus nginx and envsubst). CI reads uv's version from `tools.env`. Language dependencies stay in `package-lock.json` and `uv.lock`.
- **`.github/workflows/deploy.yml`:** on push of tags `v*`; `npm ci`, `npm run build` with `NEXT_PUBLIC_API_BASE` and `NEXT_PUBLIC_BASE_PATH` from Actions variables, then the official Pages actions (`configure-pages`, `upload-pages-artifact`, `deploy-pages`). CI already ran the checks on that commit.
- **The prod API is served under `/v2/` on the existing API domain**, next to the old API on `/api/` (the old site still uses it until it's retired, 001 migration step 4) _(human decision, 2026-10-17)_. nginx maps `/v2/api/…` to the service's `/api/…`, so the frontend only needs `NEXT_PUBLIC_API_BASE=https://<api-host>/v2`; no code change.
- **The first release goes to this repo's Pages; the old site is deployed elsewhere and isn't affected** _(human decision, 2026-10-17)_.
- **The YouTube API key is the one dev uses** _(human decision, 2026-10-17)_; dev and prod share its quota (10,000 units/day; a new analysis costs 1, prod caps at 1,000/day). In Google Cloud, restrict the key to the YouTube Data API and to the server's IP (dev and prod both run there).

### The prod instance

Everything of the instance sits in one directory `<prod-dir>` on the server, so it's easy to find and trace _(human decision, 2026-10-17)_. It's outside home folders (in the system's usual place for what a machine serves): the service user can't enter home folders, and prod shouldn't depend on one person's account _(human decision, 2026-10-17)_. Layout and setup: `deploy/README.md`.

```
<prod-dir>/                  owned by root
  repo/                      clone of this repo; fetches from GitHub without a login (public repo)
  releases/<tag>/            one checkout per release, with its own .venv
  releases/current -> <tag>  what the service runs
  data/                      the service's only writable folder: analyses, caches
  bin/                       uv and deno (the service can't use ones in a home folder)
  uv/                        uv's Python and cache
  env                        prod config and secrets (readable by the service only)
  instance.env               what release.sh needs
  <service>.service          systemd unit, linked into systemd with `systemctl link`
  nginx-*.conf               per-IP connection cap and the /v2/ locations, included by nginx
  releases.log               one line per release: time, who, tag, commit, result
```

- Runs as its **own system user** (`<service-user>`), so the public service can't read or write anyone's home folder, the dev checkouts, or GitHub credentials _(human decision, 2026-10-17)_. Pushing the tag uses the releaser's own GitHub login, from their clone.
- `<prod-dir>` itself, the unit, the nginx files, `env` and `bin/` are owned by root (the service user must not change what runs it or how).
- Releasing needs no full sudo: a sudoers rule lets the release group run commands as the service user and run exactly `systemctl restart <service>`.
- Server files with real values stay on the server (001); `deploy/` holds them as templates with placeholders, rendered by `setup.sh` from `server.env`.
- **`deploy/` vs `release.sh`:** `deploy/setup.sh` prepares the server, once (and again only when the server setup changes). `release.sh` (via `hyperstim-release`) ships a new version, frontend and backend together, every time.

## Protection against abuse

The API URL is public once the site is (the browser calls it), and CORS stops only other websites' pages, not scripts. So all protection is on the server. Already in the app: per-IP limit on new analyses (20/hour _(human decision, 2026-10-17: too strict)_), a queue of 10, one analysis at a time on at most 4 cores, the made-for-kids check, thumbnails only for known videos, capped query parameters.

Added in prod:

- **Only nginx is reachable from outside:** uvicorn listens on `127.0.0.1`; nginx proxies only `/v2/api/`.
- **nginx: no request-rate limits** _(human decision, 2026-10-17: too strict)_, for the API and thumbnails alike. Kept: at most 20 connections at once per IP (`limit_conn`, over it → 429), small request bodies, short timeouts. Risk taken: each thumbnail request makes us fetch from YouTube, so one script could make the server hammer YouTube; add a thumbnail rate limit back if that shows up.
- **A daily cap on new analyses across all visitors** (`ANALYSIS_LIMIT_PER_DAY`, env var, 0 = off for dev; prod 1,000 _(human decision, 2026-10-17: too strict)_), so many IPs together can't use up the YouTube API quota or get the server's IP blocked by YouTube for heavy downloading. Over the cap → the same "busy" answer as a full queue.
- **API docs off in prod** (`/docs`, `/redoc`, `/openapi.json`), via an env var; on in dev.
- **systemd hardening** for the service (the pipeline parses downloaded videos with ffmpeg, so limit the damage if one is malicious): own user, `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, write access only to `data/`, `MemoryMax` and `CPUQuota`.
- **Firewall:** only SSH and 80/443 open to the internet, set in the cloud provider's security group.

Not now (add if abuse shows up): fail2ban on repeated 429s; a CDN or bot-check in front (third party: the privacy policy would have to name it).

## Steps

1. **GitHub setup, by hand (an org/repo admin):**
   1. Scan the whole git history for anything the public-repo rules forbid; fix before going public.
   2. Settings → General → Danger Zone: make the repo public.
   3. Settings → Pages → Build and deployment: source "GitHub Actions".
   4. Settings → Environments → `github-pages` → Deployment branches and tags: add the tag rule `v*` (by default only the default branch may deploy).
   5. Settings → Secrets and variables → Actions → Variables: `NEXT_PUBLIC_API_BASE` = `https://<api-host>/v2`, `NEXT_PUBLIC_BASE_PATH` = `/<repo-name>`.
2. **Cloud setup, by hand:** check the instance's security group allows only 22, 80, 443 from the internet; restrict the YouTube API key (above).
3. **Server setup:** copy `deploy/server.env.example` to `deploy/server.env`, fill it in, run `sudo deploy/setup.sh` (`deploy/README.md`). What it sets up: service user and release group, `<prod-dir>` layout, `bin/` tools, clone, `env`, systemd unit (`Restart=always`, enabled at boot, `--proxy-headers`, no `--reload`, single process), nginx files included from the API site, sudoers rule, `hyperstim-release`.
4. Backend: `ANALYSIS_LIMIT_PER_DAY` and the docs switch, with tests; `.env.example` and `backend/README.md` updated.
5. Write `deploy.yml`, `release.sh`, the `deploy/` templates, `server.env.example`, `setup.sh` and a short guide; `tools.env`, `scripts/install-tools.sh`, `./dev.sh --install-tools`; git-ignore `deploy/server.env`. Run `setup.sh` on our server over the setup done by hand so far (it should change nothing but add `hyperstim-release`).
6. Docs: root `README.md` "Release" section (who can release, `hyperstim-release`, rollback) and `--install-tools`; `backend/README.md` links to `deploy/README.md`; `CLAUDE.md` gets one line on releasing.
7. Update 001: frontend deployed on a release tag; prod backend runs from its own instance (done).
8. Check: 429 from nginx above 20 connections per IP; docs 404 in prod; first release end to end; a failing backend test leaves the service untouched; an unhealthy backend rolls back and pushes no tag; rollback to an older tag; a release from another clone, on a feature branch with uncommitted edits, still releases `origin/main`.

## Open questions

None.
