# Development

How to work on HyperStim: what's where, running it locally, and releasing. What the site is: [`README.md`](README.md).

How dev, CI, prod and the outside services fit together, in diagrams: [`ARCHITECTURE.md`](ARCHITECTURE.md).

- [`frontend/`](frontend/README.md): Next.js static site (GitHub Pages)
- [`backend/`](backend/README.md): Python API (FastAPI) with the video dataset and analysis pipeline
- [`deploy/`](deploy/README.md): prod setup on the server and GitHub Pages
- [`plans/`](plans/): numbered design and implementation plans

Bugs, data that looks wrong, and ideas: open an issue with one of the [issue forms](../../issues/new/choose) ([plan 016](plans/016-community.md)).

## Run locally

Install the tools once (nvm + Node, uv, and for live analysis ffmpeg and deno, at the versions in `tools.env`; uses `apt` or Homebrew; plus Chromium and WebKit for the end-to-end tests, with the system libraries they need), then start both apps:

```sh
./dev.sh --install-tools   # once, and after tools.env changes
./dev.sh          # backend on :8000 and frontend on :3000, using the real backend
./dev.sh --mock   # frontend only, with mock data
```

It installs missing dependencies, prefixes each line of output with `[backend]` or `[frontend]`, and stops both apps on Ctrl+C or when either one exits. Change the ports with `BACKEND_PORT` / `FRONTEND_PORT`. The settings that must match the ports or suit local development (`NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_API_MOCK`, `CORS_ORIGIN`, `DATASET_PATH`, `ANALYSIS_DIR`, `THUMBNAIL_DIR`, and `ANALYSIS_LIMIT_PER_IP=0`, `ANALYSIS_LIMIT_PER_DAY=0`: no limits on live analyses) are set by the script for that run and override `backend/.env` and `frontend/.env.local`; everything else in those files still applies. To run one app on its own, see its README.

`./dev.sh` also turns on the `commit-msg` hook that checks commit messages; without it, run `git config core.hooksPath .githooks` once.

## Release

`main` is the latest dev version; prod (the site on GitHub Pages and the API on our server) runs the latest release tag, a version `vMAJOR.MINOR.PATCH`. One command releases both, on the server, from any clone of this repo:

```sh
hyperstim-release          # release the latest main on GitHub
hyperstim-release v1.2.0   # roll back: release an older tag again, under the next patch version
```

The version and the release notes come from the commit messages since the last release, which follow Conventional Commits (see "Commit messages" in [`CLAUDE.md`](CLAUDE.md)): a breaking change (`feat!:`) bumps the major version, a `feat:` the minor, anything else the patch. The notes are the tag's message and appear on the repo's [Releases](../../releases) page.

It releases what's on GitHub's `main`, not your clone's branch or uncommitted changes. It stops unless CI passed on that commit (this includes SonarQube Cloud's quality gate, [plan 012](plans/012-code-quality.md)); then it installs and tests the backend in a fresh checkout, switches the service over and checks `/api/health` (going back to the previous release if it doesn't answer), and only then pushes the tag, which deploys the frontend. You need to be in the server's release group and able to push to GitHub. The server's one-time setup: [`deploy/README.md`](deploy/README.md).
