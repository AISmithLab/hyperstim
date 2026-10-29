# Project rules

Website for the HyperStimulation project: a Next.js frontend (static, GitHub Pages) and a Python backend (runs on our own server, serves the frontend's API requests).

## Workflow

- Work is iterative. For each request: write the plan (or the change to it) in `plans/`, wait for review, then implement only the parts that were approved.
- Plans are concise: goal, decisions, steps, open questions. No long prose.
- Plan files are numbered: `plans/NNN-short-title.md` (e.g. `001-architecture.md`).
- Each plan owns an area of concern (a page, the dev setup, the architecture), named in an **Area** line under its title. It stays the current description of that area, so anyone working on the area reads that one plan.
  - A change to an area goes into the plan that owns it, also after the plan is done: edit it in place as a human decision (below), with the date. A change that spans areas goes into each affected area's plan; site-wide rules go into 001 or `STYLE.md`.
  - A new plan only for a new area.
- Commits for a plan go on its own branch, named after the plan file: `NNN-short-title` (e.g. `005-channel-detail` for `plans/005-channel-detail.md`). Later work on the same area reuses that branch, rebased onto `main` first so it has the latest changes.
  - When asked to commit, put the work on the one branch of the plan it's most about, even if it touches other plans too (the subject names them all: `(plans 004, 005)`); don't split one piece of work across branches.
- Parallel sessions share one checkout, on whatever branch it is on, so the user can inspect all work in progress there. Uncommitted edits belong to no branch; the branch rule applies only when committing:
  - Small edits to shared files (`CLAUDE.md`, `STYLE.md`, `globals.css`, `api.ts`, READMEs) are fine; only one session at a time changes dependencies (`package.json`, lock files).
  - Never run git commands that touch the whole checkout (`stash`, `reset --hard`, `checkout .`, `restore .`, `clean`, switching branches). Name files explicitly.
  - At commit time, take your files from `git status`; in shared files, commit only your hunks. Ask when unsure whether a change is yours.
  - To commit: if the checkout is on the plan's branch, commit only your changes there. Otherwise, add a temporary worktree of the plan's branch, copy your changes in, run lint, type check, tests and build there, commit, remove the worktree, and revert your changes in the shared checkout (git won't merge the branch over identical uncommitted edits; they come back with the merge).
  - If the checks fail in the worktree because the change relies on another unmerged branch, ask: merge that branch first, or base this one on it and say so in the plan.
  - Keep history linear. Before merging a branch, `git fetch origin` (the data bot commits to `main` daily), rebase the branch onto `origin/main`, re-run the checks, then `git merge --ff-only <branch>` into `main`. If that fails because another session merged first, rebase again. Make a merge commit only when there's no other way. Never commit on `main` directly.
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
- Research data that is not cleared for release (unpublished results, other research code). Cleared and committed: the video dataset in `backend/data/` (IDs, public metadata, features; the reference set and the videos added since in `backend/data/collected/`, plan 013) and the pipeline parts in `backend/pipeline/`.
- Downloaded video clips. They are also never served by the backend; the site exposes only video IDs, public metadata, and scores.
- Notes about third-party sites used as design inspiration. Describe design intent in our own words only.

Before committing, check `git diff --staged` for anything above.

## Privacy policy

- The privacy policy (`/privacy`, plan 009) must always match what the site and backend actually do: what they store, log, keep and for how long, and which third parties they load from or send data to.
- Check every change against it. If a change would make the policy untrue or need a policy change, stop and confirm with the user before building it; then update the policy (and plan 009) in the same change.

## Engineering

- Production quality, but keep it simple and maintainable. Prefer few dependencies and boring, well-known tools. No abstraction until there are two real uses for it.
- Frontend: Next.js (App Router, TypeScript, static export), Tailwind CSS. No server-side features (no API routes, no SSR, no image optimization).
- Backend: Python, FastAPI. Config only through environment variables.
- The frontend talks to the backend only through the typed API client in `frontend/src/lib/api.ts`; the backend's API contract lives in `backend/` and both change together.
- **Site text is in American English** (color, center, gray, analyze): everything visitors read, including page metadata and messages from the API.
- Accessibility and responsive design are requirements, not polish: every page must work on phones (from 320 px), tablets, and large desktop screens.
- **Readers other than people are requirements too** (plan 011, Readers other than people): link previewers, search engines, AI crawlers and archives mostly read the page as built, without running JavaScript. Every page must make sense to each group in plan 011's table: a meaningful title, description and H1, and loading states that read as sentences (no placeholder digits, no bare "Loading…"). Every reader gets the same page: never detect bots or serve them different content. Check a changed page's built HTML without JavaScript (the E2E no-JavaScript check).
- Visual style: `frontend/design/STYLE.md` is the single source (look, rules, and the classes for each shared surface and control); colour and font values live only as tokens in `frontend/src/app/globals.css`. It overrides the "Visual style" sections of earlier plans. The mockup (`frontend/design/Design Mockup.png`) sets the overall look only, not text or layout.
  - Read `STYLE.md` before any UI work. New UI reuses its surfaces and controls; plans reference them instead of restating styles.
  - A new or changed style goes into `STYLE.md` in the same change, and the plan says so.
  - If a requested style change conflicts with `STYLE.md`, point out the conflict before applying it.
  - Before handing back UI work, screenshot the changed parts next to their neighbours at phone (360 px) and desktop (1280 px) widths and compare them against `STYLE.md`.
  - An artifact page built to review a layout shows it at three screen sizes: phone (360 × 740), tablet (768 × 1024) and desktop (1280 × 800).
- Images and illustrations come from the team. When one is needed, ask with a spec: what it shows (object, pose/action), colours from the palette, style (hand-drawn crayon/watercolor), aspect ratio and minimum size, and background (transparent PNG/WebP unless stated). Use no placeholder or third-party art.
- Each change must pass lint, type check, build, and tests (including end-to-end) before commit.
- **Tests** (plan 012 has the setup and details):
  - Every new feature and bug fix comes with tests. A fix includes a test that fails without it.
  - Test at the level that catches the problem, often more than one: **unit** (logic: Vitest, pytest), **component** (one component or page section with `api.ts` mocked: Vitest + Testing Library), **end-to-end** (visitor flows on the built site against the real backend: Playwright, in `frontend/e2e/`). A new page or visitor flow gets an E2E spec.
  - Find elements by role and accessible name (`getByRole('button', { name: … })`), not by class or test ID.
  - Accessibility is tested too: an axe check in each component test file and on each page in E2E, and each page's keyboard path and 320 px reflow in E2E. A new page or major UI change also gets a manual keyboard and screen reader pass before handoff.
- Do not commit or push unless asked.
- When asked for a commit plan, list each commit message in full together with the branch it goes on, and report the test coverage of the changed lines (`npm run test:coverage`, `uv run pytest --cov`), flagging any below Sonar's 80% new-code gate (plan 012).
- **Commit messages follow Conventional Commits**; `release.sh` takes the next version and the release notes from them (plan 010). Format: `<type>[!]: <subject> (plan NNN)`, then an optional body after a blank line. The `commit-msg` hook in `.githooks/` checks the format.
  - **Subject:** imperative, capitalised, no full stop; says what changes and why, in words a reader of the release notes understands. End with the plan(s) it belongs to, `(plan 007)` or `(plans 007, 008)`; leave it out for changes outside any plan.
  - **Type**, by what the change means for the live site (pick the first that fits; split the commit if it's two things):
    - `feat`: something new visitors can see or use: pages, features, text, API endpoints. → minor version.
    - `fix`: the site or API didn't work as intended, or an existing feature is adjusted to work better (how it behaves, looks or is laid out), including security fixes (also a dependency upgrade done for one). → patch.
    - `perf`: faster or lighter, same behaviour. `refactor`: code change with no visible change. `style`: formatting only.
    - `test`: tests only. `docs`: plans, READMEs, `STYLE.md`, `CLAUDE.md`, code comments. `build`: dependencies, build config, dev scripts. `ci`: CI, release and server setup (`.github/`, `release.sh`, `deploy/`). `chore`: anything else.
    - `data`: only the server's daily commit of the collected dataset (`backend/data/collected/`, plan 013); never used by hand. Not listed in the release notes and no version bump; CI and `release.sh` reject a `data:` commit that changes any other file.
  - **Breaking:** add `!` after the type and a body line `BREAKING CHANGE: <what stops working, and what to do instead>` when a page URL or shareable link stops working (removed, or moved without a redirect), or scores or measurements change meaning so they can't be compared with earlier ones. → major version. Redesigns, new text and new pages are not breaking.
  - Examples:
    - `feat: Add the compare page for two videos or two channels (plan 008)`
    - `fix: Show a count of 0 as 0 and silent clips as "No sound" (plan 004)`
    - `fix: Upgrade Next.js to 16.4.2 for its security fixes`
    - `docs: Record human decisions in place in plans`
    - `ci: Number release tags from .1 each day (plan 010)`
    - `feat!: Score videos with the v3 feature set (plan 002)` + body `BREAKING CHANGE: scores are not comparable with earlier releases.`
- Releasing to prod is only through `hyperstim-release` (`release.sh`, plan 010). Backend API changes stay additive within a release, so the live frontend keeps working while the two deploy.
- **Never launch a release yourself.** A release is started manually by the team, or by you only when explicitly told to release in that request. Finishing, merging, or pushing work is not a request to release; neither is an earlier approval.

## Dev environment

New team members must be able to clone the repo and get a working setup from the docs alone.

- Tools: **npm** for the frontend (Node version via nvm), **uv** for the backend (it also installs the pinned Python). No Poetry, conda, pnpm, or Yarn.
- Pin runtime versions in the repo: Node in `frontend/.nvmrc` (and `engines` in `package.json`), Python in `backend/.python-version` (and `requires-python` in `pyproject.toml`). CI uses the same versions.
- Track every dependency with a committed lock file: `package.json` + `package-lock.json` (install with `npm ci`); `pyproject.toml` + `uv.lock` (install with `uv sync`). Dev tools (linters, test runners) are dependencies too. Don't rely on globally installed tools beyond nvm/Node and uv.
- The analysis pipeline (download, feature extraction, category classifier) is copied from the research repo into `backend/pipeline/` and kept identical to it, apart from changes listed in its README. The collector (`backend/src/hyperstim_api/collector/`, plan 013) uses it to grow the dataset; it runs as its own process (`backend/README.md`). Its Python deps are in `uv.lock` at the research pipeline's exact pins, since feature values must match the dataset's. It also needs ffmpeg/ffprobe and deno on the server (see `backend/README.md`).
- The research repo is a read-only source: copy from it, never modify it. This repo must work without it.
- `frontend/README.md` and `backend/README.md` are short dev guides: prerequisites, install, env vars (pointing to `.env.example`), and the commands to run, lint, type check, test, and build. `DEVELOPMENT.md` at the root is the developer entry point and links to both; the root `README.md` describes the site for any visitor (plan 001).
- When a change adds a dependency or changes a command or env var, update the README and lock file in the same change.
