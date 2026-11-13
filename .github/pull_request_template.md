## What this changes

<!-- One sentence. If it needs three, say what the user sees. -->

## The receipt

<!-- Greenwash's own rule: no claim without the command and its output. -->

```
$ command
output
```

## Which gate does this belong to

- [ ] Shipped behaviour (`greenwash/`, hooks, plugins) — run `pytest -q -m "not program"`
- [ ] The detector (`greenwash/scan/rules/`) — the README rule table and a positive + negative test
- [ ] The benchmark or corpus (`benchmark/`) — `python benchmark/verify.py`
- [ ] Documentation only

## If this changes a published number

- [ ] The artifact was regenerated, not edited by hand
- [ ] The pages that quote it were regenerated or updated, and `pytest tests/test_readme.py tests/test_launch_docs.py tests/test_claim_ledger.py` passes
- [ ] The claim ledger's wording still covers what the new number supports

## Anything you had to work around

<!-- A test that was already failing, a flaky check, a rule this change does not
fix. Say it here rather than in a code comment -- the next person reads this. -->
