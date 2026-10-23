# 03: Cluster-aware intervals and conservative rounding

**What to build:** every headline rate carries an interval that accounts for cases clustering inside repositories. The evaluation output gains repository identity aggregation: cluster sizes, the intraclass-correlation estimate, the floor-adjusted rho, the design effect, effective counts, and the exact interval computed at those effective counts, printed beside the case-level exact interval and the Wilson sensitivity. Rounding is conservative: one decimal place, lower bounds down, upper bounds up. The designed-for table prints from the same arithmetic so a reader sees the launch odds a sample implies. The published boundary values are pinned: 11 of 11 prints a lower bound of 71.5, 0 of 11 an upper bound of 28.5, 100 cases with 4 misses passes and 5 fails, 36 with zero errors passes and 35 falls short.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Rates print n, repository count, rho estimate, rho used, design effect, effective n, and both intervals
- [ ] The effective-n interval is never tighter than the case-level interval
- [ ] The pinned boundary values print exactly, and lower bounds never round up
- [ ] The designed-for table is generated from the same arithmetic, not typed
- [ ] A fixture where the case-level interval passes and the effective-n interval fails reports the effective-n failure
