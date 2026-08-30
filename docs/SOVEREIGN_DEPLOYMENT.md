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

It receives no name, persona, preferred language or ideology. The OpenAI
Responses API returns a strict JSON-schema decision. For a direct admitted
owner message inside the service window, trusted code restricts that decision
to a service reply; silence remains available for clock-only wakes. Trusted
code converts only three possible outcomes: silence, a service-window message,
or an allowlisted WhatsApp template. The model never receives network or
actuator access.

## Start

```bash
cp .env.sovereign.example .env.sovereign
# Fill the six required secrets/IDs.
docker compose -f docker-compose.sovereign.yml up -d --build
```

Expose `https://YOUR_HOST/webhook` to Meta and use the same verify token as in
`.env.sovereign`. `GET /healthz` returns the current identity head, number of
memory commits, durable queue state and worker/clock task state.

Run exactly one application worker. SQLite is mounted on the `sovereign-state`
volume; inbound event IDs are deduplicated and failed cognition calls are
retried up to five times. Worker completion logs and durable episodes record
whether an effect occurred and Meta's outbound HTTP status without logging
message contents or access tokens. For multi-instance deployment, replace the queue and
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
