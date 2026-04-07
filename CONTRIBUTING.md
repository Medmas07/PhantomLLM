# Contributing to PhantomLLM

Thanks for helping make PhantomLLM stronger.

## Scope we especially welcome

- Provider implementations for missing models/UIs
- Selector robustness improvements when vendor UIs change
- Fallback and reliability improvements
- Windows/Linux compatibility fixes
- Tests, docs, and reproducible bug reports

## Development setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r PhantomLLM/requirements.txt
playwright install
```

Optional for Camoufox backend:

```bash
python -m camoufox fetch
```

## Pull request guidelines

- Keep PRs focused and small when possible.
- Include clear repro steps for bugs.
- Update docs/config examples when behavior changes.
- Preserve compatibility across Windows and Linux when touching paths/process/browser startup.
- Never commit secrets, cookies, or personal profile data.

## Testing expectations

- Run the app in CLI mode for a basic smoke test.
- Run API mode and verify `/status` and `/v1/chat/completions`.
- For provider changes, include at least one realistic manual test flow.

## Project usage intent

This project is intended for educational, research, and testing use.  
Please avoid unsafe or policy-violating automation usage.
