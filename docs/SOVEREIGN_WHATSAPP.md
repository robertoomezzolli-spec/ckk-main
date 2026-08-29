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
- Roberto's exact WhatsApp ID/number as sole admitted owner,
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
