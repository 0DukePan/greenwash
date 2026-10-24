# 06: Evaluate stage over the dev split

**What to build:** the evaluate stage adapts the assembled v2 records for the existing evaluation runner, runs the detector over the dev split, records the detector configuration id and hash, and writes the evaluation table Gate A consumes, with provenance hashes. It refuses when adjudication is incomplete, when twins are missing, or when a record is not in the dev split.

**Blocked by:** 05 (baselines).

**Status:** ready-for-agent

- [ ] The dev split produces the evaluation table through the existing runner, with no separate table format
- [ ] The detector configuration id and hash are recorded in the artifact
- [ ] Incomplete adjudication, missing twins or a non-dev record is refused by name
- [ ] The table carries the hashes of the records it was computed from
