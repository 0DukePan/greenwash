# 04: Twins stage over adjudicated legitimate records

**What to build:** the twins stage runs after adjudication, pairs each adjudicated positive with same-shape legitimate records using the twinning matcher, refuses to pair across repositories or with synthetic records, and writes the pair list with similarity scores as an artifact with input hashes. It refuses when adjudication is incomplete.

**Blocked by:** 03 (labeling and adjudication).

**Status:** ready-for-agent

- [ ] Adjudicated positives are paired with legitimate twins and the scores are recorded
- [ ] A cross-repository or synthetic candidate is refused as a twin by name
- [ ] The stage refuses while adjudication is incomplete
- [ ] The pair list names every positive with no twin and why
