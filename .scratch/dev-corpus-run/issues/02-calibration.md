# 02: Calibration closes the labeling-time assumption

**What to build:** the calibrate stage measures time per case on a supplied calibration file, writes its measurement artifact with input hashes, and closes the labeling-time assumption in the register with status verified, the measured value and the artifact path. The register loader gains an evidence field, and an assumption marked verified without an artifact path is refused. The stage refuses to run unless assembly has produced its manifest.

**Blocked by:** 01 (assemble).

**Status:** ready-for-agent

- [ ] Calibration writes the measured time per case and closes the labeling-time assumption with evidence
- [ ] A register entry marked verified without an evidence path is refused by name
- [ ] Calibration before assembly is an out-of-order refusal
- [ ] Gate A consumes the closed register without a hand edit
