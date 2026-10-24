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
- **Privacy:** no change. Sonar only reads the repo's code; nothing reaches site visitors or the backend.

## Steps

**In the repo (me):**

1. Coverage dev dependencies and config, `test:coverage` script, `.gitignore` entries, ESLint ignores `coverage/`; lock files updated.
2. `sonar-project.properties`.
3. `ci.yml`: coverage runs, artifact uploads, `sonar` job.
4. Docs: coverage commands in `frontend/README.md` and `backend/README.md`. A one-line pointer to this plan in 001.
5. Check the first CI run on this branch's PR: coverage shows up in Sonar for both parts, and the excluded paths don't appear.

**For you (team):** Automatic Analysis off and `SONAR_TOKEN` secret set (done). In the project's Administration → New Code, choose "Previous version".

## Open questions

- None.
