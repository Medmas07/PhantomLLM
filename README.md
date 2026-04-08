# PhantomLLM

Multi-provider LLM assistant that runs through browser UIs (Playwright) and exposes both:
- an interactive CLI
- an OpenAI-compatible HTTP API

## Project purpose

This project is built as an academic alternative for LLM API credits and usage limits.  
Instead of calling paid model APIs directly, it automates browser-based chat interfaces and keeps a local workflow for experimentation, orchestration, and tooling research.

The long-term goal is to keep expanding and maintaining compatibility with as many LLM browser UIs as possible.

Important: this project is for educational, research, and testing use.  
It is not a guarantee of production-grade reliability against third-party UI changes.
## Demo
[🎥 Watch Demo](https://github.com/Medmas07/PhantomLLM/releases/download/untagged-87ac9fe487697d4568a2/demo.mp4)
## Core features

- Multi-provider routing (`ChatGPT`, `Gemini`, `Perplexity`, and more providers in progress)
- Single Playwright worker with one persistent browser context and provider-specific tabs
- Configurable fallback chain across providers (`fallback_enabled`, `fallback_models`)
- CLI chat loop with history management
- OpenAI-compatible endpoint: `POST /v1/chat/completions`
- Tool/action execution protocol (`<ACTION>...</ACTION>`) for local file operations
- Browser session reuse with persistent Chrome profile

## Architecture overview

- `agent/main.py`
  - Entry point
  - Mode selection (`cli` or `api`)
  - Provider menu and browser-worker bootstrap

- `agent/worker.py`
  - Dedicated Playwright thread
  - Tab lifecycle per provider
  - System prompt injection
  - Message send/receive loop
  - Action execution round-trip (`TOOL_RESULT`)

- `agent/models/router.py`
  - Model alias to provider-module mapping
  - Dispatches calls to provider `generate()`

- `agent/models/providers/*.py`
  - Provider-specific browser logic (selectors, send flow, response extraction)

- `agent/api_server.py`
  - FastAPI app
  - OpenAI-compatible chat endpoint
  - Model listing and status endpoints

- `agent/tools/*`
  - File tools, path safety, backups, patching, base64 helpers

## Requirements

- Python 3.11+ recommended
- Google Chrome / Chromium recommended (auto-detection for Windows/Linux)
- Dependencies in `requirements.txt`:
  - `fastapi`
  - `uvicorn[standard]`
  - `pydantic`
  - `playwright`
  - `camoufox`

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

## Docker (Camoufox hidden by default)

This repository includes a production-ready container setup for Linux/Windows hosts (Docker Desktop or Docker Engine).

Default container behavior:
- API mode
- `camoufox` backend
- hidden browser (`headless=true`)
- listening on `0.0.0.0:8000`

Build image locally:

```bash
docker build -t phantomllm:camoufox-hidden .
```

Run container:

```bash
docker run --rm -p 8000:8000 phantomllm:camoufox-hidden
```

Run with Docker Compose:

```bash
docker compose up -d --build
```

Runtime environment variables:
- `PHANTOM_MODE` (`api` or `cli`)
- `PHANTOM_MODEL` (for example `openai_ui`)
- `PHANTOM_BROWSER` (`camoufox` or `playwright`)
- `PHANTOM_HEADLESS` (`true` or `false`)
- `PHANTOM_HOST` (default `0.0.0.0`)
- `PHANTOM_PORT` (default `8000`)

Example override (visible Camoufox):

```bash
docker run --rm -p 8000:8000 -e PHANTOM_HEADLESS=false phantomllm:camoufox-hidden
```

### Publish to Docker Hub

```bash
docker login
docker tag phantomllm:camoufox-hidden <dockerhub-user>/phantomllm:camoufox-hidden
docker push <dockerhub-user>/phantomllm:camoufox-hidden
```

## Configuration

Edit `agent/config/config.json`:

- `mode`: default runtime mode (`cli` or `api`)
- `default_model`: default provider key (for example `openai_ui`)
- `browser_backend`: `playwright` or `camoufox`
- `camoufox_fetch_prompted`: internal flag to avoid repeating first-time Camoufox cache prompt
- `fallback_enabled`: enables runtime fallback attempts when a provider fails
- `fallback_models`: ordered provider/model aliases used as fallback candidates
- `headless`: `false` shows the browser, `true` hides it
- `workspace`: writable workspace root for tool actions
- `providers.openai_ui.profile_dir`: persistent Chrome profile directory
- `providers.openai_ui.executable_path`: Chrome/Chromium executable path (optional; auto-detected when possible)

First-time interactive behavior:
- If `browser_backend=playwright` and Chromium/Chrome path is missing/invalid, the launcher asks for it and saves it.
- If `browser_backend=camoufox` with `headless=true`, the launcher asks once if it should run `python -m camoufox fetch` to cache browser binaries for background use.
- In interactive mode, the launcher now suggests runtime choices: `Camoufox hidden`, `Camoufox visible`, or `Your browser (Playwright)`.

## Fallback system

If a provider call fails at runtime (timeout, UI break, transient errors), the router can automatically retry using fallback models from `fallback_models`.

Default chain:
1. requested model
2. `default_model`
3. `fallback_models` (in order)
4. final safety fallback: `openai_ui`

## Run the project

### Interactive launcher

```bash
python -m agent.main
```

You can choose:
- runtime mode (`CLI` or `API`)
- model/provider from the menu

### CLI directly

```bash
python -m agent.main --cli --model gemini_ui
```

With explicit browser backend + visibility:

```bash
python -m agent.main --cli --model openai_ui --browser camoufox --show-browser
python -m agent.main --cli --model openai_ui --browser camoufox --hide-browser
```

### API server directly

```bash
python -m agent.main --api --model openai_ui --host 127.0.0.1 --port 8000
```

## API endpoints

- `POST /v1/chat/completions` (OpenAI-compatible)
- `GET /v1/models`
- `GET /status`
- `POST /message` (legacy endpoint)

Example:

```bash
curl http://127.0.0.1:8000/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"gemini_ui\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}"
```

## Provider status (current)

- `openai_ui`: stable
- `gemini_ui`: stable
- `perplexity_ui`: unstable / in progress
- `claude_ui`, `deepseek_ui`, `grok_ui`, `qwen_ui`: scaffolding/ongoing 
- `meta_ui`, `baidu_ui`: listed but not implemented

## Safety and limitations

- Browser automation may violate provider Terms of Service.
- Accounts may face temporary/permanent restrictions.
- Use a secondary account for testing.
- Response timings and selectors can break when provider UIs change.
- Educational/testing use only; validate outputs before real-world decisions.

## Production notes (Windows + Linux)

- Prefer `--api` mode behind a process manager:
  - Windows: NSSM / Task Scheduler / service wrapper
  - Linux: systemd or supervisor
- Run with a dedicated browser profile directory and service account.
- Keep `fallback_enabled=true` in production-like tests.
- Add monitoring on `/status` and restart on persistent failures.
- Pin dependency versions and update selectors regularly as UIs evolve.

## Open source contributions

Contributions are welcome and encouraged.

- Improve provider stability and selector resilience.
- Implement missing providers/models and expand aliases.
- Improve fallback strategy and health/error reporting.
- Improve cross-environment compatibility (Windows/Linux/macOS, CI, containers).
- Add tests, docs, and reproducible bug reports.

Please open an issue or pull request. See `CONTRIBUTING.md` for guidelines.

For responsible usage:
- keep contributions focused on reliability, transparency, and maintainability
- treat this project as educational/research/testing software, not guaranteed production compliance with third-party UIs

## License

This project is licensed under the MIT License.
See the `LICENSE` file for full text.

## Notes for development

- Add or adjust provider selectors in `agent/models/providers/`
- Keep provider send/wait/extract logic isolated per UI
- Prefer updating a single provider module when a UI changes
- Use `agent/workspace/` for action-generated files
