# Offline evaluation

`make eval` runs a deterministic 100-case synthetic contract baseline plus 40
pattern pairs, 30 material-change pairs, and 10 temporal queue scenarios. It
tests the shape and safety invariants of the pipeline without a model key or
network access.

This baseline is deliberately **not** evidence that any live model meets the
launch quality gates. `run_live_eval.py` is a dormant, manually invoked entry
for a separately approved provider and permitted, human-labelled data. It has
no scheduled workflow. The distinction prevents a fixture written to its
expected answer from being presented as real-world quality.

## Human labelling before a live trial

Prepare at least 100 permitted historical reports, remove personal details,
record source permission and provenance outside the model input, then lock the
holdout and its SHA-256 before evaluating candidates. Two independent people
label relevance, category, required response actions, whether each candidate
is the same scam pattern, and whether the change is material. Adjudicate every
disagreement before freezing the labels. Keep the source text and labels only
in ignored local `work/`; the report contains case IDs, counts and scores, not
text. Split the locked dataset into batches of at most 50 cases; combine all
batches before checking the gates in `evals/expected/quality-gates.json`. Use
the same split and behavior hash for each candidate. Failed calls remain in
`failed_cases`, cannot be dropped from the dataset, and prevent any launch
claim even when the reported precision/recall figures look high.

Each case is a JSON object with `id`, `text`, `expected_relevant`, and, for a
relevant report, `expected_category` and `expected_actions`. For pattern
comparison, include `candidate_revisions`, `expected_same_pattern`, and
`expected_material_change`. Record the label rubric and adjudication separately
under ignored `work/` to avoid turning real source text into a tracked fixture.

The local protocol run uses `--local-endpoint http://127.0.0.1:<port>/...` and
synthetic cases. The live path requires a separate exact activation, one selected
configured HTTPS endpoint, a dedicated key, a verified price/region/quota/account
hard limit record under ignored `work/`, and current `price_verified` model
configuration. Its hard ceiling is 10 attempts and $1 per run, further limited
by the approved account cap. The budget reserves a conservative maximum before
each attempt, including invalid responses and retries; exhaustion denies the
request before it leaves the process. Outputs always say
`launch_qualified=false`. Real model quality and launch eligibility remain
unverified until the authorized trial, manual error review, and the separate
release decision.

Reports are written to ignored `work/evals/`; the versioned policy and synthetic
catalog remain under `evals/gold/` and `evals/expected/`.
