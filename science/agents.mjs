import { deterministicId, sha256 } from './core.mjs';
import { PROMPT_VERSION } from './prompts.mjs';

function outputText(response) {
  if (typeof response.output_text === 'string') return response.output_text;
  return (response.output ?? []).flatMap((item) => item.content ?? [])
    .filter((item) => item.type === 'output_text').map((item) => item.text).join('\n');
}

function parseJson(text) {
  const cleaned = String(text ?? '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  return JSON.parse(cleaned);
}

export class OpenAIAdapter {
  constructor({ apiKey = process.env.OPENAI_API_KEY, model = process.env.OPENAI_SCIENCE_MODEL ?? 'gpt-5.6-luna', fetchImpl = fetch } = {}) {
    if (!apiKey) throw new Error('OPENAI_API_KEY missing');
    this.apiKey = apiKey;
    this.model = model;
    this.fetchImpl = fetchImpl;
    this.provider = 'OPENAI';
  }

  async complete({ prompt, schema, schemaName, webSearch = false }) {
    const response = await this.fetchImpl('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: { authorization: `Bearer ${this.apiKey}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model: this.model,
        input: prompt,
        ...(webSearch ? { tools: [{ type: 'web_search' }] } : {}),
        text: { format: { type: 'json_schema', name: schemaName, strict: true, schema } },
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(`OpenAI ${response.status}: ${payload.error?.message ?? 'request failed'}`);
    return { output: parseJson(outputText(payload)), usage: payload.usage ?? {}, model: payload.model ?? this.model };
  }
}

export class AnthropicAdapter {
  constructor({ apiKey = process.env.ANTHROPIC_API_KEY, model = process.env.ANTHROPIC_SCIENCE_MODEL ?? 'claude-sonnet-5', fetchImpl = fetch } = {}) {
    if (!apiKey) throw new Error('ANTHROPIC_API_KEY missing');
    this.apiKey = apiKey;
    this.model = model;
    this.fetchImpl = fetchImpl;
    this.provider = 'ANTHROPIC';
  }

  async complete({ prompt, system }) {
    const response = await this.fetchImpl('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': this.apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({ model: this.model, max_tokens: 2400, temperature: 0, system, messages: [{ role: 'user', content: prompt }] }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(`Anthropic ${response.status}: ${payload.error?.message ?? 'request failed'}`);
    const text = (payload.content ?? []).filter((item) => item.type === 'text').map((item) => item.text).join('\n');
    return { output: parseJson(text), usage: payload.usage ?? {}, model: payload.model ?? this.model };
  }
}

export function agentRunIdentity(role, candidateId, input, runNonce = '') {
  const inputHash = sha256(input);
  return {
    id: deterministicId('agent', { role, candidateId, inputHash, prompt: PROMPT_VERSION, runNonce }),
    inputHash,
    isolationKey: sha256({ role, candidateId, inputHash }),
  };
}

export async function executeAgent({ store, role, candidateId, adapter, input, prompt, schema, schemaName, system, webSearch, evidenceIds = [], runNonce = '' }) {
  const identity = agentRunIdentity(role, candidateId, input, runNonce);
  await store.startAgentRun({
    id: identity.id,
    candidate_id: candidateId,
    role,
    provider: adapter.provider,
    model: adapter.model,
    prompt_version: PROMPT_VERSION,
    isolation_key: identity.isolationKey,
    input_hash: identity.inputHash,
    input_evidence_ids: evidenceIds,
  });
  try {
    const result = await adapter.complete({ prompt, schema, schemaName, system, webSearch });
    await store.finishAgentRun(identity.id, 'SUCCEEDED', result.output, result.usage);
    return { ...result, runId: identity.id, inputHash: identity.inputHash };
  } catch (error) {
    await store.finishAgentRun(identity.id, 'FAILED', null, {}, String(error.message ?? error));
    throw error;
  }
}

export const SCOUT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['candidate_name', 'domain', 'sources', 'formal_statement', 'observed_properties', 'uncertainties'],
  properties: {
    candidate_name: { type: 'string' }, domain: { type: 'string', enum: ['PHYSICS'] },
    sources: { type: 'array', minItems: 1, items: { type: 'object', additionalProperties: false, required: ['source_ref', 'source_type', 'fact', 'quality'], properties: {
      source_ref: { type: 'string' }, source_type: { type: 'string' }, fact: { type: 'string' }, quality: { type: 'string', enum: ['PRIMARY', 'STANDARD', 'SECONDARY'] },
    } } },
    formal_statement: { type: 'string' }, observed_properties: { type: 'array', items: { type: 'string' } }, uncertainties: { type: 'array', items: { type: 'string' } },
  },
};

export const NORMALIZATION_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['structural_claim', 'supported_by_evidence', 'unmapped_properties', 'required_missing_distinctions', 'confidence'],
  properties: {
    structural_claim: { type: 'object', additionalProperties: false,
      required: ['kind', 'dim', 'order', 'sym', 'sq', 'anti', 'mult', 'bc', 'dual', 'occ'],
      properties: {
        kind: { type: 'string' }, dim: { type: 'integer', minimum: 0 }, order: { type: 'integer', minimum: 0 },
        sym: { type: ['string', 'null'] }, sq: { type: ['integer', 'null'] }, anti: { type: ['boolean', 'null'] },
        mult: { type: 'integer', minimum: 1 }, bc: { type: ['string', 'null'] }, dual: { type: 'integer', enum: [0, 1] }, occ: { type: ['integer', 'null'] },
      } },
    supported_by_evidence: { type: 'array', items: { type: 'string' } }, unmapped_properties: { type: 'array', items: { type: 'string' } },
    required_missing_distinctions: { type: 'array', items: { type: 'string' } }, confidence: { type: 'number', minimum: 0, maximum: 1 },
  },
};

export const JUDGE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verdict', 'reason', 'blocking_items', 'selected_normalization_id'],
  properties: {
    verdict: { type: 'string', enum: ['ACCEPT_NORMALIZATION', 'REJECT', 'AMBIGUOUS', 'NEEDS_SOURCE', 'NEEDS_SCHEMA'] },
    reason: { type: 'string' }, blocking_items: { type: 'array', items: { type: 'string' } }, selected_normalization_id: { type: ['string', 'null'] },
  },
};
