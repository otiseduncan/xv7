// @vitest-environment jsdom

import { describe, expect, it } from 'vitest';
import {
  classifyPromptRuntime,
  createRuntimeStatusModel,
  isRuntimePhaseBusy,
  normalizeRuntimePhase,
  phaseFromOperatorStatus,
  runtimeActionLabel,
  runtimePhaseHint,
  runtimePhaseLabel,
  updateRuntimeStatusElement,
} from './runtime-status.js';

describe('runtime status UI helpers', () => {
  it('normalizes supported runtime phases and falls back safely', () => {
    expect(normalizeRuntimePhase('thinking')).toBe('thinking');
    expect(normalizeRuntimePhase('NEEDS_APPROVAL')).toBe('needs_approval');
    expect(normalizeRuntimePhase('raw-chain-of-thought')).toBe('idle');
  });

  it('labels only safe visible phases', () => {
    expect(runtimePhaseLabel('routing')).toBe('Routing');
    expect(runtimePhaseHint('routing')).toBe('Choosing the correct XV7 lane.');
    expect(runtimePhaseLabel('unknown')).toBe('Idle');
  });

  it('marks active phases as busy', () => {
    expect(isRuntimePhaseBusy('thinking')).toBe(true);
    expect(isRuntimePhaseBusy('running')).toBe(true);
    expect(isRuntimePhaseBusy('complete')).toBe(false);
    expect(isRuntimePhaseBusy('needs_approval')).toBe(false);
  });

  it('maps common operator statuses into visible UI phases', () => {
    expect(phaseFromOperatorStatus('succeeded')).toBe('complete');
    expect(phaseFromOperatorStatus('failed')).toBe('failed');
    expect(phaseFromOperatorStatus('denied')).toBe('blocked');
    expect(phaseFromOperatorStatus('needs_approval')).toBe('needs_approval');
  });

  it('classifies known prompts without exposing hidden reasoning', () => {
    expect(classifyPromptRuntime('check the repo')).toEqual({
      phase: 'running',
      label: 'Checking repo',
    });
    expect(classifyPromptRuntime('run validation')).toEqual({
      phase: 'running',
      label: 'Running validation',
    });
    expect(classifyPromptRuntime('commit and push')).toEqual({
      phase: 'needs_approval',
      label: 'Preparing commit/push',
    });
    expect(classifyPromptRuntime('Build me a website for a diner.')).toEqual({
      phase: 'running',
      label: 'Building site preview',
    });
  });

  it('creates a normalized status model', () => {
    const model = createRuntimeStatusModel({ phase: 'running', actionName: 'operator_validation_report', startedAt: 10 });
    expect(model).toMatchObject({
      phase: 'running',
      label: 'Running validation',
      hint: 'Running an allowed operation.',
      actionName: 'operator_validation_report',
      startedAt: 10,
      endedAt: null,
      busy: true,
    });
  });

  it('renders a status element with phase classes and text', () => {
    const el = document.createElement('div');
    const status = updateRuntimeStatusElement(el, {
      phase: 'running',
      actionName: 'site_bundle_export',
    });

    expect(status.phase).toBe('running');
    expect(el.dataset.runtimePhase).toBe('running');
    expect(el.classList.contains('is-busy')).toBe(true);
    expect(el.classList.contains('is-terminal')).toBe(true);
    expect(el.textContent).toContain('Exporting sandbox files');
    expect(el.textContent).toContain('Running an allowed operation.');
  });

  it('falls back to readable action labels', () => {
    expect(runtimeActionLabel('operator_custom_action')).toBe('operator custom action');
    expect(runtimeActionLabel('')).toBe('Runtime action');
  });
});
