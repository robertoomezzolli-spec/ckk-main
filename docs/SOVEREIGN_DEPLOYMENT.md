# Brain and hosting

This deployment turns the contained architecture into one running process:

`signed WhatsApp webhook -> durable queue -> OpenAI cognition -> capability gate -> WhatsApp Cloud API -> sleep commit -> SQLite checkpoint`

## What the brain receives

- the immutable viability laws,
- current admitted observations,
- committed learned beliefs,
- recent episodic history,
- the last memory head,
- only the currently available output modes.

It receives no name, persona, preferred language, ideology or mandatory reply
rule. The OpenAI Responses API returns a strict JSON-schema decision. Trusted
code converts only three possible outcomes: silence, a service-window message,
or an allowlisted WhatsApp template. The model never receives network or
actuator access.

## Start

Create the dead-man signing key on an offline owner device. Never copy the
private key to the server:

```bash
PYTHONPATH=ckk_snapshot python scripts/deadman-control.py keygen \
  --private roberto.deadman-private.pem --public control/deadman-public.pem
PYTHONPATH=ckk_snapshot python scripts/deadman-control.py renew \
  --private roberto.deadman-private.pem --output control/deadman-lease.json
```

The signed lease permits processing for 24 hours. After that, the queue and all
outputs/learning freeze. After 72 hours, ingress is rejected. An operator can
force immediate quarantine with `touch control/KILL`. The control directory is
mounted read-only into the organism; only the public key and signed lease reach
the host.

```bash
cp .env.sovereign.example .env.sovereign
# Fill the six required secrets/IDs.
docker compose -f docker-compose.sovereign.yml up -d --build
```

Expose `https://YOUR_HOST/webhook` to Meta and use the same verify token as in
`.env.sovereign`. `GET /healthz` returns the current identity head and number of
memory commits.

Run exactly one application worker. SQLite is mounted on the `sovereign-state`
volume; inbound event IDs are deduplicated and failed cognition calls are
retried up to five times. For multi-instance deployment, replace the queue and
checkpoint store with Postgres while preserving the same interfaces.

## Operational boundary

Text conversations are live. Documents, images and voice notes currently enter
as authenticated, quarantined metadata; byte download, malware scanning,
transcription and extraction remain separate sensory organs and are not enabled
by this deployment.

External delivery and the local sleep commit cannot form one atomic transaction.
A process death in the narrow interval after Meta accepts a message but before
the checkpoint is written can duplicate that outbound message on retry. Keep a
single worker and monitor retries until a provider-level idempotency key is
available.
