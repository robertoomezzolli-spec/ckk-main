"""Read-only sleep/consolidation projection for the operator Observatory.

The projection contains only redacted observable outcomes. It never reads the
organism database, model context, prompts, message bodies or ground truth.
"""

from __future__ import annotations

import html
import time
from typing import Any, Iterable


WINDOW_SECONDS = {
    "1h": 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "lifetime": None,
}

SLEEP_EVENT_TYPES = frozenset(
    {"OBSERVED", "RETRIEVED", "ACTED", "LEARNED", "CONSOLIDATED", "FAILED", "SLEEP_PHASE"}
)


def window_start(window: str, *, now: float | None = None) -> float | None:
    if window not in WINDOW_SECONDS:
        raise ValueError("window must be one of 1h, 24h, 7d, 30d or lifetime")
    seconds = WINDOW_SECONDS[window]
    return None if seconds is None else (time.time() if now is None else now) - seconds


def _number(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _clean_phase_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "observation_count",
        "effect_count",
        "audit_chain_valid",
        "candidate_sequence",
        "memory_sequence",
        "learning_proposal_count",
    }
    return {key: payload[key] for key in sorted(allowed) if key in payload}


def build_sleep_report(
    events: Iterable[dict[str, Any]],
    *,
    window: str,
    limit: int = 120,
) -> dict[str, Any]:
    """Group the append-only observable stream into privacy-safe sleep cycles."""

    if window not in WINDOW_SECONDS:
        raise ValueError("window must be one of 1h, 24h, 7d, 30d or lifetime")
    cycle_limit = max(1, min(int(limit), 500))
    cycles_by_ref: dict[str, dict[str, Any]] = {}
    ordered = sorted(events, key=lambda item: (float(item.get("occurred_at") or 0), int(item.get("sequence") or 0)))

    for event in ordered:
        event_type = str(event.get("event_type") or "")
        if event_type not in SLEEP_EVENT_TYPES:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        event_ref = payload.get("event_ref")
        if not isinstance(event_ref, str) or not event_ref:
            continue
        occurred_at = float(event.get("occurred_at") or 0)
        cycle = cycles_by_ref.setdefault(
            event_ref,
            {
                "cycle_id": event_ref,
                "started_at": occurred_at,
                "last_event_at": occurred_at,
                "completed_at": None,
                "status": "running",
                "trigger": None,
                "retrieval": None,
                "action": None,
                "learning": {"proposal_count": 0, "belief_delta": 0, "committed": False},
                "consolidation": None,
                "phase_boundaries": [],
                "phase_source": "not_yet_observed",
                "evidence_ids": [],
                "session_ref": event.get("session_id"),
            },
        )
        cycle["started_at"] = min(float(cycle["started_at"]), occurred_at)
        cycle["last_event_at"] = max(float(cycle["last_event_at"]), occurred_at)
        evidence_id = event.get("evidence_id")
        if isinstance(evidence_id, str):
            cycle["evidence_ids"].append(evidence_id)

        if event_type == "OBSERVED":
            cycle["trigger"] = {
                "sensor_class": str(payload.get("sensor_class") or "unknown"),
                "kind": str(payload.get("kind") or "unknown"),
                "trust": payload.get("trust"),
                "payload_keys": list(payload.get("payload_keys") or []),
                "payload_bytes": _number(payload.get("payload_bytes")),
                "text_length": _number(payload.get("text_length")) if "text_length" in payload else None,
                "content_exported": False,
            }
        elif event_type == "RETRIEVED":
            cycle["retrieval"] = {
                "episodic_count": _number(payload.get("episodic_count")),
                "committed_belief_count": _number(payload.get("committed_belief_count")),
                "external_evidence_count": _number(payload.get("ckk_external_evidence_count")),
                "external_commit_sha": payload.get("ckk_commit_sha"),
                "content_exported": False,
            }
        elif event_type == "SLEEP_PHASE":
            phase = str(payload.get("phase") or "")
            if phase in {"WAKE", "NREM", "REM", "HALTED"}:
                cycle["phase_boundaries"].append(
                    {"phase": phase, "occurred_at": occurred_at, "detail": _clean_phase_payload(payload)}
                )
                cycle["phase_source"] = "runtime_boundary"
                cycle["learning"]["proposal_count"] = max(
                    cycle["learning"]["proposal_count"], _number(payload.get("learning_proposal_count"))
                )
        elif event_type == "ACTED":
            cycle["action"] = {
                "capability": payload.get("capability"),
                "success": bool(payload.get("success")),
                "simulated": bool(payload.get("simulated")),
                "action_class": payload.get("action_class"),
                "provider_http_status": payload.get("provider_http_status"),
                "provider_message_count": _number(payload.get("provider_message_count")),
            }
        elif event_type == "LEARNED":
            cycle["learning"]["belief_delta"] += _number(payload.get("belief_delta"))
            cycle["learning"]["committed"] = cycle["learning"]["belief_delta"] > 0
        elif event_type == "CONSOLIDATED":
            cycle["status"] = "completed"
            cycle["completed_at"] = occurred_at
            cycle["consolidation"] = {
                "sleep_cycle": str(payload.get("sleep_cycle") or ""),
                "identity_chain_valid": bool(payload.get("identity_chain_valid")),
                "audit_chain_valid": bool(payload.get("audit_chain_valid")),
                "memory_advanced": bool(payload.get("memory_advanced")),
                "checkpoint_persisted": bool(payload.get("checkpoint_persisted")),
                "memory_commit": event.get("memory_version"),
            }
            if not cycle["phase_boundaries"] and payload.get("sleep_cycle") == "NREM_REM_WAKE":
                cycle["phase_source"] = "completed_cycle_summary"
        elif event_type == "FAILED":
            cycle["status"] = "failed"
            cycle["completed_at"] = occurred_at
            cycle["failure"] = {
                "error_type": str(payload.get("error_type") or "unknown"),
                "capability": payload.get("capability"),
                "error_text_exported": False,
            }

    cycles = list(cycles_by_ref.values())
    for cycle in cycles:
        finished = cycle["completed_at"] if cycle["completed_at"] is not None else cycle["last_event_at"]
        cycle["cycle_latency_ms"] = round(max(0.0, (float(finished) - float(cycle["started_at"])) * 1000), 2)
        cycle["trigger_class"] = _trigger_class(cycle.get("trigger"))
        cycle["phase_boundaries"].sort(key=lambda item: item["occurred_at"])
    cycles.sort(key=lambda item: (float(item["started_at"]), item["cycle_id"]), reverse=True)

    all_cycles = cycles
    displayed = all_cycles[:cycle_limit]
    latest = all_cycles[0] if all_cycles else None
    current_phase = _current_phase(latest)
    completed = [cycle for cycle in all_cycles if cycle["status"] == "completed"]
    learned = [cycle for cycle in completed if cycle["learning"]["belief_delta"] > 0]
    phase_covered = [cycle for cycle in all_cycles if cycle["phase_source"] == "runtime_boundary"]
    return {
        "scientific_scope": (
            "Observable functional consolidation telemetry. The spatial view is a data map, "
            "not a recording of subjective dreams or hidden reasoning."
        ),
        "privacy": {
            "message_content_exported": False,
            "phone_identifiers_exported": False,
            "model_reasoning_exported": False,
            "ground_truth_exported": False,
        },
        "window": window,
        "generated_at": time.time(),
        "current_phase": current_phase,
        "stats": {
            "cycles": len(all_cycles),
            "completed": len(completed),
            "failed": sum(cycle["status"] == "failed" for cycle in all_cycles),
            "running": sum(cycle["status"] == "running" for cycle in all_cycles),
            "clock_triggered": sum(cycle["trigger_class"] == "clock" for cycle in all_cycles),
            "conversation_triggered": sum(cycle["trigger_class"] == "conversation" for cycle in all_cycles),
            "learning_cycles": len(learned),
            "beliefs_committed": sum(cycle["learning"]["belief_delta"] for cycle in completed),
            "runtime_phase_coverage": len(phase_covered),
        },
        "cycles": displayed,
        "truncated": len(all_cycles) > len(displayed),
    }


def _trigger_class(trigger: dict[str, Any] | None) -> str:
    if not trigger:
        return "unknown"
    if trigger.get("sensor_class") == "internal.clock" or trigger.get("kind") == "clock.tick":
        return "clock"
    if trigger.get("sensor_class") == "whatsapp":
        return "conversation"
    return "system"


def _current_phase(cycle: dict[str, Any] | None) -> str:
    if not cycle or cycle.get("status") in {"completed", "failed"}:
        return "WAKE"
    boundaries = cycle.get("phase_boundaries") or []
    if boundaries:
        return str(boundaries[-1].get("phase") or "WAKE")
    return "WAKE"


def sleep_dashboard_html(scientific_label: str) -> str:
    return _SLEEP_DASHBOARD.replace("__SCIENTIFIC_LABEL__", html.escape(scientific_label))


_SLEEP_DASHBOARD = r'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>KAIROS Schlaf-Observatorium</title>
<style>
:root {
  --bg: #071017;
  --surface: #0b1821;
  --surface-raised: #10222d;
  --line: #23404f;
  --line-bright: #356278;
  --ink: #edf7fa;
  --muted: #91abb7;
  --accent: #53b9dd;
  --accent-soft: rgba(83, 185, 221, .13);
  --danger: #ee8075;
  --radius: 14px;
  --ease-out: cubic-bezier(.23, 1, .32, 1);
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  min-width: 320px;
  background:
    radial-gradient(circle at 72% 18%, rgba(50, 107, 130, .13), transparent 34rem),
    var(--bg);
  color: var(--ink);
  font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
button, a { font: inherit; }
button { color: inherit; }
a { color: var(--ink); }
.shell { width: min(1540px, 100%); min-height: 100dvh; margin: 0 auto; padding: 24px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.title-block { display: flex; align-items: flex-start; gap: 14px; }
.mark {
  width: 36px; height: 36px; display: grid; place-items: center; flex: 0 0 auto;
  border: 1px solid var(--line-bright); border-radius: 50%; color: var(--accent);
  font: 700 15px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  box-shadow: inset 0 0 0 5px rgba(83, 185, 221, .05);
}
h1 { margin: 0; font-size: clamp(20px, 2vw, 27px); line-height: 1.05; letter-spacing: -.025em; }
.subtitle { margin: 7px 0 0; color: var(--muted); max-width: 62ch; }
.nav-link {
  display: inline-flex; align-items: center; min-height: 36px; padding: 0 12px;
  border: 1px solid var(--line); border-radius: 9px; text-decoration: none;
  background: rgba(11, 24, 33, .74); transition: border-color 160ms ease, transform 160ms var(--ease-out);
}
.nav-link:active { transform: scale(.97); }
.phase-strip {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); align-items: center;
  gap: 0; margin-bottom: 18px; border: 1px solid var(--line); border-radius: var(--radius);
  background: rgba(11, 24, 33, .72); overflow: hidden;
}
.phase {
  position: relative; min-height: 58px; display: grid; place-items: center; color: var(--muted);
  font: 650 12px/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em;
}
.phase + .phase { border-left: 1px solid var(--line); }
.phase::after { content: ""; position: absolute; left: 0; right: 100%; bottom: 0; height: 2px; background: var(--accent); transition: right 220ms var(--ease-out); }
.phase.active { color: var(--ink); background: var(--accent-soft); }
.phase.active::after { right: 0; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.window-button {
  min-height: 34px; padding: 0 12px; border: 1px solid var(--line); border-radius: 9px;
  background: var(--surface); cursor: pointer; transition: border-color 150ms ease, transform 150ms var(--ease-out), background 150ms ease;
}
.window-button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); }
.window-button:active { transform: scale(.97); }
.workspace { display: grid; grid-template-columns: minmax(0, 1.8fr) minmax(280px, .62fr); gap: 12px; }
.map-panel, .detail-panel, .history-panel {
  border: 1px solid var(--line); border-radius: var(--radius); background: rgba(11, 24, 33, .9);
  overflow: hidden; box-shadow: inset 0 1px 0 rgba(237, 247, 250, .025);
}
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px 15px; border-bottom: 1px solid var(--line); }
.panel-heading h2 { margin: 0; font-size: 13px; letter-spacing: .015em; }
.live-label { color: var(--accent); font: 600 11px/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
.map-wrap { position: relative; min-height: 540px; }
#sleep-map { display: block; width: 100%; height: 540px; }
.map-caption {
  position: absolute; left: 14px; bottom: 12px; max-width: 70ch; margin: 0; padding: 8px 10px;
  border-radius: 9px; background: rgba(7, 16, 23, .82); color: var(--muted); font-size: 12px;
  backdrop-filter: blur(10px);
}
.detail-panel { min-height: 540px; }
.detail-content { padding: 15px; }
.cycle-time { margin: 0 0 4px; font: 650 16px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace; }
.cycle-kind { margin: 0 0 18px; color: var(--muted); }
.fact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.fact { min-height: 76px; padding: 11px; background: var(--surface); }
.fact dt { margin: 0 0 6px; color: var(--muted); font-size: 11px; }
.fact dd { margin: 0; font: 650 14px/1.35 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }
.trace { margin-top: 17px; }
.trace h3 { margin: 0 0 9px; font-size: 12px; }
.trace-step { display: grid; grid-template-columns: 56px 1fr; gap: 10px; padding: 8px 0; color: var(--muted); }
.trace-step + .trace-step { border-top: 1px solid rgba(35, 64, 79, .7); }
.trace-step strong { color: var(--ink); font: 650 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
.trace-step span { overflow-wrap: anywhere; }
.history-panel { margin-top: 12px; }
.stats { display: flex; flex-wrap: wrap; gap: 18px; color: var(--muted); font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
.stats strong { color: var(--ink); font-size: 15px; }
.history { display: grid; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr)); gap: 8px; padding: 12px; }
.cycle-button {
  min-height: 84px; padding: 10px; text-align: left; cursor: pointer; border: 1px solid var(--line);
  border-radius: 10px; background: var(--surface); transition: border-color 160ms ease, transform 160ms var(--ease-out), background 160ms ease;
}
.cycle-button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); }
.cycle-button:active { transform: scale(.98); }
.cycle-button time, .cycle-button small { display: block; }
.cycle-button time { margin-bottom: 7px; font: 650 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; }
.cycle-button small { color: var(--muted); }
.cycle-button.failed { border-color: rgba(238, 128, 117, .6); }
.footer-note { margin: 16px 2px 0; color: var(--muted); font-size: 12px; max-width: 95ch; }
.state-message { min-height: 360px; display: grid; place-items: center; padding: 32px; text-align: center; color: var(--muted); }
.skeleton { background: linear-gradient(90deg, var(--surface) 25%, var(--surface-raised) 50%, var(--surface) 75%); background-size: 200% 100%; }
.error { color: var(--danger); }
@media (hover: hover) and (pointer: fine) {
  .nav-link:hover, .window-button:hover, .cycle-button:hover { border-color: var(--line-bright); }
}
@media (prefers-reduced-motion: no-preference) {
  .skeleton { animation: shimmer 1.4s linear infinite; }
  @keyframes shimmer { to { background-position: -200% 0; } }
}
@media (max-width: 820px) {
  .shell { padding: 14px; }
  .topbar { align-items: stretch; flex-direction: column; }
  .nav-link { align-self: flex-start; }
  .workspace { grid-template-columns: 1fr; }
  .map-wrap { min-height: 0; }
  .detail-panel { min-height: 410px; }
  #sleep-map { height: 360px; }
  .map-caption { position: static; max-width: none; margin: 0 12px 12px; }
}
@media (max-width: 520px) {
  .phase { min-height: 48px; font-size: 10px; }
  .history { grid-template-columns: 1fr 1fr; }
  .fact-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-transparency: reduce) {
  .map-caption { background: var(--bg); backdrop-filter: none; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
</head>
<body>
<main class="shell">
  <header class="topbar">
    <div class="title-block">
      <div class="mark" aria-hidden="true">K</div>
      <div>
        <h1>KAIROS Schlaf-Observatorium</h1>
        <p class="subtitle">Reale NREM-, REM- und Commit-Telemetrie als räumliche Datenkarte.</p>
      </div>
    </div>
    <a class="nav-link" href="/awareness">Awareness Übersicht</a>
  </header>

  <section class="phase-strip" aria-label="Aktueller Laufzeitzustand">
    <div class="phase" data-phase="WAKE_START">WAKE</div>
    <div class="phase" data-phase="NREM">NREM</div>
    <div class="phase" data-phase="REM">REM</div>
    <div class="phase" data-phase="WAKE">WAKE</div>
  </section>

  <nav class="toolbar" aria-label="Zeitfenster">
    <button class="window-button" data-window="1h" aria-pressed="false">1 Stunde</button>
    <button class="window-button" data-window="24h" aria-pressed="true">24 Stunden</button>
    <button class="window-button" data-window="7d" aria-pressed="false">7 Tage</button>
    <button class="window-button" data-window="30d" aria-pressed="false">30 Tage</button>
    <button class="window-button" data-window="lifetime" aria-pressed="false">Gesamt</button>
  </nav>

  <section class="workspace" aria-live="polite">
    <div class="map-panel">
      <div class="panel-heading"><h2>Konsolidierungskarte</h2><span class="live-label" id="live-state">LÄDT</span></div>
      <div class="map-wrap" id="map-wrap">
        <canvas id="sleep-map" role="img" aria-label="Datenkarte des ausgewählten Konsolidierungszyklus"></canvas>
        <p class="map-caption">Positionen zeigen Datenbeziehungen. Sie sind keine Aufnahme subjektiver Bilder oder privater Gedanken.</p>
      </div>
    </div>
    <aside class="detail-panel">
      <div class="panel-heading"><h2>Ausgewählter Zyklus</h2><span class="live-label" id="cycle-state"></span></div>
      <div class="detail-content" id="cycle-detail"><div class="state-message skeleton">Telemetrie wird geladen</div></div>
    </aside>
  </section>

  <section class="history-panel">
    <div class="panel-heading"><h2>Zyklen</h2><div class="stats" id="stats"></div></div>
    <div class="history" id="history"><div class="state-message skeleton">Historie wird geladen</div></div>
  </section>

  <p class="footer-note">__SCIENTIFIC_LABEL__ Das Observatory erhält keine Nachrichtentexte, Telefonnummern, Modellgedanken oder versteckte Testdaten.</p>
</main>
<script>
(() => {
  const canvas = document.querySelector('#sleep-map');
  const context = canvas.getContext('2d');
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let report = null;
  let selectedId = null;
  let activeWindow = '24h';
  let frame = 0;
  let lastFrame = 0;

  const formatTime = value => new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit'
  }).format(new Date(value * 1000));
  const compact = value => typeof value === 'string' && value.length > 14 ? value.slice(0, 12) + '...' : (value ?? 'keine');
  const phaseLabel = cycle => cycle.phase_source === 'runtime_boundary' ? 'gemessene Phasengrenzen' : 'Zyklusabschluss belegt';
  const triggerLabel = cycle => ({clock: 'Clock', conversation: 'Gespräch', system: 'System', unknown: 'Unbekannt'})[cycle.trigger_class] || cycle.trigger_class;
  const statusLabel = status => ({completed: 'ABGESCHLOSSEN', failed: 'FEHLER', running: 'LÄUFT'})[status] || String(status).toUpperCase();

  function currentCycle() {
    if (!report || !report.cycles.length) return null;
    return report.cycles.find(cycle => cycle.cycle_id === selectedId) || report.cycles[0];
  }

  function setPhase(phase, cycle) {
    const elements = [...document.querySelectorAll('.phase')];
    elements.forEach(element => element.classList.remove('active'));
    const key = phase === 'NREM' || phase === 'REM' ? phase : 'WAKE';
    const initialWake = key === 'WAKE' && cycle?.status === 'running' && !cycle.phase_boundaries.length;
    const target = key === 'WAKE' ? elements[initialWake ? 0 : 3] : elements.find(element => element.dataset.phase === key);
    if (target) target.classList.add('active');
  }

  function makeFact(label, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'fact';
    const term = document.createElement('dt');
    const detail = document.createElement('dd');
    term.textContent = label;
    detail.textContent = String(value ?? 'keine');
    wrapper.append(term, detail);
    return wrapper;
  }

  function traceStep(label, text) {
    const row = document.createElement('div');
    row.className = 'trace-step';
    const strong = document.createElement('strong');
    const span = document.createElement('span');
    strong.textContent = label;
    span.textContent = text;
    row.append(strong, span);
    return row;
  }

  function renderDetail(cycle) {
    const root = document.querySelector('#cycle-detail');
    root.replaceChildren();
    if (!cycle) {
      const empty = document.createElement('div');
      empty.className = 'state-message';
      empty.textContent = 'In diesem Zeitfenster wurden keine Zyklen beobachtet.';
      root.append(empty);
      document.querySelector('#cycle-state').textContent = '';
      return;
    }
    document.querySelector('#cycle-state').textContent = statusLabel(cycle.status);
    const title = document.createElement('p');
    title.className = 'cycle-time';
    title.textContent = formatTime(cycle.started_at);
    const kind = document.createElement('p');
    kind.className = 'cycle-kind';
    kind.textContent = triggerLabel(cycle) + ' / ' + (cycle.trigger?.kind || 'unbekannt');
    const facts = document.createElement('dl');
    facts.className = 'fact-grid';
    facts.append(
      makeFact('Zykluslatenz', cycle.cycle_latency_ms.toFixed(0) + ' ms'),
      makeFact('Episoden gelesen', cycle.retrieval?.episodic_count ?? 0),
      makeFact('Beliefs vorher', cycle.retrieval?.committed_belief_count ?? 0),
      makeFact('Learning-Proposals', cycle.learning.proposal_count),
      makeFact('Persistenter Zuwachs', '+' + cycle.learning.belief_delta),
      makeFact('Memory Commit', compact(cycle.consolidation?.memory_commit))
    );
    const trace = document.createElement('div');
    trace.className = 'trace';
    const heading = document.createElement('h3');
    heading.textContent = 'Beobachtbarer Backtrace';
    trace.append(heading);
    trace.append(traceStep('WAKE', (cycle.trigger?.payload_bytes ?? 0) + ' Bytes struktureller Input, Inhalt nicht exportiert'));
    trace.append(traceStep('RETRIEVE', (cycle.retrieval?.episodic_count ?? 0) + ' Episoden und ' + (cycle.retrieval?.external_evidence_count ?? 0) + ' externe Evidenzen'));
    trace.append(traceStep('NREM', phaseLabel(cycle) + ', ' + cycle.learning.proposal_count + ' Learning-Proposals'));
    trace.append(traceStep('REM', cycle.consolidation?.audit_chain_valid === false ? 'Audit-Invariante fehlgeschlagen' : 'Audit-Invariante bestätigt'));
    trace.append(traceStep('WAKE', cycle.status === 'completed' ? 'Checkpoint persistent, Memory-Kette fortgesetzt' : cycle.status));
    if (cycle.action?.capability) {
      trace.append(traceStep('ACTION', cycle.action.capability + ', Erfolg: ' + (cycle.action.success ? 'ja' : 'nein')));
    } else {
      trace.append(traceStep('ACTION', 'Keine externe Aktion'));
    }
    root.append(title, kind, facts, trace);
  }

  function renderStats() {
    const root = document.querySelector('#stats');
    root.replaceChildren();
    if (!report) return;
    const items = [
      ['Zyklen', report.stats.cycles],
      ['Gespräche', report.stats.conversation_triggered],
      ['Clock', report.stats.clock_triggered],
      ['Learning', report.stats.learning_cycles],
      ['Beliefs', '+' + report.stats.beliefs_committed]
    ];
    for (const [label, value] of items) {
      const span = document.createElement('span');
      const strong = document.createElement('strong');
      strong.textContent = String(value);
      span.append(strong, document.createElement('br'), document.createTextNode(label));
      root.append(span);
    }
  }

  function renderHistory() {
    const root = document.querySelector('#history');
    root.replaceChildren();
    if (!report?.cycles.length) {
      const empty = document.createElement('div');
      empty.className = 'state-message';
      empty.textContent = 'Noch keine beobachtbaren Konsolidierungszyklen.';
      root.append(empty);
      return;
    }
    for (const cycle of report.cycles) {
      const button = document.createElement('button');
      button.className = 'cycle-button' + (cycle.status === 'failed' ? ' failed' : '');
      button.type = 'button';
      button.setAttribute('aria-pressed', cycle.cycle_id === selectedId ? 'true' : 'false');
      const timestamp = document.createElement('time');
      timestamp.dateTime = new Date(cycle.started_at * 1000).toISOString();
      timestamp.textContent = formatTime(cycle.started_at);
      const trigger = document.createElement('small');
      trigger.textContent = triggerLabel(cycle) + ' / Learning +' + cycle.learning.belief_delta;
      const phase = document.createElement('small');
      phase.textContent = cycle.phase_source === 'runtime_boundary' ? 'Phasen gemessen' : 'Commit belegt';
      button.append(timestamp, trigger, phase);
      button.addEventListener('click', () => {
        selectedId = cycle.cycle_id;
        renderAll();
      });
      root.append(button);
    }
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.min(devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(rect.width * ratio));
    const height = Math.max(1, Math.round(rect.height * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    return rect;
  }

  function drawMap(now = 0) {
    const rect = resizeCanvas();
    const width = rect.width;
    const height = rect.height;
    context.clearRect(0, 0, width, height);
    const cycle = currentCycle();
    context.fillStyle = '#091720';
    context.fillRect(0, 0, width, height);

    const seed = cycle ? [...cycle.cycle_id].reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 7) : 7;
    context.fillStyle = 'rgba(145,171,183,.18)';
    for (let index = 0; index < 56; index += 1) {
      const x = ((seed * (index + 17) * 37) % 997) / 997 * width;
      const y = ((seed * (index + 31) * 53) % 991) / 991 * height;
      context.fillRect(x, y, 1, 1);
    }
    if (!cycle) {
      context.fillStyle = '#91abb7';
      context.font = '14px ui-sans-serif, system-ui';
      context.textAlign = 'center';
      context.fillText('Keine Zyklusdaten im gewählten Zeitfenster', width / 2, height / 2);
      return;
    }

    const nodes = [
      {key: 'experience', label: 'ERFAHRUNG', sub: triggerLabel(cycle), x: .16, y: .58, size: 39},
      {key: 'retrieval', label: 'RETRIEVAL', sub: (cycle.retrieval?.episodic_count ?? 0) + ' Episoden', x: .42, y: .25, size: 34},
      {key: 'action', label: 'AKTION', sub: cycle.action?.capability || 'keine', x: .79, y: .38, size: 34},
      {key: 'commit', label: 'COMMIT', sub: statusLabel(cycle.status).toLowerCase(), x: .58, y: .76, size: 43}
    ];
    if (cycle.learning.belief_delta > 0 || cycle.learning.proposal_count > 0) {
      nodes.push({key: 'learning', label: 'LEARNING', sub: '+' + cycle.learning.belief_delta + ' persistent', x: .78, y: .72, size: 31});
    }
    const byKey = Object.fromEntries(nodes.map(node => [node.key, node]));
    const edges = [['experience','retrieval'], ['retrieval','action'], ['action','commit'], ['experience','commit']];
    if (byKey.learning) edges.push(['retrieval','learning'], ['learning','commit']);
    const pulse = reduceMotion ? .55 : .42 + Math.sin(now / 700) * .13;
    context.lineWidth = 1;
    for (const [fromKey, toKey] of edges) {
      const from = byKey[fromKey];
      const to = byKey[toKey];
      context.beginPath();
      context.moveTo(from.x * width, from.y * height);
      context.lineTo(to.x * width, to.y * height);
      context.strokeStyle = 'rgba(83,185,221,.31)';
      context.stroke();
      if (!reduceMotion) {
        const travel = ((now / 2200) + edges.indexOf(edges.find(edge => edge[0] === fromKey && edge[1] === toKey)) * .14) % 1;
        const x = (from.x + (to.x - from.x) * travel) * width;
        const y = (from.y + (to.y - from.y) * travel) * height;
        context.beginPath(); context.arc(x, y, 2.2, 0, Math.PI * 2);
        context.fillStyle = 'rgba(171,226,245,.9)'; context.fill();
      }
    }
    for (const node of nodes) {
      const x = node.x * width;
      const y = node.y * height;
      const radius = node.size + pulse * 2;
      const gradient = context.createRadialGradient(x - radius * .24, y - radius * .27, 2, x, y, radius);
      gradient.addColorStop(0, 'rgba(208,242,251,.88)');
      gradient.addColorStop(.18, 'rgba(83,185,221,.48)');
      gradient.addColorStop(1, 'rgba(13,42,55,.24)');
      context.beginPath(); context.arc(x, y, radius, 0, Math.PI * 2);
      context.fillStyle = gradient; context.fill();
      context.strokeStyle = 'rgba(133,211,236,.55)'; context.stroke();
      context.fillStyle = '#edf7fa'; context.textAlign = 'center';
      context.font = '650 11px ui-monospace, SFMono-Regular, Menlo, monospace';
      context.fillText(node.label, x, y + radius + 18);
      context.fillStyle = '#91abb7'; context.font = '11px ui-sans-serif, system-ui';
      context.fillText(String(node.sub).slice(0, 28), x, y + radius + 34);
    }
    canvas.setAttribute('aria-label', 'Zyklus ' + formatTime(cycle.started_at) + ': ' + triggerLabel(cycle) + ', Learning plus ' + cycle.learning.belief_delta + ', Status ' + cycle.status);
  }

  function animate(now) {
    if (now - lastFrame > 45) { drawMap(now); lastFrame = now; }
    frame = requestAnimationFrame(animate);
  }

  function renderAll() {
    const cycle = currentCycle();
    renderDetail(cycle);
    renderStats();
    renderHistory();
    setPhase(report?.current_phase || 'WAKE', cycle);
    document.querySelector('#live-state').textContent = report ? report.current_phase + ' / LIVE' : 'OFFLINE';
    drawMap(performance.now());
  }

  async function load() {
    try {
      const response = await fetch('api/sleep?window=' + encodeURIComponent(activeWindow) + '&limit=180', {headers: {'accept': 'application/json'}});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const next = await response.json();
      report = next;
      if (!selectedId || !next.cycles.some(cycle => cycle.cycle_id === selectedId)) selectedId = next.cycles[0]?.cycle_id || null;
      renderAll();
    } catch (error) {
      document.querySelector('#live-state').textContent = 'NICHT ERREICHBAR';
      const detail = document.querySelector('#cycle-detail');
      detail.replaceChildren();
      const message = document.createElement('div');
      message.className = 'state-message error';
      message.textContent = 'Telemetrie konnte nicht geladen werden: ' + error.message;
      detail.append(message);
    }
  }

  document.querySelectorAll('.window-button').forEach(button => button.addEventListener('click', () => {
    activeWindow = button.dataset.window;
    document.querySelectorAll('.window-button').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
    selectedId = null;
    load();
  }));
  new ResizeObserver(() => drawMap(performance.now())).observe(document.querySelector('#map-wrap'));
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  if (!reduceMotion) frame = requestAnimationFrame(animate);
  window.addEventListener('pagehide', () => cancelAnimationFrame(frame), {once: true});
  load();
  setInterval(() => { if (!document.hidden) load(); }, 5000);
})();
</script>
</body>
</html>'''
