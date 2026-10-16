# Project rules

Website for the HyperStimulation project: a Next.js frontend (static, GitHub Pages) and a Python backend (runs on our own server, serves the frontend's API requests).

## Workflow

- Work is iterative. For each request: write the plan (or the change to it) in `plans/`, wait for review, then implement only the parts that were approved.
- Plans are concise: goal, decisions, steps, open questions. No long prose.
- Plan files are numbered: `plans/NNN-short-title.md` (e.g. `001-architecture.md`).
- Each plan owns an area of concern (a page, the dev setup, the architecture), named in an **Area** line under its title. It stays the current description of that area, so anyone working on the area reads that one plan.
  - A change to an area goes into the plan that owns it, also after the plan is done: edit it in place as a human decision (below), with the date. A change that spans areas goes into each affected area's plan; site-wide rules go into 001 or `STYLE.md`.
  - A new plan only for a new area.
- Work on a plan happens on its own branch, named after the plan file: `NNN-short-title` (e.g. `005-channel-detail` for `plans/005-channel-detail.md`). Later work on the same area reuses that branch, rebased onto `main` first so it has the latest changes.
- Never delete plans. Together with the dated decision marks and git history, they are the record of how things were built and the choices made along the way.
- Human decisions: while a plan is in progress (including reviewing what was built), record every decision the user makes in that plan, so the plan always reads as what is (or will be) built:
  - Edit the plan in place: rewrite the spot the decision is about (or add it where it belongs) and mark it _(human decision)_. If the user said why the earlier version didn't work, add that very briefly: _(human decision: too little breathing space)_. Don't keep the earlier version in the plan.
  - Only where a mark can't go in place (e.g. ASCII sketches): edit it directly, and list the decision in the plan's **Review decisions** section (before **Open questions**), naming what changed and the related spot in the plan.
  - Ask when a comment is unclear or conflicts with an earlier plan.
  - Apply each decision to the implementation right away too (with lint, type check, tests, build passing), so plan and code stay in sync.
- If a change contradicts another plan and it is unclear whether that is intended, ask before proceeding.
- Keep this file up to date when a rule changes.

## Public repository

This repo is public. Never commit:

- Secrets, tokens, cookies, API keys, or `.env` files (commit `.env.example` with placeholder values only).
- Server details: hostnames, IPs, ports, usernames, absolute paths on the server, systemd/nginx files with real values. Use env vars and placeholders.
- Research data that is not cleared for release (unpublished results, other research code). Cleared and committed: the video dataset in `backend/data/` (IDs, public metadata, features) and the pipeline parts in `backend/pipeline/`.
- Downloaded video clips. They are also never served by the backend; the site exposes only video IDs, public metadata, and scores.
- Notes about third-party sites used as design inspiration. Describe design intent in our own words only.

Before committing, check `git diff --staged` for anything above.

## Engineering

- Production quality, but keep it simple and maintainable. Prefer few dependencies and boring, well-known tools. No abstraction until there are two real uses for it.
- Frontend: Next.js (App Router, TypeScript, static export), Tailwind CSS. No server-side features (no API routes, no SSR, no image optimization).
- Backend: Python, FastAPI. Config only through environment variables.
- The frontend talks to the backend only through the typed API client in `frontend/src/lib/api.ts`; the backend's API contract lives in `backend/` and both change together.
- Accessibility and responsive design are requirements, not polish: every page must work on phones (from 320 px), tablets, and large desktop screens.
- Visual style: `frontend/design/STYLE.md` is the single source (look, rules, and the classes for each shared surface and control); colour and font values live only as tokens in `frontend/src/app/globals.css`. It overrides the "Visual style" sections of earlier plans. The mockup (`frontend/design/Design Mockup.png`) sets the overall look only, not text or layout.
  - Read `STYLE.md` before any UI work. New UI reuses its surfaces and controls; plans reference them instead of restating styles.
  - A new or changed style goes into `STYLE.md` in the same change, and the plan says so.
  - If a requested style change conflicts with `STYLE.md`, point out the conflict before applying it.
  - Before handing back UI work, screenshot the changed parts next to their neighbours at phone (360 px) and desktop (1280 px) widths and compare them against `STYLE.md`.
- Images and illustrations come from the team. When one is needed, ask with a spec: what it shows (object, pose/action), colours from the palette, style (hand-drawn crayon/watercolor), aspect ratio and minimum size, and background (transparent PNG/WebP unless stated). Use no placeholder or third-party art.
- Each change must pass lint, type check, build, and tests before commit.
- Commit messages: imperative, describe the why. Do not commit or push unless asked.

## Dev environment

New team members must be able to clone the repo and get a working setup from the docs alone.

- Tools: **npm** for the frontend (Node version via nvm), **uv** for the backend (it also installs the pinned Python). No Poetry, conda, pnpm, or Yarn.
- Pin runtime versions in the repo: Node in `frontend/.nvmrc` (and `engines` in `package.json`), Python in `backend/.python-version` (and `requires-python` in `pyproject.toml`). CI uses the same versions.
- Track every dependency with a committed lock file: `package.json` + `package-lock.json` (install with `npm ci`); `pyproject.toml` + `uv.lock` (install with `uv sync`). Dev tools (linters, test runners) are dependencies too. Don't rely on globally installed tools beyond nvm/Node and uv.
- The analysis pipeline (download + feature extraction) is copied from the research repo into `backend/pipeline/` and kept identical to it, apart from changes listed in its README. Its Python deps are in `uv.lock` at the research pipeline's exact pins, since feature values must match the dataset's. It also needs ffmpeg/ffprobe and deno on the server (see `backend/README.md`).
- The research repo is a read-only source: copy from it, never modify it. This repo must work without it.
- `frontend/README.md` and `backend/README.md` are short dev guides: prerequisites, install, env vars (pointing to `.env.example`), and the commands to run, lint, type check, test, and build. The root `README.md` links to both.
- When a change adds a dependency or changes a command or env var, update the README and lock file in the same change.
