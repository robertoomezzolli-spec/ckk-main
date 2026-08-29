BEGIN;

CREATE TABLE IF NOT EXISTS science_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now(),
  checksum text NOT NULL
);

CREATE TABLE IF NOT EXISTS science_canons (
  id text PRIMARY KEY,
  domain text NOT NULL CHECK (domain IN ('PHYSICS','CHEMISTRY','BIOLOGY','COMPUTATION','MATHEMATICS')),
  version integer NOT NULL CHECK (version > 0),
  status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','FROZEN','SUPERSEDED')),
  coverage_denominator integer CHECK (coverage_denominator >= 0),
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  payload_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  frozen_at timestamptz,
  UNIQUE(domain, version)
);

CREATE TABLE IF NOT EXISTS science_candidates (
  id text PRIMARY KEY,
  domain text NOT NULL CHECK (domain IN ('PHYSICS','CHEMISTRY','BIOLOGY','COMPUTATION','MATHEMATICS')),
  name text NOT NULL,
  status text NOT NULL DEFAULT 'DISCOVERED' CHECK (status IN (
    'DISCOVERED','SOURCED','CRITIQUED','NORMALIZING','DISPUTED','ADJUDICATED',
    'FROZEN','GENERATED','MATCHED','VALIDATED','SEALED','REJECTED','FAILED'
  )),
  created_by_agent text NOT NULL,
  dedupe_key text NOT NULL UNIQUE,
  uncertainties jsonb NOT NULL DEFAULT '[]'::jsonb,
  formal_statement text,
  budget jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS science_evidence (
  id text PRIMARY KEY,
  candidate_id text NOT NULL REFERENCES science_candidates(id) ON DELETE RESTRICT,
  source_type text NOT NULL,
  source_ref text NOT NULL,
  fact text NOT NULL,
  retrieved_at timestamptz NOT NULL,
  quality text NOT NULL CHECK (quality IN ('PRIMARY','STANDARD','SECONDARY','INSUFFICIENT')),
  content_hash text NOT NULL,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(candidate_id, content_hash)
);

CREATE TABLE IF NOT EXISTS science_agent_runs (
  id text PRIMARY KEY,
  candidate_id text REFERENCES science_candidates(id) ON DELETE RESTRICT,
  role text NOT NULL CHECK (role IN ('GPT_SCOUT','CLAUDE_RED_TEAM','GPT_NORMALIZER','CLAUDE_NORMALIZER','JUDGE')),
  provider text NOT NULL,
  model text NOT NULL,
  prompt_version text NOT NULL,
  isolation_key text NOT NULL,
  input_hash text NOT NULL,
  output_hash text,
  status text NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','BLOCKED')),
  input_evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  output jsonb,
  usage jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  error text
);

CREATE TABLE IF NOT EXISTS science_normalizations (
  id text PRIMARY KEY,
  candidate_id text NOT NULL REFERENCES science_candidates(id) ON DELETE RESTRICT,
  agent_role text NOT NULL CHECK (agent_role IN ('GPT_NORMALIZER','CLAUDE_NORMALIZER')),
  structural_claim jsonb NOT NULL,
  supported_by_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  input_evidence_ids jsonb NOT NULL,
  unmapped_properties jsonb NOT NULL DEFAULT '[]'::jsonb,
  required_missing_distinctions jsonb NOT NULL DEFAULT '[]'::jsonb,
  confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  input_hash text NOT NULL,
  output_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(candidate_id, agent_role)
);

CREATE TABLE IF NOT EXISTS science_adjudications (
  id text PRIMARY KEY,
  candidate_id text NOT NULL UNIQUE REFERENCES science_candidates(id) ON DELETE RESTRICT,
  verdict text NOT NULL CHECK (verdict IN ('ACCEPT_NORMALIZATION','REJECT','AMBIGUOUS','NEEDS_SOURCE','NEEDS_SCHEMA')),
  normalization_ids jsonb NOT NULL,
  selected_normalization_id text REFERENCES science_normalizations(id) ON DELETE RESTRICT,
  reason text NOT NULL,
  blocking_items jsonb NOT NULL DEFAULT '[]'::jsonb,
  judge_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((verdict = 'ACCEPT_NORMALIZATION' AND selected_normalization_id IS NOT NULL)
    OR (verdict <> 'ACCEPT_NORMALIZATION' AND selected_normalization_id IS NULL))
);

CREATE TABLE IF NOT EXISTS science_canon_targets (
  id text PRIMARY KEY,
  canon_id text NOT NULL REFERENCES science_canons(id) ON DELETE RESTRICT,
  candidate_id text UNIQUE REFERENCES science_candidates(id) ON DELETE RESTRICT,
  domain text NOT NULL CHECK (domain IN ('PHYSICS','CHEMISTRY','BIOLOGY','COMPUTATION','MATHEMATICS')),
  name text NOT NULL,
  hidden boolean NOT NULL DEFAULT true,
  frozen_payload jsonb NOT NULL,
  payload_hash text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS science_generations (
  id text PRIMARY KEY,
  grammar_version text NOT NULL,
  grammar_hash text NOT NULL,
  seed_set_hash text NOT NULL,
  maxdim integer NOT NULL CHECK (maxdim >= 0),
  expansion_levels integer NOT NULL CHECK (expansion_levels >= 0),
  status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','GENERATED','AUDITED','VALIDATED','SEALED','SUPERSEDED','REJECTED')),
  parent_generation_id text REFERENCES science_generations(id) ON DELETE RESTRICT,
  scope jsonb NOT NULL DEFAULT '{}'::jsonb,
  node_count integer NOT NULL DEFAULT 0 CHECK (node_count >= 0),
  derivation_event_count integer NOT NULL DEFAULT 0 CHECK (derivation_event_count >= 0),
  true_confluence_count integer NOT NULL DEFAULT 0 CHECK (true_confluence_count >= 0),
  validation_report jsonb,
  preview boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  generated_at timestamptz,
  validated_at timestamptz
);

CREATE TABLE IF NOT EXISTS science_structures (
  generation_id text NOT NULL REFERENCES science_generations(id) ON DELETE RESTRICT,
  id text NOT NULL,
  kind text NOT NULL,
  dim integer NOT NULL,
  recurrence_order integer NOT NULL,
  sym text,
  sq integer,
  anti boolean,
  mult integer NOT NULL,
  bc text,
  dual integer NOT NULL CHECK (dual IN (0,1)),
  occ integer,
  lifecycle text NOT NULL CHECK (lifecycle IN ('ADMITTED','GENERABLE')),
  structural_sig jsonb NOT NULL,
  structural_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(generation_id, id),
  UNIQUE(generation_id, structural_hash)
);

CREATE TABLE IF NOT EXISTS science_derivation_events (
  generation_id text NOT NULL REFERENCES science_generations(id) ON DELETE RESTRICT,
  id text NOT NULL,
  operator text NOT NULL,
  operator_version text NOT NULL,
  inputs jsonb NOT NULL,
  output text NOT NULL,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  level integer NOT NULL CHECK (level > 0),
  input_structural_hashes jsonb NOT NULL,
  output_structural_hash text NOT NULL,
  event_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(generation_id, id),
  UNIQUE(generation_id, event_hash),
  FOREIGN KEY(generation_id, output) REFERENCES science_structures(generation_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS science_interpretations (
  id text PRIMARY KEY,
  generation_id text NOT NULL,
  structure_id text NOT NULL,
  domain text NOT NULL CHECK (domain IN ('PHYSICS','CHEMISTRY','BIOLOGY','COMPUTATION','MATHEMATICS')),
  target_id text NOT NULL REFERENCES science_canon_targets(id) ON DELETE RESTRICT,
  status text NOT NULL CHECK (status IN ('KNOWN','REDISCOVERED','VARIANT','UNMATCHED','EXPLAINED_FAILURE')),
  match_rule text NOT NULL,
  confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  sealed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(generation_id, structure_id) REFERENCES science_structures(generation_id, id) ON DELETE RESTRICT,
  UNIQUE(generation_id, structure_id, domain, target_id)
);

CREATE TABLE IF NOT EXISTS science_failures (
  id text PRIMARY KEY,
  candidate_id text REFERENCES science_candidates(id) ON DELETE RESTRICT,
  generation_id text REFERENCES science_generations(id) ON DELETE RESTRICT,
  domain text NOT NULL CHECK (domain IN ('PHYSICS','CHEMISTRY','BIOLOGY','COMPUTATION','MATHEMATICS')),
  code text NOT NULL CHECK (code IN ('MISSING_PRIMITIVE','MISSING_OPERATOR','SIGNATURE_COLLISION','AMBIGUOUS','OUT_OF_SCOPE','INSUFFICIENT_EVIDENCE','FORBIDDEN','VALIDATION_FAILED')),
  missing_distinction text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','GROUPED','RESOLVED')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS science_grammar_proposals (
  id text PRIMARY KEY,
  status text NOT NULL DEFAULT 'HUMAN_REVIEW_REQUIRED' CHECK (status IN ('HUMAN_REVIEW_REQUIRED','REJECTED','APPROVED_FOR_FUTURE_MANUAL_IMPLEMENTATION')),
  missing_distinction text NOT NULL,
  failure_ids jsonb NOT NULL,
  domains jsonb NOT NULL,
  proposal jsonb NOT NULL,
  counterexamples jsonb NOT NULL DEFAULT '[]'::jsonb,
  test_plan jsonb NOT NULL DEFAULT '[]'::jsonb,
  human_review_required boolean NOT NULL DEFAULT true CHECK (human_review_required = true),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS science_seals (
  generation_id text PRIMARY KEY REFERENCES science_generations(id) ON DELETE RESTRICT,
  validator_version text NOT NULL,
  test_report_hash text NOT NULL,
  sealed_at timestamptz NOT NULL DEFAULT now(),
  public_eligible boolean NOT NULL DEFAULT false,
  seal_payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS science_worker_runs (
  id text PRIMARY KEY,
  status text NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','FAILED','CIRCUIT_OPEN')),
  batch_size integer NOT NULL CHECK (batch_size > 0),
  max_agent_calls integer NOT NULL CHECK (max_agent_calls > 0),
  agent_calls integer NOT NULL DEFAULT 0 CHECK (agent_calls >= 0),
  error_count integer NOT NULL DEFAULT 0 CHECK (error_count >= 0),
  circuit_breaker_threshold integer NOT NULL CHECK (circuit_breaker_threshold > 0),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  report jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS science_public_state (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  active_generation_id text UNIQUE REFERENCES science_generations(id) ON DELETE RESTRICT,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS science_candidates_status_idx ON science_candidates(status, created_at);
CREATE INDEX IF NOT EXISTS science_evidence_candidate_idx ON science_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS science_agent_runs_candidate_idx ON science_agent_runs(candidate_id, started_at);
CREATE INDEX IF NOT EXISTS science_structures_hash_idx ON science_structures(structural_hash);
CREATE INDEX IF NOT EXISTS science_events_output_idx ON science_derivation_events(generation_id, output);
CREATE INDEX IF NOT EXISTS science_failures_pressure_idx ON science_failures(missing_distinction, domain, status);

CREATE OR REPLACE FUNCTION science_touch_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_touch_candidate_trigger ON science_candidates;
CREATE TRIGGER science_touch_candidate_trigger BEFORE UPDATE ON science_candidates
FOR EACH ROW EXECUTE FUNCTION science_touch_candidate();

CREATE OR REPLACE FUNCTION science_guard_frozen_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Frozen canon targets are immutable';
END;
$$;

DROP TRIGGER IF EXISTS science_frozen_target_guard ON science_canon_targets;
CREATE TRIGGER science_frozen_target_guard BEFORE UPDATE OR DELETE ON science_canon_targets
FOR EACH ROW EXECUTE FUNCTION science_guard_frozen_target();

CREATE OR REPLACE FUNCTION science_guard_frozen_canon() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'FROZEN' THEN
    RAISE EXCEPTION 'Frozen canon % is immutable', OLD.id;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_frozen_canon_guard ON science_canons;
CREATE TRIGGER science_frozen_canon_guard BEFORE UPDATE OR DELETE ON science_canons
FOR EACH ROW EXECUTE FUNCTION science_guard_frozen_canon();

CREATE OR REPLACE FUNCTION science_guard_sealed_generation_rows() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  candidate_generation text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    candidate_generation := OLD.generation_id;
  ELSE
    candidate_generation := NEW.generation_id;
  END IF;
  IF EXISTS (SELECT 1 FROM science_seals WHERE generation_id = candidate_generation) THEN
    RAISE EXCEPTION 'Sealed generation % is immutable', candidate_generation;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_structure_seal_guard ON science_structures;
CREATE TRIGGER science_structure_seal_guard BEFORE UPDATE OR DELETE ON science_structures
FOR EACH ROW EXECUTE FUNCTION science_guard_sealed_generation_rows();
DROP TRIGGER IF EXISTS science_event_seal_guard ON science_derivation_events;
CREATE TRIGGER science_event_seal_guard BEFORE UPDATE OR DELETE ON science_derivation_events
FOR EACH ROW EXECUTE FUNCTION science_guard_sealed_generation_rows();
DROP TRIGGER IF EXISTS science_interpretation_seal_guard ON science_interpretations;
CREATE TRIGGER science_interpretation_seal_guard BEFORE UPDATE OR DELETE ON science_interpretations
FOR EACH ROW EXECUTE FUNCTION science_guard_sealed_generation_rows();

CREATE OR REPLACE FUNCTION science_guard_generation_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = NEW.status THEN RETURN NEW; END IF;
  IF OLD.status = 'SEALED' THEN
    RAISE EXCEPTION 'Sealed generation % is immutable', OLD.id;
  END IF;
  IF NOT (
    (OLD.status = 'DRAFT' AND NEW.status IN ('GENERATED','REJECTED')) OR
    (OLD.status = 'GENERATED' AND NEW.status IN ('AUDITED','REJECTED')) OR
    (OLD.status = 'AUDITED' AND NEW.status IN ('VALIDATED','REJECTED')) OR
    (OLD.status = 'VALIDATED' AND NEW.status IN ('SEALED','REJECTED'))
  ) THEN
    RAISE EXCEPTION 'Invalid generation transition % -> %', OLD.status, NEW.status;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_generation_transition_guard ON science_generations;
CREATE TRIGGER science_generation_transition_guard BEFORE UPDATE OF status ON science_generations
FOR EACH ROW EXECUTE FUNCTION science_guard_generation_transition();

CREATE OR REPLACE FUNCTION science_guard_sealed_generation_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'SEALED' THEN
    RAISE EXCEPTION 'Sealed generation % is immutable', OLD.id;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_sealed_generation_metadata_guard ON science_generations;
CREATE TRIGGER science_sealed_generation_metadata_guard BEFORE UPDATE OR DELETE ON science_generations
FOR EACH ROW EXECUTE FUNCTION science_guard_sealed_generation_metadata();

CREATE OR REPLACE FUNCTION science_guard_public_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.active_generation_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM science_generations g
    JOIN science_seals s ON s.generation_id = g.id
    WHERE g.id = NEW.active_generation_id AND g.status = 'SEALED' AND s.public_eligible = true
  ) THEN
    RAISE EXCEPTION 'Public generation must be sealed and public eligible';
  END IF;
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS science_public_state_guard ON science_public_state;
CREATE TRIGGER science_public_state_guard BEFORE INSERT OR UPDATE ON science_public_state
FOR EACH ROW EXECUTE FUNCTION science_guard_public_state();

COMMIT;
