# 05: Twin matching and hard-case cards

**What to build:** given a positive, find legitimate twins of the same surface shape (same AST-level edit class, similar diff size) and record a similarity score per pair, so H2 and H3 measure false alarms against realistic neighbors. A hard-case card schema captures family, route, refs, the edit, the stated reason, the pinned-evidence verdict, the axes, the twin link, labels, expected verdicts and split. The HC1, HC4 and HC11 families ship twelve dev cards each, generated from the maintainer fixtures and clearly labeled as such.

**Blocked by:** 01 (case record shape), 04 (labels exist for cards).

**Status:** ready-for-agent

- [ ] A positive with a same-shape legitimate edit is paired, and the score is recorded
- [ ] A card missing a required field is rejected by name
- [ ] Twelve dev cards exist for each of HC1, HC4 and HC11 and validate
- [ ] Matching never pairs across repositories and never pairs a positive with a synthetic record
