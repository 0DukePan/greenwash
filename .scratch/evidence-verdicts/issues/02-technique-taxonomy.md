# 02: Versioned technique taxonomy and coverage matrix

**What to build:** one versioned table names every tampering technique the tool knows, with the mechanism that catches it, whether replay is needed, and its current status. The rules listing command renders the coverage matrix from that table instead of prose. The table gains the techniques this project has not covered yet: spec, docstring or fixture rewrites, runner and plugin configuration tampering, report tampering, and gate or hook tampering.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The coverage matrix is generated from the table, not maintained by hand
- [ ] Adding a technique is a single data edit plus its detection or an honest not-covered status
- [ ] The taxonomy carries a version that the docs pin
- [ ] A corpus record naming an unknown technique is rejected with the offending field named
