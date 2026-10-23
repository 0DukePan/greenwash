# 02: Gate-input hygiene and hostile repository content

**What to build:** the corpus kit can no longer feed a gate with a case that should not decide one. A gate-input class admits only real, adjudicated cases: planted, synthetic and dev-split records are rejected, records missing source, repository identity, license, technique or split are rejected naming the field, and any class holds at most five cases per repository. The builder reads repository objects only and treats them as untrusted: no repository code, hooks or filters run, repository-supplied git configuration is ignored, paths escaping the work tree are rejected, and file sizes and counts are bounded. Cases that need replay use the integrity-checked sandbox or a recorded, hashed replay result.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A planted, synthetic or dev record in a gate-input class is rejected; kept out, the gate numbers are identical
- [ ] A record missing a required field is rejected with the field named
- [ ] A class with more than five cases from one repository is rejected or capped, per one documented rule
- [ ] Hostile fixture repositories create no canary file, touch nothing outside the work tree, and are rejected
- [ ] The builder runs no repository code, hooks or filters and honors no repository git configuration
