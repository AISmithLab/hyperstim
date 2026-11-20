## Type of change

- [ ] Bug fix (something didn't work as intended)
- [ ] New feature (something new visitors can see or use)
- [ ] Improvement to an existing feature
- [ ] Breaking change (a link stops working, or scores change meaning)
- [ ] Docs, tests or refactoring only (no visible change)

## Problem

<!-- What was wrong or missing, and who it affects. -->

## Solution

<!-- What you changed and why this way. Alternatives you tried, and how they did. -->

## Visitor-facing changes

<!-- Anything visitors will notice; write "None" if nothing. -->
- **Interface:** <!-- e.g. new category list, new filter on the rankings page -->
- **Claims and text:** <!-- e.g. changed numbers, explanations, methodology wording -->

## Screenshots

<!-- UI changes only; otherwise write "None". -->

| Size | Before | After |
| --- | --- | --- |
| Phone (360 px) | | |
| Tablet (768 px) | | |
| Desktop (1280 px) | | |

## Ready for review

<!-- Each box is a merge requirement, not a list of what you did. Tick all of them before asking for review. If one doesn't apply, tick it and add "n/a" with a word on why. If one isn't met yet, leave the PR as a draft. -->

- [ ] Tests added or updated; a bug fix includes a test that fails without it
- [ ] Lint, type check, tests (unit, component, end-to-end) and build pass
- [ ] Test coverage of the changed lines (`npm run test:coverage`, `uv run pytest --cov`): frontend __%, backend __%
- [ ] UI changes checked at the three sizes above, with the keyboard, and in the Safari check
- [ ] Docs updated (READMEs, `.env.example`) if setup, commands or settings changed
- [ ] The privacy policy (`/privacy`) is still true
- [ ] Nothing secret or server-specific in the diff (keys, tokens, hostnames, server paths, unreleased research data)
- [ ] Every commit message follows "Commit messages" in `DEVELOPMENT.md` (PRs are merged with "Rebase and merge", so each commit lands as written)
