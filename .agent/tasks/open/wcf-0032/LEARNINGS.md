# Learnings
- 2026-11-06 [testing] — When mutating `src/` by hand and rerunning pytest within the same second, a mutant of the same byte size as the one before can run from a stale `__pycache__` .pyc (CPython checks source mtime in seconds and size). Set `PYTHONDONTWRITEBYTECODE=1` and remove `src/**/__pycache__` before each mutant run.
