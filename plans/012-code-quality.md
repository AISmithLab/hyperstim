# 012 — Code quality checks

**Area:** CI checks (`ci.yml`), test coverage, and static analysis with SonarQube Cloud.

## Goal

Show test coverage and SonarQube Cloud's analysis (bugs, code smells, security hotspots, duplication) for every push to `main` and every PR, next to the existing lint, type check, test and build checks.

## Decisions

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

**For you (team):** Automatic Analysis off and `SONAR_TOKEN` secret set (done). In the project's Administration → New Code, choose "Previous version".

## Open questions

- None.
