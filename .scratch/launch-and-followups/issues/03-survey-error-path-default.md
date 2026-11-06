# 03: Put error-path-default through the survey, and guard the survey's numbers

**What to build:** The one rule that has never been through the real-history survey gets measured. Run the survey over the same repositories, classify every `error-path-default` flag by hand, and publish what it finds: which fired, which were genuine, which were the rules asking rather than accusing. In the same pass, make the survey page's numbers mechanically checked against the artifact, the way the README and the claim ledger already are, so the page cannot drift from the data it quotes.

**Blocked by:** None (can start immediately).

**Status:** done — merged `cd7ea0d`, review fixes `9579da2` on `integration/launch-followups`. Measured 2 flags, both one pytest change; found and fixed a blind-rule bug in the survey harness; the page is now guarded against drift.

- [ ] The survey artifact contains the `error-path-default` flags and the survey page names what fired and on what
- [ ] Every flag from that rule is classified, with genuine positives separated from asks
- [ ] The published counts are generated from or checked against the artifact by a test
- [ ] The "never been surveyed" limitation in the limits page is closed or restated with the measurement
- [ ] The claim ledger's survey row still answers from the artifact after the change
