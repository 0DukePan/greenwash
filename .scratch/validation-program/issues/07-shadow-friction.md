# 07: Shadow replay and the friction report

**What to build:** an offline harness that replays the checker over merged pull requests from consented repositories and produces the friction numbers: interruption rate over PRs that touched tests, unnecessary interruptions from a human judgment file, time to resolve where timestamps exist, override rate, and removal or opt-out where recorded. It never comments anywhere, never touches the network beyond the recorded inputs, and states each denominator explicitly.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A fixture PR log produces the five friction measures with explicit denominators
- [ ] An alert a human marked legitimate counts as unnecessary; an unreviewed alert does not
- [ ] A repository without recorded consent is refused
- [ ] The report states that it is offline and posts nothing
