# 04: Launch criteria engine

**What to build:** the nine launch criteria become one evaluable engine that reads only the computed evaluation table, the pre-registration record and the claim ledger, plus two injected results for the criteria whose inputs live elsewhere: a rebuild-equality flag for L6 and the announcement-draft check result for L7. It evaluates L1 and L2 on the pre-registered launch configuration using the effective-n intervals, separates abstention ceilings for twins and natural clean, applies the determinism rule, requires the integrity suite to have run with zero successes, checks the sample floor and distinct-repository count as a criterion, and evaluates label quality from the double-labeled sample. It fails closed: a missing cell, empty class or unevaluable check is a failure with reason `not evaluated`, never a skip. It returns the decision, the first failing criterion in fixed order, and all failing criteria.

**Blocked by:** 01 (pre-registration and thresholds), 03 (cluster-aware intervals).

**Status:** ready-for-agent

- [ ] All criteria passing yields LAUNCH; each criterion failing alone yields NARROW naming only it
- [ ] Several criteria failing lists all of them and picks the first in fixed order as the decider
- [ ] A missing or unevaluable input yields NARROW with reason `not evaluated`, never LAUNCH
- [ ] A non-launch detector cell passing does not rescue the launch cell
- [ ] Abstention above the ceiling on twins and on natural clean each fail L3 by name
- [ ] A double-labeled sample below the floor, or PABAK below its floor, fails L9
- [ ] A false rebuild-equality flag fails L6 and a failing announcement check fails L7, both inside the same decision
- [ ] The engine reads no prose and no file outside the three named inputs
