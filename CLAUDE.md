# Project rules

Website for the HyperStimulation project: a Next.js frontend (static, GitHub Pages) and a Python backend (runs on our own server, serves the frontend's API requests).

## Workflow

- Work is iterative. For each request: write a plan in `plans/`, wait for review, then implement only the parts that were approved.
- Plans are concise: goal, decisions, steps, open questions. No long prose.
- Plan files are numbered: `plans/NNN-short-title.md` (e.g. `001-architecture.md`). Never rewrite an approved plan to change its decisions; write a new plan instead.
- Later plans override earlier ones. If a new plan contradicts an earlier one and it is unclear whether that is intended, ask before proceeding.
- Keep this file up to date when a rule changes.

## Public repository

This repo is public. Never commit:

- Secrets, tokens, cookies, API keys, or `.env` files (commit `.env.example` with placeholder values only).
- Server details: hostnames, IPs, ports, usernames, absolute paths on the server, systemd/nginx files with real values. Use env vars and placeholders.
- Research data that is not cleared for release (raw datasets, private pipeline code, unpublished results). The backend reads these from paths given in its config.
- Downloaded video clips. They are also never served by the backend; the site exposes only video IDs, public metadata, and scores.
- Notes about third-party sites used as design inspiration. Describe design intent in our own words only.

Before committing, check `git diff --staged` for anything above.

## Engineering

- Production quality, but keep it simple and maintainable. Prefer few dependencies and boring, well-known tools. No abstraction until there are two real uses for it.
- Frontend: Next.js (App Router, TypeScript, static export), Tailwind CSS. No server-side features (no API routes, no SSR, no image optimization).
- Backend: Python, FastAPI. Config only through environment variables.
- The frontend talks to the backend only through the typed API client in `frontend/src/lib/api.ts`; the backend's API contract lives in `backend/` and both change together.
- Accessibility and responsive design are requirements, not polish: every page must work on phones (from 320 px), tablets, and large desktop screens.
- Visual style follows `frontend/design/Design Mockup.png` and the "Visual style" section of the plans (fonts, palette, look), not its text or layout.
- Images and illustrations come from the team. When one is needed, ask with a spec: what it shows (object, pose/action), colours from the palette, style (hand-drawn crayon/watercolor), aspect ratio and minimum size, and background (transparent PNG/WebP unless stated). Use no placeholder or third-party art.
- Each change must pass lint, type check, build, and tests before commit.
- Commit messages: imperative, describe the why. Do not commit or push unless asked.

## Dev environment

New team members must be able to clone the repo and get a working setup from the docs alone.

- Tools: **npm** for the frontend (Node version via nvm), **uv** for the backend (it also installs the pinned Python). No Poetry, conda, pnpm, or Yarn.
- Pin runtime versions in the repo: Node in `frontend/.nvmrc` (and `engines` in `package.json`), Python in `backend/.python-version` (and `requires-python` in `pyproject.toml`). CI uses the same versions.
- Track every dependency with a committed lock file: `package.json` + `package-lock.json` (install with `npm ci`); `pyproject.toml` + `uv.lock` (install with `uv sync`). Dev tools (linters, test runners) are dependencies too. Don't rely on globally installed tools beyond nvm/Node and uv.
- The external analysis pipeline keeps its own environment; the backend runs it as a separate process via its configured path, so its dependencies never enter `uv.lock`.
- `frontend/README.md` and `backend/README.md` are short dev guides: prerequisites, install, env vars (pointing to `.env.example`), and the commands to run, lint, type check, test, and build. The root `README.md` links to both.
- When a change adds a dependency or changes a command or env var, update the README and lock file in the same change.
