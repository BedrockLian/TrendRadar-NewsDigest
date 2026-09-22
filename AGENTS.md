# Repository Guidelines

## Project Structure & Module Organization

This private news workbench uses Python 3.14, Django 5.2, PostgreSQL 18, and server-rendered templates with HTMX.

- `app/core/`: configuration, authentication, views, CLI, durable tasks, and storage management.
- `app/news/`, `app/briefs/`, `app/events/`, `app/ai/`: ingestion, immutable briefings, event timelines, and Responses API integration. Keep models, services, and migrations within their owning modules.
- `app/ui/templates/` and `app/ui/static/`: shared pages, CSS, JavaScript, and self-hosted fonts.
- `tests/`: pytest integration tests and standalone Playwright checks.
- `deploy/` and `docs/`: deployment utilities, architecture, and operations guidance.
- `.local/`: ignored credentials, runtime data, screenshots, and temporary scripts.

## Build, Test, and Development Commands

Run commands from the repository root. Configure a local PostgreSQL database and `.local/dev.env` using `deploy/app.env.example`; enable `RADAR_DEBUG=1` for local HTTP.

```powershell
uv sync --frozen
uv run --env-file .local/dev.env radar migrate
uv run --env-file .local/dev.env python -m django collectstatic --noinput
uv run --env-file .local/dev.env radar serve
uv run --env-file .local/dev.env pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
```

These install locked dependencies, migrate the database, collect assets, serve on localhost:18081, and validate code. Run `radar scheduler` and `radar worker collect|maintenance|ai` in separate terminals with the same environment-file prefix when exercising background work.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions/modules, and `PascalCase` classes. Ruff targets Python 3.14 with a 110-character line limit. Keep shared UI styles in semantic theme variables; support both themes without duplicating page markup. Add lasting operational commands through `radar`, not loose root-level scripts.

## Testing Guidelines

Use pytest and pytest-django with PostgreSQL; name tests `tests/test_*.py` and functions `test_*`. No numeric coverage threshold is configured. Cover changed behavior, especially deduplication, fixed references, task recovery, and authentication.

With the local server running, execute `uv run python tests/browser_redesign.py` for theme and responsive checks. Browser checks require local credentials and write artifacts to `.local/`. Use an isolated local database and inspect screenshots for visual changes.

## Commit & Pull Request Guidelines

Existing commits use concise Chinese descriptions; no mandatory prefix scheme exists. Keep commits focused. PRs should describe the problem, resulting behavior, verification performed, and any migration or deployment implications. Link relevant issues and include screenshots for UI changes.

## Security & Agent Workflow

Never commit credentials, backups, or `.local/` artifacts. Read `docs/operations.md` before deployment or destructive maintenance. Preserve unrelated changes. For substantial frontend work, load `frontend-orchestrator` and complete its required verification before claiming completion.
