# Structural core fix plan

Safety branch only: `fix/derivation-events-crossdomain-safety-20260827`.

Wayback branch: `backup/pre-structural-core-fix-20260827-1547`.

Goals:
- preserve every derivation event, even when the target structure already exists;
- distinguish binary composition from derivational confluence;
- keep Run 34, main, production, and current generation untouched;
- add regression tests before any merge;
- do not reintroduce self-duality claims;
- do not reinterpret `dim=4` as spacetime.

No production mutation is part of this branch.
