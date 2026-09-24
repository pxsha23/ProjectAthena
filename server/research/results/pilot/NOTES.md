# Pilot run notes

- Run: 3 ideas (study-groups, shopping-list, habit-buddy) x strict/naive x 1 repeat, qwen2.5-coder:7b via
  Ollama on a CPU-only laptop, 2026-09-23 to 2026-09-24.
- Rerun: the first attempt of shopping-list / naive failed at the code stage with "Could not reach Ollama"
  after 8.5 hours (the machine slept, so the model server stopped answering). This is an infrastructure fault,
  not a result of the naive handoff, so that row was removed and the pipeline was run again.
  The original rows are kept in `pipelines.before-rerun.csv.bak`.
- In the rerun, the naive Code Agent answered but no files could be extracted from its text (0 files).
  This counts as a naive handoff failure.
- Per-file checks (files_parse, python_lint, dependency checks) pass trivially when there are no files, so
  `summary.md` counts them only over pipelines that produced at least one file.
