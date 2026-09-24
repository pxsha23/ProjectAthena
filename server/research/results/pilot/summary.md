# Paper 1 benchmark: strict schema handoffs vs naive free text

Generated 2026-09-24 05:47 UTC from `research/results/pilot/pipelines.csv`.

| Measure | strict | naive |
|---|---|---|
| Pipelines | 3 | 3 |
| Completed all stages | 3/3 | 3/3 |
| Code produced (files > 0) | 3/3 | 2/3 |
| All code checks passed | 33% (1/3) | 0% (0/3) |
| Check: spec_has_core_features | 100% (3/3) | 100% (3/3) |
| Check: spec_has_target_users | 100% (3/3) | 100% (3/3) |
| Check: stack_covers_layers | 100% (3/3) | 100% (3/3) |
| Check: files_parse | 67% (2/3) | 0% (0/2) |
| Check: python_lint | 67% (2/3) | 100% (2/2) |
| Check: python_dependencies_declared | 33% (1/3) | 100% (1/1) |
| Check: node_dependencies_declared | 33% (1/3) | 0% (0/2) |
| Check: code_matches_stack | 100% (3/3) | 33% (1/3) |
| Backend detected for deployment | 100% (3/3) | 100% (2/2) |
| Deployment matches chosen stack | 100% (3/3) | 0% (0/2) |
| Time per pipeline (min) | 13.6 ± 3.2 | 16.5 ± 7.1 |
| Input tokens | 3431 ± 930 | 2013 ± 159 |
| Output tokens | 2961 ± 862 | 3679 ± 1652 |
| Schema retries per pipeline | 0.33 ± 0.58 | 0.00 ± 0.00 |

Rates are over the pipelines where the check ran; values are mean ± standard deviation. Per-file checks (files_parse, python_lint, dependency checks) count only pipelines that produced at least one file, since they pass trivially on no files.

## Setup

- Model: qwen2.5-coder:7b via Ollama (context 16384 tokens, temperature 0.2)
- Ideas: 3 (habit-buddy, shopping-list, study-groups); repeats per idea and mode: 1
- Stages: idea, stack, code; schema retry limit (strict): 2
- Refusal fallback: off; code version: eaa8ceb

## Methods paragraph (draft for the synopsis)

We compared two handoff designs in a three-agent pipeline (Idea, Tech Stack, Code) using the same locally hosted model (qwen2.5-coder:7b). In the strict condition, every agent returned output that had to validate against a Pydantic schema with unknown fields rejected; invalid output was retried up to 2 times with the validation error fed back. In the naive condition, agents exchanged free Markdown text with no validation or retries, and files were extracted from the Code Agent's text with a lenient parser. Both conditions used identical role instructions and were evaluated with the same static consistency checks (syntax, pyflakes lint, declared Python and npm dependencies, code matching the chosen stack, spec completeness) and rule-based deployment detection. No generated code was executed. We ran 3 app ideas in each condition (6 pipelines in total).
