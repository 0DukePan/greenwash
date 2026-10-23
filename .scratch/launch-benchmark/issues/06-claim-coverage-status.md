# 06: Claim coverage and the README launch status

**What to build:** the launch report's announcement-wording section is rendered from the claim ledger, and the launch gate fails when an announcement draft contains a claim beyond its row's allowed wording, including registered paraphrases. A NARROW decision additionally produces the publishable narrowed-scope statement with the ledger's allowed wording. The README carries a launch status line generated from the decision record: `UNMEASURED` with no record, `NARROWED` naming the failing criteria, or `LAUNCH-READY`, and CI fails when the committed line differs from the generated one.

**Blocked by:** 05 (launch command and decision record).

**Status:** ready-for-agent

- [ ] A planted over-claim in the announcement draft fails the gate, and so does a registered paraphrase
- [ ] The announcement section and the narrowed-scope statement render from ledger data, not prose
- [ ] The README line shows UNMEASURED, NARROWED or LAUNCH-READY as the record changes, and CI fails on a hand-edit
- [ ] The NARROW report names its failing criteria and remains publishable
