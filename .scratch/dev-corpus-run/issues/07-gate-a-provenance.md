# 07: Gate A over pipeline artifacts only

**What to build:** the final dev-run stage hands the Gate A report its inputs: the pipeline's evaluation table, labelled cases, baselines and register. Gate A refuses a table or label file that did not come from this pipeline, verified by provenance hashes, and names the mismatch. The pipeline writes a report beside Gate A's decision that states the stage sequence, the counts per route and class, the measured labeling time, and the one-line statement that development results license no public claim.

**Blocked by:** 06 (evaluate).

**Status:** ready-for-agent

- [ ] Gate A runs on pipeline artifacts and returns go, pivot or stop
- [ ] A table from outside the pipeline is refused with the provenance mismatch named
- [ ] The pipeline report states the stage sequence, counts and measured labeling time
- [ ] The report says development results are not evidence of generalization
