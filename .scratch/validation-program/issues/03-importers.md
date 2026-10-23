# 03: Importers for R3, R4 and R5

**What to build:** import paths that turn outside sources into case records. R3 imports local agent runs on impossible tasks, where any pass is an exploit by construction. R4 imports public dataset entries only when the task has an executable test suite and its license permits the use. R5 imports public agent pull request metadata and diffs only where the license permits. Every import records the route, source, license and technique, and refuses when a license check cannot be recorded.

**Blocked by:** 01 (case record shape).

**Status:** ready-for-agent

- [ ] Each route imports a fixture source into unadjudicated records with route and license recorded
- [ ] An R4 entry without an executable suite is refused by name
- [ ] A source without a recorded license decision is refused, never defaulted
- [ ] Imported records carry the technique from the versioned taxonomy or are refused
