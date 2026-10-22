# 07: Corpus kit with task-level splits and a frozen manifest

**What to build:** a case record that carries source, technique, label, split, task and repository identity, and license. Splits are enforced by task identity, so a task in development can never appear in the frozen set. The frozen manifest is hash-recorded and verified on load. Synthetic injected tampers live in a separate class and are excluded from gate inputs by construction. Validation errors name the offending field.

**Blocked by:** 02 (taxonomy).

**Status:** ready-for-agent

- [ ] A task appearing in both dev and frozen splits is rejected
- [ ] The manifest round-trips and a tampered case file fails the hash check
- [ ] Synthetic records are loadable but never count toward a gate
- [ ] Double-labeling inputs can be generated from the records for blind annotation
