# CKK Scientific v1 · Wayback

- Starting main SHA: `c1a8be5a454bf4b4532217616a5daba04cd6b225`
- Production deploy: `6a9064ce12674a0008bb019d`
- Production commit: `c1a8be5a454bf4b4532217616a5daba04cd6b225`
- Git backup branch: `backup/pre-scientific-v1-20260827-184521`
- Git tag: `pre-scientific-v1-20260827-184521`
- Neon project: `autumn-bonus-53940783`
- Production branch: `br-wild-hill-awswgush`
- Read-only backup branch: `br-little-feather-aw31y5fw`
- Backup branch name: `snapshot-pre-scientific-v1-20260827-184057`
- Parent LSN: `0/3861078`

## Golden snapshot verification

Both production and the read-only backup returned:

- generation: `v6-noselfdual-563f50e328c5`
- grammar: `v6-html-no-asserted-selfdual`
- run: `34`
- nodes: `276`
- edges: `945`
- historical graph confluences: `196`
- dangling edges: `0`
- self loops: `0`
- unverified self-duality claims: `0`
- self-duality: `NOT_EVALUATED`

The untracked user artifact `agent/graph_export.json` had SHA-256 `5d3605ff257562fba97c8a697c0784d84b46584fcd9f474e20eabe066bff1106` and is outside this implementation.

## Restore

Git inspection without changing the current branch:

```sh
git show backup/pre-scientific-v1-20260827-184521
git show pre-scientific-v1-20260827-184521
```

Create a recovery branch from the exact code waypoint:

```sh
git switch -c restore/scientific-v1-wayback pre-scientific-v1-20260827-184521
```

Neon production restore is intentionally not executed automatically. The reviewed restore command is:

```sh
npx neonctl branches restore br-wild-hill-awswgush br-little-feather-aw31y5fw --project-id autumn-bonus-53940783 --preserve-under-name pre-scientific-v1-restore-source
```

