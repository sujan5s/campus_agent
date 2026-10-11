**Infeasibility diagnosis: 10/10 detected, 7/10 with a specific cause**

| Broken instance | Status | Diagnosed by | Groups blamed | Time | Explanation (truncated) |
| --- | --- | --- | --- | --- | --- |
| every teacher capped at 1 period/day | infeasible | precheck | 1 (exact cause) | 0 ms | Total demand is 101 periods/week but teachers can cover at most 60 (max_hours_per_day × da |
| no teacher qualified for a subject | infeasible | precheck | 1 (exact cause) | 0 ms | No teacher can teach CS701 — map at least one teacher to it in Data Setup. |
| class reduced to 2 periods/day | infeasible | precheck | 1 (exact cause) | 0 ms | Section CSE-7A needs 28 periods/week plus 3 open-elective period(s) but its rules leave on |
| all lab rooms removed | infeasible | precheck | 1 (exact cause) | 0 ms | Subjects ['CS703', 'CS707', 'CS505'] need a lab but no room of type 'lab' exists. |
| class strength 500 (no room fits) | infeasible | precheck | 1 (exact cause) | 68 ms | No classroom has capacity >= 500 for section CSE-7A (rooms reserved for elective baskets a |
| pinned teacher banned all week | infeasible | assumption core | 11 | 112 ms | Conflicting constraint groups: teacher availability (clash-free teaching), teacher daily h |
| class capped at 3 periods/day | infeasible | precheck | 1 (exact cause) | 0 ms | Section CSE-7A needs 31 periods/week but its 'at most 3 periods per day' rule allows at mo |
| 6 periods/week with max 1/day | infeasible | assumption core | 11 | 184 ms | Conflicting constraint groups: teacher availability (clash-free teaching), teacher daily h |
| every teacher capped at 4 periods/week | infeasible | precheck | 1 (exact cause) | 0 ms | Total demand is 101 periods/week but teachers can cover at most 48 (max_hours_per_day × da |
| max 1 in a row + 2 periods/day | infeasible | assumption core | 11 | 154 ms | Conflicting constraint groups: teacher availability (clash-free teaching), teacher daily h |
