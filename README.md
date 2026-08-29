# CKK Live Fan

Private, live visualization + autonomous research loop for the CKK/Fan grammar.

## Architecture

`CKK grammar snapshot -> blind expansion -> quotient/graph export -> Neon Postgres -> ranked research queue -> OpenAI web-research worker -> evidence/proposals -> Netlify live dashboard`

The research worker may change verdicts and create **proposals**, but it does **not** rewrite grammar code automatically. This preserves the distinction between generation, admission, evidence, and grammar changes.

## Sovereign architecture: Agency = Fan + Sleep

The minimal L4 architecture lives in
`ckk_snapshot/ckk/sovereign/architecture.py`. It separates provenance-free
`structural_sig()` morphology from append-only `lineage_id` identity, then
enforces the cycle:

`isolate -> blind generate -> NREM exact-replay prune -> REM verify/write-lock -> explicit lineage commit -> wake`

Equal structural snapshots may form one morphological confluence class, but
histories reached through different operator events are never fused at L4.
Pending proposals remain RAM-only until verified and explicitly admitted. See
`docs/SOVEREIGN_ARCHITECTURE.md` and `test/test_sovereign_architecture.py`.

The first contained sensory/runtime slice is implemented in
`ckk_snapshot/ckk/sovereign/runtime.py`. Sensors produce immutable observations;
an LLM or deterministic planner may only propose an intent; a sealed capability
gate, intent-bound approval and a simulation-only actuator stand between intent
and effect. NREM flushes the wake cache and REM validates the audit hash chain
before an append-only memory commit. See `docs/SOVEREIGN_RUNTIME.md` and
`experiments/sovereign_runtime_demo.py`.

WhatsApp is defined as the first real bidirectional interface in
`ckk_snapshot/ckk/sovereign/whatsapp.py`. The agent may answer or deliberately
remain silent. Signed text/document webhooks become observations; free-form
outbound text is restricted to WhatsApp's service window, while admitted
templates provide budgeted proactive contact outside it. The shipped actuator
is simulation-only until the dedicated number and Meta credentials are bound.
See `docs/SOVEREIGN_WHATSAPP.md`.

`ckk_snapshot/ckk/sovereign/organism.py` now composes the complete bootstrap:
WhatsApp/media senses, internal time, provider-neutral cognition, optional
action, hysteretic learning, sleep and an irreversible organism identity. It
contains no prescribed language, name or persona. See
`docs/SOVEREIGN_BOOTSTRAP.md`.

The first real brain and host live in `brain.py`, `state.py`, and `host.py`.
The brain uses the OpenAI Responses API with a strict decision schema; the host
provides a durable SQLite queue/checkpoint, an internal thought clock, signed
WhatsApp webhooks and the real WhatsApp Cloud API actuator. It ships as a
single-worker Docker service. See `docs/SOVEREIGN_DEPLOYMENT.md`.

`ckk_snapshot/ckk/agency_lab/` is the sealed parallel fork for causal agency
testing. It compares ordered history, shuffled history, stateless cognition and
no-sleep wake cache inside a closed simulated world. The model is blind to fork
labels and scoring; a source manifest freezes the protocol before results.
It has a separate one-shot container and receives no WhatsApp credentials. See
`docs/AGENCY_LAB.md`.

The production target is DigitalOcean: one Frankfurt Droplet, Caddy-managed
HTTPS, a private Docker network, six-hour verified SQLite recovery points and
DigitalOcean daily backups. Only the signed webhook and health endpoint are
public. See `docker-compose.digitalocean.yml` and
`docs/DIGITALOCEAN_META_SETUP.md`.

## Required secrets

### Netlify
- `DATABASE_URL` — Neon pooled connection string
- `CKK_USER` — dashboard username, default `ckk`
- `CKK_PASSWORD` — dashboard password

### GitHub Actions
- `DATABASE_URL`
- `OPENAI_API_KEY`
- optional repository variable `OPENAI_MODEL` (default in code: `gpt-5.6`)

## Neon
Run `schema/001_init.sql` once. It enables `pgvector` and creates structures, edges, evidence, discoveries, proposals, queue and vector memory tables.

## Netlify
Import the GitHub repository. `netlify.toml` publishes `site/`, deploys functions, and places an Edge Function Basic-Auth gate over `/*`.

The browser polls `/.netlify/functions/state` every 4 seconds, so new graph/evidence events appear live after a worker cycle.

## Autonomous cycle
GitHub Actions runs every 15 minutes (and manually):
1. `export_graph.py` executes the frozen grammar and writes graph state.
2. `build_queue.py` ranks unmatched structures mechanically.
3. `research_agent.py` takes the top queue item and researches it with OpenAI web search.
4. Evidence is stored with verdict/caveat/confidence; missing primitives become `PENDING` proposals.

## Safety against self-confirmation
- Generator never sees evidence or physics matches.
- Research worker cannot edit grammar.
- `UNMATCHED` is not a discovery.
- New primitives are proposals until separately admitted.
- All state transitions are persisted.

## Local
`npm install && npx netlify dev`
