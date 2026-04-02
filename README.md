# PhantomLLM

Multi-provider LLM assistant that runs through browser UIs (Playwright) and exposes both:
- an interactive CLI
- an OpenAI-compatible HTTP API

## Project purpose

This project is built as an academic alternative for LLM API credits and usage limits.  
Instead of calling paid model APIs directly, it automates browser-based chat interfaces and keeps a local workflow for experimentation, orchestration, and tooling research.

The long-term goal is to keep expanding and maintaining compatibility with as many LLM browser UIs as possible.

## Core features

- Multi-provider routing (`ChatGPT`, `Gemini`, `Perplexity`, and more providers in progress)
- Single Playwright worker with one persistent browser context and provider-specific tabs
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
- Google Chrome installed (Windows path is configured in `agent/config/config.json`)
- Dependencies in `requirements.txt`:
  - `fastapi`
  - `uvicorn[standard]`
  - `pydantic`
  - `playwright`

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

## Configuration

Edit `agent/config/config.json`:

- `mode`: default runtime mode (`cli` or `api`)
- `default_model`: default provider key (for example `openai_ui`)
- `workspace`: writable workspace root for tool actions
- `providers.openai_ui.profile_dir`: persistent Chrome profile directory
- `providers.openai_ui.executable_path`: Chrome executable path

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
- `claude_ui`, `deepseek_ui`, `grok_ui`, `qwen_ui`: scaffolding/ongoing stabilization
- `meta_ui`, `baidu_ui`: listed but not implemented

## Safety and limitations

- Browser automation may violate provider Terms of Service.
- Accounts may face temporary/permanent restrictions.
- Use a secondary account for testing.
- Response timings and selectors can break when provider UIs change.

## Notes for development

- Add or adjust provider selectors in `agent/models/providers/`
- Keep provider send/wait/extract logic isolated per UI
- Prefer updating a single provider module when a UI changes
- Use `agent/workspace/` for action-generated files
