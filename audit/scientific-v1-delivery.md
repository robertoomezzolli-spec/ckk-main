# CKK Scientific v1 · Delivery state

## Preview

- Feature branch: `feature/scientific-v1-20260827`
- Netlify preview site: `ckk-scientific-v1-preview`
- Draft deploy: `6a9076eff97d07cc8da373ea`
- URL: `https://6a9076eff97d07cc8da373ea--ckk-scientific-v1-preview.netlify.app/science/`
- Context: `deploy-preview`
- Neon branch: `br-weathered-smoke-awvboh0k`
- Database migration: applied and immutable-trigger smoke test passed
- Scientific generations: 1 `SEALED` private preflight, 1 `REJECTED` integrity candidate
- Public Scientific generation: none
- HTTPS verification: unauthenticated `401`, authenticated UI `200`, authenticated Scientific API `200`

## Production safety verification

- GitHub `main`: `c1a8be5a454bf4b4532217616a5daba04cd6b225`
- Netlify published deploy: `6a9064ce12674a0008bb019d`
- Netlify published commit: `c1a8be5a454bf4b4532217616a5daba04cd6b225`
- Run: `34`
- Grammar: `v6-html-no-asserted-selfdual`
- Structures: `276`
- Edges: `945`
- Historical graph confluences: `196`
- Scientific production migration: not applied
- Production alias changed: no
- Run 34 changed: no

## Preview database state

- Inherited historical run: `34`, `276` structures, `945` edges
- Scientific structures: `67`
- Scientific generation status: `SEALED=1`, `REJECTED=1`
- Unresolved findings: `SIGNATURE_COLLISION=2`, `INSUFFICIENT_EVIDENCE=3`, `VALIDATION_FAILED=1`
- Active public generation: `null`

## Acceptance status

`NO-GO`

The control plane, schema, deterministic preflight, UI, API, validation and preview deployment are complete. The required real GPT/Claude cycle is not complete because the outbound transfer of public source facts to OpenAI and Anthropic still awaits explicit approval. The successful contract-replay test is deliberately not counted as scientific evidence.

## Restore

Git recovery branch:

```sh
git switch -c restore/scientific-v1-wayback pre-scientific-v1-20260827-184521
```

Reviewed Neon production restore command (not executed):

```sh
npx neonctl branches restore br-wild-hill-awswgush br-little-feather-aw31y5fw --project-id autumn-bonus-53940783 --preserve-under-name pre-scientific-v1-restore-source
```

The isolated Scientific preview branch can be discarded independently; production does not depend on it.
