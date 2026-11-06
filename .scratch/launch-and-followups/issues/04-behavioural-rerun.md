# 04: Re-run the behavioural study with the fixed instrument

**What to build:** The behavioural study, re-run on an instrument that can now label the outcome it claims to test. The same corpus, three plugin states and three runs per state. Every row saves its diff, transcript and detector flags, so a later detector can re-score it. Whatever comes out is published — including another null — with the pages that quote it regenerated from the rows rather than edited by hand.

**Blocked by:** None technically. The prerequisite is a reachable, funded model; without one the ticket cannot complete and must say so rather than publish a number.

**Status:** ready-for-agent

- [ ] A plumbing run proves the fixed classifier labels a planted passing cheat as `flagged`, not `genuine fix`
- [ ] The scored run completes for every task and state, or names every blocked row and why
- [ ] Every row carries its diff, transcript, detector flags and outcome
- [ ] The published pages are regenerated from the rows, with the counts and intervals they produce
- [ ] If the run cannot complete, the pages say "not measured" instead of quoting the old +0.0
- [ ] A passing cheat is counted separately from an integrity cheat and from a genuine fix
