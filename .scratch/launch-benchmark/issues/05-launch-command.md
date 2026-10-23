# 05: Launch command, refusals and byte-stable outputs

**What to build:** one command runs the launch benchmark end to end and answers with exactly three outcomes, distinguishable by exit code and by artifacts: LAUNCH writes the report and decision record, NARROW writes both and is publishable, REFUSED writes neither. The seven refusal conditions are enforced before any evaluation: drifted artifacts, drifted thresholds, drifted configuration, a reused manifest with a changed detector, a gate input that is planted, synthetic, dev or incomplete, any attempted network access, and a missing baseline pin. The command runs offline. The report and decision record are generated, never typed, and byte-identical across runs, locales, time zones and line-ending settings, with the single `generated_at` field excluded by field name; CI rebuilds and compares them, so a hand-edited report fails.

**Blocked by:** 01 (pre-registration and ledger), 02 (gate-input hygiene), 04 (criteria engine).

**Status:** ready-for-agent

- [ ] LAUNCH exits 0, writes both artifacts; NARROW exits 1; REFUSED exits 2 and writes neither
- [ ] Each of the seven refusals triggers on its own fixture and names its cause
- [ ] The report and decision record rebuild byte-identically twice, and under a different locale, time zone and CRLF checkout
- [ ] CI comparison fails on a hand-edited report
- [ ] The run completes with network access blocked, and any connection attempt fails the run
- [ ] The decision record lists decision, deciding criterion, all failing criteria, per-criterion value, threshold, interval and effective n, configuration ids, hashes and the pre-registration hash
