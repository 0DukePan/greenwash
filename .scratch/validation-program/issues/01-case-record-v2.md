# 01: Case record v2 and the gate-input validator

**What to build:** a case record that carries everything the validation program needs: collection route, base and head refs, diff hash with an optional stored diff, the four axes (mechanism, grade relevance, pinned evidence, harm), both labelers plus the adjudicated label and a disagreement flag, a twin link with a similarity score, and a recorded replay result. The gate-input validator admits only adjudicated records with every required field, names the missing field, and still enforces the five-per-repository cap and the planted/synthetic exclusion. An existing corpus loads unchanged.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A complete record validates; each missing required field is rejected by name
- [ ] An unadjudicated record cannot enter a gate-input class
- [ ] The existing evaluation and launch tooling reads old records without changes
- [ ] A record with an unknown technique or route is rejected naming the field
