# Cross-Domain Universe Wayback

- Starting SHA: `5128409001c77306a8b1cb04583cbc79203e5978`
- Git branch: `backup/pre-crossdomain-universe-20260827-172219`
- Git tag: `pre-crossdomain-universe-20260827-172219`
- Neon backup: `br-mute-smoke-aw43dft1` (`snapshot-pre-crossdomain-universe-20260827-172219`, read-only, parent LSN `0/37E3D90`)
- Production deployment: `6a905439bb00070008bc7a9d`
- Golden snapshot: generation `v6-noselfdual-563f50e328c5`, Run 34, 276 nodes, 945 edges, 196 historical graph confluences
- Self-duality: `NOT_EVALUATED`

Both the production and backup Neon branches were read independently and returned the same clean Run 34 counts before implementation started.

## Restore

Safe Git inspection branch:

```bash
git switch -c restore/pre-crossdomain-universe pre-crossdomain-universe-20260827-172219
```

Only if the preserved pre-task working tree is needed:

```bash
git stash apply 96b11c3fcb69657c4b6b514e94155eb0baff93fe
```

Neon restore command (this mutates the production branch and therefore requires explicit operational approval):

```bash
npx neonctl branches restore br-wild-hill-awswgush br-mute-smoke-aw43dft1 --project-id autumn-bonus-53940783 --preserve-under-name pre-crossdomain-universe-restore-source
```
