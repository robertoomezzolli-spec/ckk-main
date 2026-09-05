# WhatsApp as the sovereign agent's primary interface

## Intended behavior

- Roberto can send text and documents to one dedicated WhatsApp Business number.
- The agent answers each admitted direct owner message while the customer-service
  window is open. Silence remains available for clock ticks and other events
  that do not require a conversational reply.
- The agent may initiate contact when its wake/sleep process produces a salient
  reason.
- Conversation and document observations enter the same NREM/REM memory path as
  every other sense.
- Learning changes committed memory and hysteretic preferences, not executable
  capabilities or grammar.
- Roberto and Amelie may explicitly ask KAIROS to relay a message to the other
  participant through the sealed `whatsapp.send_to_allowed_person` capability.

## Platform boundary

WhatsApp Cloud API opens a customer-service window after the user messages the
business. Free-form service messages are allowed within that window. Outside
it, business-initiated contact must use an approved template. Therefore truly
free-form proactive thought is possible only while the window is open. Outside
it the runtime must either stay silent or send an admitted template inviting
Roberto to reopen the conversation.

## Implemented boundary

`ckk_snapshot/ckk/sovereign/whatsapp.py` provides:

- webhook challenge verification,
- `X-Hub-Signature-256` HMAC verification over raw request bytes,
- pinning to one business phone-number ID and one owner WhatsApp ID,
- text and document-metadata observations,
- mandatory service replies for admitted direct owner messages,
- free-form service-window enforcement,
- an allowlist for approved templates,
- a proactive daily budget,
- a policy-complete simulation actuator and a live Cloud API actuator that
  records Meta's HTTP status and response body in the durable episode.

The relay contact book is fixed trusted configuration: `Roberto` resolves to
the owner ID and `Amelie` resolves to the sole additional admitted ID. The
model receives only those two names, never the underlying WhatsApp IDs. A
conservative non-model gate requires a direct inbound text containing a relay
verb and the other participant's name. Raw-number and third-party targets,
self-relays, clock/status-triggered outreach, and chat-based allowlist changes
are rejected. The target must also have an open Meta service window.

Passing that gate grants an option, not an obligation. KAIROS may relay the
substance, phrase it in its own words, or decline to carry the message. The
runtime does not force a tool call or replace KAIROS' reply with a canned
confirmation. If KAIROS does invoke the tool, trusted code still attributes
the real requester and an actual provider failure overrides any success claim.

Every inbound event can produce at most one relay. A durable reservation is
written before the Graph API call, so a cognition retry cannot duplicate an
accepted or uncertain send. The relay audit stores participant labels,
timestamps, provider status, Meta message ID, and later delivery state, but no
message content or phone identifier. The sender receives a separate direct
confirmation only after Meta accepts the relay.

Document bytes are not trusted merely because their metadata arrived in a
signed webhook. The media ID is admitted first; a later fetcher must download,
size-limit, hash-check, malware-scan and parse the file before its contents enter
memory.

## Activation requirements

Real activation needs user-controlled infrastructure and credentials:

- Meta Business Portfolio and WhatsApp Business Account,
- a dedicated phone number registered for Cloud API,
- permanent access token or system-user token,
- WhatsApp phone-number ID,
- Meta app secret and webhook verify token,
- Roberto's exact WhatsApp ID/number as primary owner and any deliberately
  admitted additional IDs in `WHATSAPP_ALLOWED_WA_IDS`,
- one approved proactive template,
- public HTTPS webhook deployment.

The repository intentionally contains no credential values. Production loads
them from its non-versioned environment file and uses the live Cloud API
transport only after the same recipient and service-window checks as the
simulation boundary.

## Self-learning

`ckk_snapshot/ckk/sovereign/learning.py` implements evidence-bearing,
hysteretic learning. Repeated conversation can commit beliefs and preferences;
weak one-off impressions remain cache, and contradictory replacements must
cross a higher threshold. The learned context can influence future silence,
reply and proactive-message decisions. Protected prefixes prevent the learner
from changing capabilities, grammar, recipients, actuators or safety policy.
