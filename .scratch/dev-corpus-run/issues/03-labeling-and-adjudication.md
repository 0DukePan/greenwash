# 03: Labeling and adjudication checkpoints

**What to build:** the label stage generates blind packets from the assembled split only after calibration has closed, then waits for two label files. The adjudicate stage validates supplied files against the split, refuses case ids outside it, refuses a second adjudication for the same case, and refuses the evaluate stage while any case lacks an adjudicated label, naming the cases. The L9 result is written as an artifact with input hashes.

**Blocked by:** 02 (calibration).

**Status:** ready-for-agent

- [ ] Packets are generated only after the calibration artifact exists, and contain no detector output or other labeler's answer
- [ ] A label file naming a case outside the split is refused by name
- [ ] Adjudication is recorded once; a second record for a case is refused
- [ ] The L9 output is refused while unadjudicated cases remain, and names them
