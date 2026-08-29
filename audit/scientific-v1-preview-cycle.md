# CKK Scientific v1 · Preview-cycle status

## Deterministic generation preflight

`sci-v1-preflight-clean-b5c48f1603ad8b25`

- scope: `CONTROL_PLANE_PREFLIGHT_NO_INTERPRETATION`
- level: 1
- structures: 15
- admitted: 10
- generable: 5
- derivation events: 5
- true derivational confluences: 0
- integrity violations: 0
- status: `SEALED`
- public eligible: `false`

`sci-v1-preflight-rejected-5edce29dd6267467`

- level: 2
- structures: 52
- derivation events: 60
- true derivational confluences: 9
- idempotent self transitions: 1
- cross-order fiber violations: 12
- status: `REJECTED`
- seal attempt: `BLOCKED`

This is deliberate evidence that Scientific v1 does not hide the current deeper-core defects.

## Agent pipeline

The complete Discover → Source → Critique → GPT Normalize → Claude Normalize → Judge → Freeze → Generate → Match → Validate → Seal implementation exists and its contract-replay integration test reaches a private seal in exactly five isolated agent calls.

The real externally backed GPT/Claude cycle is currently:

`BLOCKED_EXTERNAL_APPROVAL`

No candidate, evidence, normalization or agent trace was written by the rejected external attempts, and no payload reached OpenAI or Anthropic. Runtime approval requires explicit authorization to transmit public source URLs/facts and neutral structural proposals to `gpt-5.6-luna` and `claude-sonnet-5`. DB credentials, repository data, internal IDs/hashes, generations and hidden targets are excluded by an outbound DLP guard.

Because the real cycle has not run, the Scientific v1 acceptance gate is not yet complete and the current recommendation remains `NO-GO`.

## Draft deployment

- Netlify preview site: `ckk-scientific-v1-preview`
- Netlify deploy ID: `6a9076eff97d07cc8da373ea`
- Preview URL: `https://6a9076eff97d07cc8da373ea--ckk-scientific-v1-preview.netlify.app/science/`
- Deploy context: `deploy-preview`
- Neon preview branch: `br-weathered-smoke-awvboh0k`
- Public Scientific generation: `null`
- Production deploy after preview: `6a9064ce12674a0008bb019d` (unchanged)
- Production commit after preview: `c1a8be5a454bf4b4532217616a5daba04cd6b225` (unchanged)

The draft lives on a separate preview-only Netlify site and is protected by preview-scoped CKK Edge Basic Auth. An unauthenticated request returns `401`; authenticated UI and Scientific API requests return `200`. The Scientific API is connected only to the isolated Neon preview branch through the `deploy-preview` environment context.
