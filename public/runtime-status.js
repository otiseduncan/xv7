/**
 * Shared UI runtime-status helpers for the XV7 chat surface.
 *
 * This module intentionally exposes status-only phase labels. It never stores,
 * renders, or infers private reasoning; it only models safe visible phases such
 * as thinking, routing, running, success, failure, and approval required.
 */

const RUNTIME_PHASES = new Set([
  'idle',
  'thinking',
  'routing',
  'running',
  'streaming',
  'complete',
  'failed',
  'blocked',
  'needs_approval',
]);

const PHASE_LABELS = {
  idle: 'Idle',
  thinking: 'Thinking',
  routing: 'Routing',
  running: 'Running',
  streaming: 'Streaming',
  complete: 'Complete',
  failed: 'Failed',
  blocked: 'Blocked',
  needs_approval: 'Approval required',
};

const PHASE_HINTS = {
  idle: 'Ready for the next instruction.',
  thinking: 'Preparing a safe response.',
  routing: 'Choosing the correct XV7 lane.',
  running: 'Running an allowed operation.',
  streaming: 'Rendering the response.',
  complete: 'Finished.',
  failed: 'Action failed. Review the result card.',
  blocked: 'Blocked by safety policy.',
  needs_approval: 'Waiting for explicit approval.',
};

const ACTION_LABELS = {
  operator_status_report: 'Checking repository...',
  operator_validation_report: 'Running validation...',
  operator_patch_report: 'Preparing patch',
  operator_repair_report: 'Repair planning',
  operator_commit_report: 'Checking commit/push approval...',
  site_bundle_preview: 'Building site preview',
  site_bundle_export: 'Exporting sandbox files',
};

function normalizeRuntimePhase(phase) {
  const normalized = String(phase || '').trim().toLowerCase();
  return RUNTIME_PHASES.has(normalized) ? normalized : 'idle';
}

function runtimePhaseLabel(phase) {
  return PHASE_LABELS[normalizeRuntimePhase(phase)];
}

function runtimePhaseHint(phase) {
  return PHASE_HINTS[normalizeRuntimePhase(phase)];
}

function isRuntimePhaseBusy(phase) {
  return ['thinking', 'routing', 'running', 'streaming'].includes(normalizeRuntimePhase(phase));
}

function runtimeActionLabel(actionName) {
  const normalized = String(actionName || '').trim();
  return ACTION_LABELS[normalized] || normalized.replace(/_/g, ' ') || 'Runtime action';
}

function phaseFromOperatorStatus(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'succeeded' || normalized === 'success' || normalized === 'passed') return 'complete';
  if (normalized === 'failed' || normalized === 'error') return 'failed';
  if (normalized === 'denied' || normalized === 'blocked') return 'blocked';
  if (normalized === 'needs_approval' || normalized === 'pending_confirmation') return 'needs_approval';
  if (normalized === 'needs_patch') return 'blocked';
  if (normalized === 'running' || normalized === 'pending') return 'running';
  return 'complete';
}

function classifyPromptRuntime(prompt) {
  const text = String(prompt || '').toLowerCase();
  if (!text.trim()) return { phase: 'idle', label: runtimePhaseLabel('idle') };
  if (text.includes('run validation')) {
    return { phase: 'running', label: runtimeActionLabel('operator_validation_report') };
  }
  if (text.includes('check the repo') || text.includes('repo status')) {
    return { phase: 'running', label: runtimeActionLabel('operator_status_report') };
  }
  if (text.includes('commit') && text.includes('push')) {
    return { phase: 'needs_approval', label: runtimeActionLabel('operator_commit_report') };
  }
  if ((text.includes('export') || text.includes('save') || text.includes('write')) && text.includes('sandbox')) {
    return { phase: 'running', label: runtimeActionLabel('site_bundle_export') };
  }
  if (text.includes('website') || text.includes('site bundle')) {
    return { phase: 'running', label: runtimeActionLabel('site_bundle_preview') };
  }
  return { phase: 'thinking', label: runtimePhaseLabel('thinking') };
}

function createRuntimeStatusModel(overrides = {}) {
  const phase = normalizeRuntimePhase(overrides.phase);
  const actionName = String(overrides.actionName || '').trim();
  const label = String(overrides.label || '').trim() || (actionName ? runtimeActionLabel(actionName) : runtimePhaseLabel(phase));
  return {
    phase,
    label,
    hint: String(overrides.hint || '').trim() || runtimePhaseHint(phase),
    actionName,
    startedAt: Number.isFinite(overrides.startedAt) ? overrides.startedAt : Date.now(),
    endedAt: Number.isFinite(overrides.endedAt) ? overrides.endedAt : null,
    busy: isRuntimePhaseBusy(phase),
  };
}

function updateRuntimeStatusElement(element, model) {
  if (!element) return null;
  const status = createRuntimeStatusModel(model || {});
  element.dataset.runtimePhase = status.phase;
  element.classList.toggle('is-busy', status.busy);
  element.classList.toggle('is-terminal', status.phase === 'running');
  element.classList.toggle('is-complete', status.phase === 'complete');
  element.classList.toggle('is-failed', status.phase === 'failed');
  element.classList.toggle('is-blocked', status.phase === 'blocked');
  element.classList.toggle('needs-approval', status.phase === 'needs_approval');
  element.setAttribute('aria-live', status.busy ? 'polite' : 'off');
  element.innerHTML = '';

  const dot = document.createElement('span');
  dot.className = 'runtime-status-dot';

  const label = document.createElement('span');
  label.className = 'runtime-status-label';
  label.textContent = status.label;

  const hint = document.createElement('span');
  hint.className = 'runtime-status-hint';
  hint.textContent = status.hint;

  element.append(dot, label, hint);
  return status;
}

export {
  RUNTIME_PHASES,
  classifyPromptRuntime,
  createRuntimeStatusModel,
  isRuntimePhaseBusy,
  normalizeRuntimePhase,
  phaseFromOperatorStatus,
  runtimeActionLabel,
  runtimePhaseHint,
  runtimePhaseLabel,
  updateRuntimeStatusElement,
};
