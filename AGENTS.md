# AGENTS.md

## Project

BuildAI is a Python desktop app for architects. It connects an AI agent to Blender, AutoCAD, SketchUp, and Revit so users can control those programs via natural language. The server is FastAPI on `127.0.0.1:8600`, displayed in a native pywebview window. Python 3.11+.

All code, comments, docstrings, variable names, and UI text are in **Spanish**. Maintain this convention.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Run the app
python -m buildai.main

# Run all tests
python -m pytest tests -q

# Run a single test file
python -m pytest tests/test_entregables.py -q

# Run a single test class or method
python -m pytest tests/test_entregables.py::TestRutaPara::test_sanea_nombre -q

# Install Playwright browser (needed only for UI integration tests)
python -m playwright install chromium
```

No linter, formatter, or typecheck is configured. There is no `ruff`, `flake8`, `mypy`, or `black` in the project.

## Architecture

```
buildai/              The only package — server, agent, connectors, providers, UI, resources
├── main.py           FastAPI app, uvicorn server, pywebview window (entrypoint: arrancar())
├── agent.py          Agent loop: sends messages to AI provider, executes tool calls, emits events
├── config.py         Persistent config (~/.buildai/config.json): provider, keys, models
├── rutas.py          Data paths — all user data goes to ~/.buildai/, never alongside code
├── modelos.py        Model catalog per provider (live queries + fallbacks + cache)
├── sesiones.py       Session persistence (~/.buildai/sesiones/*.json)
├── memoria.py        Learns user preferences from past sessions, injected into system prompt
├── conocimiento.py   Knowledge base: Markdown files with front-matter, FTS5 search via SQLite
├── entregables.py    Exported file pipeline (IFC, DWG, DXF, PDF, etc.) with whitelist validation
├── instalador.py     Auto-installs bridges into detected CAD/BIM programs
├── connectors/       Bridges to each CAD/BIM program
│   ├── base.py       Conector base class (disponible, herramientas, ejecutar)
│   ├── blender.py    HTTP bridge on port 8601
│   ├── autocad.py    Windows COM automation
│   ├── sketchup.py   HTTP bridge on port 8602 (Ruby extension)
│   ├── revit.py      HTTP bridge on port 48884 (pyRevit Routes)
│   ├── blender_kit.py   Export helpers (read as text, injected into Blender at runtime)
│   └── revit_kit.py     Export helpers (read as text, injected into Revit extension at runtime)
├── providers/        Adapters for AI APIs
│   ├── base.py       Proveedor base class, neutral history format, LlamadaHerramienta
│   ├── openai_compat.py  OpenRouter, OpenAI, Gemini, Ollama, OpenCode (OpenAI-compatible APIs)
│   └── anthropic_provider.py  Anthropic Claude (uses official SDK)
├── ui/               Static frontend (vanilla JS/CSS, no build step)
│   ├── index.html    Main app UI
│   ├── manual.html   Connection manual
│   ├── app.js        Frontend logic
│   ├── style.css     Styles
│   ├── icons.js      Icon definitions
│   └── assets/       Images (logo, favicon, .ico)
├── addons/           Bridges copied into each program at install time
│   ├── blender/      Python startup script for Blender
│   ├── sketchup/     Ruby plugin for SketchUp
│   └── revit/        pyRevit extension (Python, Routes API)
├── conocimiento_semillas/  25 seed knowledge files (*.md with front-matter)
tests/                All tests (unittest.TestCase style, run via pytest)
docs/                 Technical documentation (14 files, start at docs/README.md)
empaquetado/          PyInstaller spec + Inno Setup script + build_installer.ps1
website/              Static download landing page (unrelated to app server)
```

## Key constraints

- **`buildai/` is the sole copy of all resources.** Addons, knowledge seeds, UI, and skills are read from there at runtime. Do not create copies outside the package.
- **User data lives in `~/.buildai/`** (config.json, sessions/, conocimiento/, entregables/, renders/). Never write user data next to the code. This also avoids Microsoft Store Python's AppData virtualization issue.
- **Thread safety matters.** The agent runs in a separate thread. `_ocupado` (Lock) serializes conversation. `config._lock` protects config JSON. The queue between agent work and SSE avoids blocking the async event loop.
- **Defensive validation everywhere.** Path traversal is rejected (renders, entregables, session IDs). Attachments are sanitized (type, base64, size, count). Input from AI models is never trusted blindly.
- **History format is provider-neutral.** The `{tipo, texto, llamadas, ...}` format in `providers/base.py` is the contract. Each provider adapter translates to/from its own API format. Anthropic requires re-sending `_raw` blocks.
- **Limits are explicit and intentional.** 100 agent steps, 120 history entries, 8000 chars per fresh result, 600 for compressed old results, 12 images max, 8 MiB per attachment. Do not remove without analyzing impact.

## Testing

- All tests use `unittest.TestCase` (not bare pytest functions). This is intentional — bare functions were historically missed by unittest discovery.
- `tests/dobles.py` provides doubles for all four CAD/BIM programs: fake `bpy`/`mathutils` modules, COM document mocks, httpx mocks, and pyRevit stubs. These **write files to disk** because the real export code waits for files to appear.
- Tests run on Linux in CI (Ubuntu, Python 3.11 + 3.13) despite the app being Windows-only. `pywin32` is conditional on `sys_platform == 'win32'` in pyproject.toml.
- Playwright UI tests (`test_ui_entregables.py`) self-skip if Playwright is not installed.
- To test the Blender kit (`blender_kit.py`), use `tests/dobles.kit_blender()` context manager — the module can't be imported normally outside Blender.

## CI

`.github/workflows/pruebas.yml` runs `pytest tests -q` on push to master and on PRs. No linter, no typecheck, no pre-commit hooks.

## Packaging

Desktop installer: `powershell -File empaquetado\build_installer.ps1` — runs PyInstaller then Inno Setup. Output: `empaquetado/Output/BuildAI-Setup.exe`. The `.spec` file lists all bundled data paths.

## Deep references

`docs/README.md` maps 14 technical documents. Read the relevant one before modifying connectors (06), providers (07), skills/knowledge (08), sessions (09), or packaging (10). `docs/11-buenas-practicas.md` records existing conventions and tech debt. `docs/12-pruebas-y-desarrollo.md` covers debugging workflow.
