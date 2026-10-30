# 012 — Code quality checks

**Area:** CI checks (`ci.yml`), testing (levels, tools, what each change must test), test coverage, and static analysis with SonarQube Cloud _(human decision, 2026-10-27: testing added)_.

## Goal

Show test coverage and SonarQube Cloud's analysis (bugs, code smells, security hotspots, duplication) for every push to `main` and every PR, next to the existing lint, type check, test and build checks. Set what every change must test, at unit, component and end-to-end level, accessibility included _(human decision, 2026-10-27)_.

## Decisions

### Static analysis and coverage

- **SonarQube Cloud, free plan for public repos** (the repo is public and Apache 2.0). Organization `aismithlab`, project `AISmithLab_hyperstim`, region sonarcloud.io (default). The keys aren't secret; only the token is.
- **CI-based analysis instead of Automatic Analysis**, because Automatic Analysis can't import coverage. Automatic Analysis is turned off in the project's settings (done).
- **Frontend coverage:** `@vitest/coverage-v8` (dev dependency, same version as vitest), configured in `vitest.config.mts` to write `frontend/coverage/lcov.info` for `src/**/*.{ts,tsx}` (tests excluded). Vitest writes paths relative to `frontend/`, so the `sonar` job prefixes them with `frontend/`.
- **Backend coverage:** `pytest-cov` (dev dependency), configured in `pyproject.toml` to measure `src/` and `scripts/` (with branches) and write `backend/coverage.xml`.
- **Commands:** `npm test` and `uv run pytest` stay as they are. Coverage is opt-in: `npm run test:coverage` and `uv run pytest --cov --cov-report=xml`. CI runs the coverage variants. Coverage output is git-ignored.
- **`sonar-project.properties` at the repo root** sets the keys, sources, tests and report paths:
  - Sources: `frontend/src`, `backend/src`, `backend/scripts`.
  - Tests: `*.test.ts(x)` in `frontend/src`, and `backend/tests`.
  - Excluded: `backend/pipeline/` (must stay identical to the research repo, so its issues can't be fixed), `backend/data/`.
- **New `sonar` job in `ci.yml`** (scan action `v8.3.0`), after the frontend and backend jobs: those jobs upload their coverage reports as artifacts. The `sonar` job downloads them, checks out the full history (Sonar needs it to tell new code from old), and runs `SonarSource/sonarqube-scan-action` (pinned version) with the `SONAR_TOKEN` repo secret (set).
- **PRs from forks** get no secrets, so the `sonar` job is skipped when the token is missing instead of failing (the job runs only for pushes and for PRs from branches of this repo). Outside contributors' PRs still pass CI.
- **A failing quality gate blocks releases** _(human decision, 2026-10-24)_: the `sonar` job waits for the gate (`sonar.qualitygate.wait=true`) and fails if it fails, and `release.sh` releases only commits where CI passed (plan 010). We work on `main` rather than through PRs, so the gate is checked on each push to `main`.
- **Gate criteria: Sonar's default "Sonar way"**, which the free plan can't change. It looks only at new code (below) and fails on any new bug, vulnerability or maintainability issue above rating A, any new security hotspot not yet reviewed in Sonar, new-code coverage under 80%, or new-code duplication over 3%. Coverage and duplication are ignored while new code is under 20 lines.
- **New code = everything since the last release** _(human decision, 2026-10-24)_: the `sonar` job passes the latest release tag on `main` (`git describe --tags --match 'v*'`, or `none` before the first release) as `sonar.projectVersion`, and the project's New Code setting is "Previous version". So each release tag starts a new version, and new code is what the next release would ship. The baseline is Sonar's last analysis before the tag appeared, normally the released commit (`release.sh` releases the latest `main` once CI passed). A failure blocks releases until it's fixed or marked in Sonar (accepted / false positive, hotspot reviewed).
- **`frontend/src/lib/mock.ts` is left out of coverage** _(human decision, 2026-10-25)_: it is a dev-only fake backend (loaded only with `NEXT_PUBLIC_API_MOCK=1`), not site code. Excluded in `sonar.coverage.exclusions` and in the vitest coverage `exclude`. It is still linted and analysed.
- **Raising coverage to 80%+ (overall and new code)** _(human decision, 2026-10-25)_: overall was 79.9%, new code 72% (only 25 lines/conditions since `v1.0.0`, below the gate's 20-line threshold for now). Tests are added where a bug would hurt most, not where lines are cheapest:
  1. `frontend/src/lib/api.ts`: the real `request()` against a stubbed `fetch`: URL and query building, ID encoding, `listParams` dropping empty values, `ApiError` with the status on a non-OK reply, `thumbnailUrl`. Component tests mock this module, so it was never run.
  2. `backend/src/hyperstim_api/analysis.py`, `ResearchPipeline` and the worker thread, with `subprocess` and `urlopen` faked: commands built (cookies flag), failures and timeouts mapped to `unavailable` / `failed`, too-small clip, the Data API key sent in a header and never in the URL or error text, `cancel()` and `_run` killing the process group, `start_worker` / `stop_worker`.
  3. `backend/scripts/import_dataset.py`: a small fake research checkout in `tmp_path`: a good import writes both files; each failed check exits with an error and writes nothing.
  4. `frontend/src/components/Header.tsx`: links, current page marked with `aria-current`, phone menu opens and closes (keyboard too).
  5. `frontend/src/components/compare/CompareChart.tsx`: the missing-value and edge-case branches.
  6. `backend/src/hyperstim_api/thumbnails.py`, `fetch_from_youtube` with `urlopen` faked: bytes on success, none on 404, `Unavailable` on other HTTP errors and network errors.
- **Privacy:** no change. Sonar only reads the repo's code; nothing reaches site visitors or the backend.

### Testing _(human decision, 2026-10-27)_

- **Every new feature and bug fix comes with tests** _(human decision)_. A fix includes a test that fails without the fix. The rule goes into CLAUDE.md (Engineering), with a pointer here.
- **Three levels** _(human decision)_, each for what it catches best:

  | Level | Tool | Covers |
  |---|---|---|
  | Unit | Vitest (frontend), pytest (backend) | Logic and edge cases: scoring, ranking, `api.ts`, formatting, parsing |
  | Component | Vitest + Testing Library | Rendering and interaction of one component or page section, with `api.ts` mocked; plus an axe check |
  | End-to-end | Playwright (new dev dependency) | Visitor flows through the built site against the **real backend** _(human decision)_; axe on every page; keyboard paths; reflow |

  Backend endpoint tests stay as they are: pytest with the synthetic fixture dataset (001).
- **Queries by role and accessible name** (`getByRole('button', { name: … })`) in component and E2E tests, not by class or test ID. A test that can't find an element by role and name has found an accessibility bug. Text the test asserts on comes from the same constant the page uses wherever one exists, so rewording doesn't break tests needlessly.
- **Accessibility testing:**
  - Automated: axe-core, called directly in component tests through a small helper, `expectNoAxeViolations` in `frontend/src/test/axe.ts` (`vitest-axe` is unmaintained, and the helper is a few lines). jsdom has no layout, so contrast is off there, and so is `region` (a component alone isn't inside the page's landmarks) and `@axe-core/playwright` in E2E (in a real browser, including contrast). Any violation fails the test. A rule may be turned off for one element only with a comment saying why. Light theme only, as the site has no dark mode _(human decision)_.
  - Written by hand in E2E: keyboard path through each page's main controls (Tab order, visible focus, Escape closes, focus comes back), and no horizontal scroll at 320 px.
  - Manual: a new page or a major UI change gets a keyboard and screen reader pass (VoiceOver or NVDA) before handoff, next to the 360/1280 screenshots CLAUDE.md asks for. Noted in the change's plan.
- **E2E setup:**
  - Tests in `frontend/e2e/`, run with `npm run test:e2e`. Playwright starts both servers itself, on ports 8100 and 3100 so they don't clash with the dev servers: the backend (`uvicorn`, from `backend/`) and the static site, which it builds for that backend and then serves from `frontend/out/` with Python's `http.server` through uv (no extra server dependency; `trailingSlash: true` makes `/rankings/` resolve to `rankings/index.html` like GitHub Pages). The build's env vars are set in `playwright.config.ts`, so a developer's `.env.local` doesn't leak in.
  - Consent: the E2E build gets a made-up Google Analytics ID, so the consent banner works as in prod. Tests start with a saved Reject, except the consent tests, which start as a first visit.
  - Backend data: the committed reference set (`backend/data/videos.tsv`) _(human decision: realistic data, like what visitors see)_ with `COLLECTED_DIR` empty, so the server's daily data commits don't move it. Tests find their videos and channels through the API (e.g. the first in the rankings), not by hard-coded IDs or values, so a research re-import doesn't break them.
  - No outside network: Playwright fails a test on any request to a host other than the two local servers, except YouTube embeds, which are answered with an empty page. This also checks the privacy policy's promise that nothing loads from YouTube before play (plan 009). Thumbnails (`/api/thumbnails/…`, which the backend would fetch from YouTube) are answered by Playwright with a local image.
  - Live analysis: CI can't download videos, so E2E covers a known dataset video (the check form goes straight to its page) and an already finished analysis (a result JSON placed in a temporary `ANALYSIS_DIR` before start). The running and failure states stay in component tests.
  - Installing the browsers: `./dev.sh --install-tools` (plan 010) installs Chromium and WebKit with their OS libraries, so a new developer's setup has them; `frontend/README.md` gives the one command for doing it by hand _(human decision, 2026-10-27)_.
  - **Safari check** (2026-10-30, plan 017): a few more E2E checks in `frontend/e2e/safari/`, with their own Playwright pinned to the newest shipping Safari's WebKit (26), as the main suite's WebKit is newer than any Safari. CI runs it after the main suite.
  - Browsers: Chromium and WebKit, each at 1280 px (desktop) and 360 px (phone): four projects, `chromium-desktop`, `webkit-desktop`, `chromium-phone`, `webkit-phone` _(human decision, 2026-10-27: people use Safari on desktops and Chrome on phones too)_. The 320 px reflow check runs in all four.
- **CI:** a new `e2e` job in `ci.yml`, after `frontend` and `backend`: installs both (`npm ci`, `uv sync --locked`), Playwright's browsers with their system libraries (`npx playwright install --with-deps`, not cached: the system libraries need installing each run anyway), builds the site, runs `npm run test:e2e`, uploads the Playwright report on failure. `release.sh` releases only commits where CI passed, so E2E failures block releases like the Sonar gate. E2E doesn't count toward Sonar coverage.
- **Existing pages get it too** _(human decision)_: E2E and axe coverage for all current pages and components, not only new work (step 12).
- **Privacy:** no change. Tests run only in CI and locally; they add nothing to the site or backend and contact no third party.

## Steps

**In the repo (me):**

1. Coverage dev dependencies and config, `test:coverage` script, `.gitignore` entries, ESLint ignores `coverage/`; lock files updated.
2. `sonar-project.properties`.
3. `ci.yml`: coverage runs, artifact uploads, `sonar` job.
4. Docs: coverage commands in `frontend/README.md` and `backend/README.md`. A one-line pointer to this plan in 001.
5. Check the first CI run on this branch's PR: coverage shows up in Sonar for both parts, and the excluded paths don't appear.

**Coverage to 80%+ (2026-10-25):**

6. Exclude `mock.ts` from coverage (`sonar-project.properties`, `vitest.config.mts`). (done)
7. Add the tests 1–6 above, one commit each (done). Result: frontend 95% statements / 91% branches, backend 98%; every file in 1–6 at 98–100%.
8. Check the next CI run: overall and new-code coverage in Sonar are 80% or more.

**Testing (2026-10-27):**

9. Rules in CLAUDE.md (Engineering: tests per feature and fix, the three levels, role queries, manual a11y pass), each pointing here. Testing section in `frontend/README.md` (E2E command, installing browsers with `npx playwright install --with-deps`).
10. Dev dependencies `@playwright/test`, `@axe-core/playwright`, `axe-core`; `playwright.config.ts` (servers, two projects, outside-network guard, thumbnail route); `test:e2e` script; ESLint and `.gitignore` for Playwright output; lock file updated.
11. `e2e` job in `ci.yml`.

    Steps 9–11 done.
12. Existing code:
    - axe check added to every existing component test file; component tests for components that have none yet where they hold interaction (`CheckVideoForm`, `SegmentedControl`, `Chip`, `Select`, `MeasurementPicker`, `CookieSettings`).
    - E2E: a spec per page (`home`, `rankings`, `video`, `channel`, `compare`; how it works, privacy and about together in `pages`): home (check a dataset video by link → its page, a finished live check, a bad link, the rankings card), rankings (category, search, calmest first, a measurement column, open a video and a channel), video (score, ⓘ, play and close, links to its channel and compare, a bad ID), channel (score, its videos over the years, a measurement, open a video, compare), compare (two videos by search and by link, remove, two channels), how it works (check field, a question), privacy (cookie settings), about. `site.spec.ts`: every page (12 states) loaded with axe and the 320 px check; skip link, header links and the phone menu, footer, consent, nothing from YouTube before Play. Keyboard paths in each spec.
    - Any bug these find is fixed in its own `fix:` commit under the plan that owns the page.

    Done (2026-10-27): 31 new component tests, axe in all 25 component test files; 46 E2E tests, run in each of the four projects. They found two bugs, fixed: rankings search missed titles with double spaces (plan 007), and on phones the channel page's video cards had an `aria-label` that left out their visible text, failing WCAG 2.5.3 "label in name" (plan 005).

**For you (team):** Automatic Analysis off and `SONAR_TOKEN` secret set (done). In the project's Administration → New Code, choose "Previous version".

## Open questions

- None.
