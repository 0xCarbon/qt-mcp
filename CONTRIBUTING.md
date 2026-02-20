# Contributing

Thanks for contributing to `qt-mcp`.

## Development Setup

```bash
git clone https://github.com/0xCarbon/qt-mcp.git
cd qt-mcp
uv sync --extra dev
```

## Local Checks

Run these before opening a pull request:

```bash
uv run ruff check src tests
uv run pytest -v
```

If you add or change behavior, include tests in `tests/`.

## Pull Requests

- Keep PRs focused and small when possible.
- Update `README.md` when user-facing behavior changes.
- Update `CHANGELOG.md` for notable changes.
- Make sure CI passes.

## Commit Messages

Use clear commit messages that describe intent and impact.

## Licensing

By submitting a contribution, you agree that your contribution is licensed under
`MIT OR Apache-2.0`.
