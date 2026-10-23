# 02: History miners R1 and R2

**What to build:** a miner that reads repository history as git objects only and proposes candidate cases: R1 for commits that change an assertion, delete a test or add a skip alongside a source change; R2 for edits later reverted or fixed by a linked commit. Each candidate carries its route, refs, diff hash, repository identity, license and the technique it looks like, and is written as an unadjudicated record for a human to label. Repository code, hooks, filters and repository-supplied git config are never executed or honoured.

**Blocked by:** 01 (case record shape).

**Status:** ready-for-agent

- [ ] Mining a fixture repository yields the expected candidates with refs and diff hashes
- [ ] A revert or later fix is attached to its candidate as supporting history
- [ ] Hostile repository content cannot execute code or escape the work tree
- [ ] Candidates are written unadjudicated and cannot enter a gate input
