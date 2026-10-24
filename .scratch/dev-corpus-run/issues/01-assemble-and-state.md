# 01: Dev-run assemble stage and checkpoint state

**What to build:** the dev-run command exists and its first stage works. `assemble` takes candidate records from the miners and importers, deduplicates by diff hash across routes, enforces the five-per-repository cap per class, requires a route and a taxonomy technique, refuses any adjudicated record, warns when a class is under the dev minimum, and writes a versioned dev manifest with input hashes plus counts by route and class. A bare invocation prints the current stage and the next required one; an out-of-order stage is a refusal by name. Everything is validated through the corpus kit's existing gate-admission rules.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Assembling a fixture candidate set yields a manifest, counts by route and class, and no adjudicated record
- [ ] A duplicate diff hash, an over-cap repository, a synthetic record and a missing field are each refused by name
- [ ] Re-running assemble on changed inputs replaces the manifest and records the new input hashes
- [ ] A bare invocation names the next stage; an out-of-order stage is refused by name
