# Evals

Eval suites in the `claude plugin eval` layout: one directory per case, each with a
`prompt.md` (what a real user would type) and `graders/criteria.md` (what a correct
run observably does).

```bash
claude plugin eval . --report evals/report.html
claude plugin eval . --case "caption-*"          # one case
```

`plugin eval` is early-access as of 2026-08; until it is enabled on your account these
run as documentation of intended behavior, and the deterministic half of every criterion
is already enforced by each skill's `tests/run_tests.sh`.

Two kinds of case, deliberately mixed:

- **Routing** — a colloquial ask with no skill named. Grades whether the right skill
  triggered at all. The SKILL.md descriptions are load-bearing; these cases catch
  description drift the way the fixtures catch gate drift.
- **Behavior** — grades that the run obeyed the skill's laws: gates actually executed,
  refusals actually refused, nothing fabricated, nothing sent.

When a case fails: fix the SKILL.md description (routing) or the skill's laws/scripts
(behavior) — never weaken the grader to pass.
