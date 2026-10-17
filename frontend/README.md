# HyperStim frontend

Next.js (App Router, static export) + Tailwind CSS. Deployed to GitHub Pages; talks to the backend only through `src/lib/api.ts`.

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm); the Node version is pinned in `.nvmrc`. `./dev.sh --install-tools` at the repo root installs both.

## Setup

```sh
cd frontend
nvm install        # or `nvm use`
npm ci
cp .env.example .env.local
```

## Environment variables

See `.env.example`. All are read at build time.

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_BASE_PATH` | Path prefix the site is served under (`/<repo-name>` on GitHub Pages). Empty locally. |
| `NEXT_PUBLIC_API_BASE` | Backend base URL, no trailing slash. Locally `http://localhost:8000`: start the backend first ([`../backend/README.md`](../backend/README.md)); its `CORS_ORIGIN` must be this site's origin (`http://localhost:3000`). |
| `NEXT_PUBLIC_GA_ID` | Google Analytics measurement ID (`G-…`). Empty: no consent banner, no "Cookie settings" button and no analytics code. Set only for production. |
| `NEXT_PUBLIC_API_MOCK` | `1` = use the mock data in `src/lib/mock.ts` instead of the backend. |

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server at http://localhost:3000 |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript |
| `npm test` | Vitest unit tests |
| `npm run build` | Static export to `out/` |
| `npm run images` | Convert art to WebP (runs automatically before `dev` and `build`) |

## Images

Originals from the team live in `art/` (including unused ones). Only images listed in `art/used.json` are converted to WebP into `public/images/` (git-ignored), at 2× the given display width. To use a new image, add a line to `used.json` and reference it as `asset("/images/<name>.webp")`.

## Styles

How the site looks (rules, and the classes for each card, control and popover) is in [`design/STYLE.md`](design/STYLE.md). Colour and font values are Tailwind tokens in `src/app/globals.css`.
