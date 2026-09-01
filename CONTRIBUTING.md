# Contributing to InkToFilm

InkToFilm is interested in evaluation code that is reproducible, inspectable, and useful during model
development.

## Before opening a pull request

1. Explain the failure mode the check detects.
2. State whether the check is deterministic, model-based, or human-calibrated.
3. Preserve evidence such as time intervals, regions, frames, or judge provenance.
4. Add a focused test, including at least one failure case.
5. Run `ruff check .` and `pytest -q`.

Avoid metrics whose implementation or prompt cannot be inspected. A provider adapter is welcome,
but the core must remain usable offline.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
```
