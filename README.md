# HyperStimulation website

Website for the HyperStimulation project: how stimulating are children’s videos?

- [`frontend/`](frontend/README.md): Next.js static site (GitHub Pages)
- [`backend/`](backend/README.md): Python API (FastAPI) with the video dataset and analysis pipeline
- [`plans/`](plans/): numbered design and implementation plans

## Run locally

Install the prerequisites from the two dev guides ([nvm](https://github.com/nvm-sh/nvm) with the Node version in `frontend/.nvmrc`, and [uv](https://docs.astral.sh/uv/getting-started/installation/)), then:

```sh
./dev.sh          # backend on :8000 and frontend on :3000, using the real backend
./dev.sh --mock   # frontend only, with mock data
```

It installs missing dependencies, prefixes each line of output with `[backend]` or `[frontend]`, and stops both apps on Ctrl+C or when either one exits. Change the ports with `BACKEND_PORT` / `FRONTEND_PORT`. The settings that must match the ports or suit local development (`NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_API_MOCK`, `CORS_ORIGIN`, `DATASET_PATH`, `ANALYSIS_DIR`, and `ANALYSIS_LIMIT_PER_IP=0`: no limit on live analyses) are set by the script for that run and override `backend/.env` and `frontend/.env.local`; everything else in those files still applies. To run one app on its own, see its README.
