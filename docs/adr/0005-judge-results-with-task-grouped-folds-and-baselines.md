# ADR-0005: Judge Results with Task-Grouped Folds and Baselines

## Status

Accepted

## Context

A failure predictor can look good for the wrong reasons.
If the same task appears in training and testing, the model can memorize tasks.
Long runs fail more often, so a behaviour result may only be a disguised run length.
For an early check, a prefix defined as a fraction of a run reveals the run's total length, and with a prefix of a fixed number of steps every run has the same step count so far, which makes a step-count baseline useless.
Most prior papers found did not report a length or duration baseline, and only one used one.

## Decision

Folds are grouped by task so that no task appears in both training and testing.
Only tasks with mixed pass and fail outcomes across trials are used.
The analysis has two parts.
The first part (Q3a) describes finished runs by their behaviour trajectory and compares a classifier on that profile with run length alone and with a trained supervised predictor.
The second part (Q3b) is an offline early check on the first k steps for k in 5, 10 and 15, using only runs with at least k steps, and the number dropped at each k is reported.
The Q3b baseline is counts so far (errors and different tools used in the first k steps), because the public dataset records tokens and time per trial and not per step.
Whole-run length is drawn on the early-check figure only as a reference line labelled as unfair because it uses information from the future.
Scores are AUROC with bootstrap ranges.
All thresholds are written in the PRD and frozen at the git tag `prereg` before results exist.

## Consequences

- Any claim that behaviours describe or warn about failure is tied to a fair baseline.
- The whole-run result is easy to read and shows whether an early check has a chance.
- The number of usable tasks may be small, which widens the ranges and is reported honestly.
- Runs shorter than k are excluded from the early check, which can bias it toward longer runs.
- The early check only measures whether a warning would have been right, and does not restart or cancel anything.

## Alternatives

- **Random splits:** Rejected because they leak task information and inflate scores.
- **Prefixes as a fraction of run length:** Rejected because they leak the run's total length.
- **A step-count baseline on fixed-length prefixes:** Rejected because the count is the same for every run.
- **Claiming a new predictor:** Rejected because the prediction side is well covered by prior work and is only a benchmark here.
