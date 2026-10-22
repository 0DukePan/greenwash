# 10: Reproduction command for the headline table

**What to build:** a single command rebuilds the published headline table from pinned artifacts: corpus manifest, frozen annotations, detector configurations and seeds. A reader with the repository can verify a release's numbers without rerunning any model.

**Blocked by:** 09 (evaluation runner).

**Status:** ready-for-agent

- [ ] The command rebuilds the table byte-identically on a second run, timestamps excluded
- [ ] Any pinned-artifact hash mismatch aborts with the artifact named
- [ ] The README's methods section links the command and its expected output
