# Offline evaluation

`make eval` runs a deterministic 100-case synthetic contract baseline plus 40
pattern pairs, 30 material-change pairs, and 10 temporal queue scenarios. It
tests the shape and safety invariants of the pipeline without a model key or
network access.

This baseline is deliberately **not** evidence that a live Gemini model meets
the launch quality gates. Before activation, the synthetic cases must be
supplemented or replaced by at least 100 human-labelled, permitted historical
reports with a locked holdout, and `eval-live.yml` must approve the exact model
and behavior hash. The distinction prevents a fixture that was written to the
expected answer from being presented as real-world model quality.

Reports are written to ignored `work/evals/`; the versioned policy and synthetic
catalog remain under `evals/gold/` and `evals/expected/`.
