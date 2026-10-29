# 016 — Community

**Area:** How people outside the team take part on GitHub: issue templates and the files that point people to them (contact links, later a contributing guide and security policy).

## Goal

Make it easy for parents, researchers and developers to report problems and suggest ideas on GitHub, and get reports we can act on without back-and-forth. Keep personal data out of public issues.

## Decisions

- **GitHub issue forms** (YAML in `.github/ISSUE_TEMPLATE/`), not Markdown templates: required fields, dropdowns and checkboxes, so reports arrive complete and labelled.
- **Three forms** _(human decision, 2026-10-29)_, each adding its own label plus `triage`:

  | Form | For | Fields | Labels |
  | --- | --- | --- | --- |
  | **Bug report** | The site or API doesn't work as it should | Where (dropdown: website, API, dev setup/docs) · page link · what happened · what you expected · steps to reproduce · device and browser with their versions, or for dev setup the OS and tool versions (required) _(human decision, 2026-10-29)_ · screenshot (optional) | `bug` |
  | **A score or detail looks wrong** | A video's or channel's data: score, measurements, category, channel name, missing or wrong metadata | Video or channel link · what looks wrong (dropdown: score, a measurement, category, channel/title, other) · why you think so | `data` |
  | **Idea or feature request** | Something new or better | What problem it solves · your idea · alternatives considered (optional) _(human decision, 2026-10-29: no "who it helps")_ | `enhancement` |

- **The "New issue" page lists only the three forms** _(human decision, 2026-10-29)_: no contact links on it. GitHub's "Open a blank issue" option is turned off (`config.yml`), so every issue comes through a form.
- **Linked from the About page's "Get in touch"** _(human decision, 2026-10-29)_: plan 015 has the text.
- **No intro text on the data form** _(human decision, 2026-10-29)_: it starts with its first field.
- **Every form ends with a required checkbox:** "I haven't included personal information (names, emails, children's details). Issues are public."
- **Rules for us, not shown to visitors:**
  - Form text in American English and plain words (site rule; parents may file the data and idea forms).
  - Labels don't clash with plan 013's alert labels (`alert`, `alert:<kind>`); the bot's issues don't use these forms.
  - Privacy policy unchanged: the forms live on GitHub, not on the site or backend, and the site already links GitHub (plan 015). Nothing new is stored or sent by us.

## Steps

1. Create the labels `bug`, `data`, `enhancement`, `triage` if missing (GitHub's defaults cover `bug` and `enhancement`).
2. ~~Add `.github/ISSUE_TEMPLATE/bug-report.yml`, `data-report.yml`, `feature-request.yml`, `config.yml` (blank issues off).~~
3. ~~About page link~~ (plan 015, step 7).
4. ~~`DEVELOPMENT.md`~~: one line pointing to the issue forms for bugs and ideas.
5. Check: open each form on GitHub after merge (forms only render from the default branch); validate the YAML locally before (`python -c "import yaml…"` via `uv run`).
6. Commit: `ci: Add issue forms for bugs, data corrections and ideas (plan 016)` and `feat: Point to the GitHub issue forms from the About page (plans 015, 016)`, on `016-community`.

## Open questions

1. **More forms?** Candidates: "Add a video or channel" (ask the collector to include one, plan 013), "Documentation" (separate from bugs), "Research question" (about the method or dataset). I'd start with three and add when real issues show the need.
2. **GitHub Discussions** for open questions instead of the contact form? Public and searchable, but one more place to watch.
3. **Also now, or later:** `CONTRIBUTING.md` (how to propose a change, link to `DEVELOPMENT.md`, the plan workflow, Conventional Commits), a pull request template (what changed, plan, tests run, screenshots at 360/1280 px), `SECURITY.md` (with no security link on the New issue page, it is where a vulnerability reporter would look to report privately), `CODE_OF_CONDUCT.md` (Contributor Covenant)?
4. **Who triages, and how often?** Worth stating in `CONTRIBUTING.md` (e.g. weekly, like the contact form).
