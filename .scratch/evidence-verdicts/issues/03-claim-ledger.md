# 03: Claim ledger gating public wording

**What to build:** a data-driven claim ledger where every public sentence pattern maps to the evidence it needs, its current status, and the strongest wording allowed today. A docs test fails when a public page claims more than the ledger licenses, and the limits page renders its claim table from the same data.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A planted over-claim in a public page makes the suite fail, naming the claim
- [ ] Every claim in the positioning plan has a ledger row with allowed wording
- [ ] The rendered limits-page table matches the ledger verbatim
- [ ] Numbers quoted in allowed wording come from generated artifacts, not prose
