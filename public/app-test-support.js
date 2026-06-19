import { vi } from 'vitest';
import { buildBrainRecords } from './app-test-brain-records.js';

export function okJson(payload) {
  return {
    ok: true,
    status: 200,
    async json() { return payload; },
    async text() { return JSON.stringify(payload); },
  };
}

export function errorText(status, message) {
  return {
    ok: false,
    status,
    async json() { return { detail: message }; },
    async text() { return message; },
  };
}


export function createRuntimeFetchMock(options = {}) {
  const state = {
    activeProfile: options.activeProfile || 'balanced',
    source: options.source || 'env',
    reachable: options.reachable ?? true,
    failModels: options.failModels ?? false,
    brainRecords: buildBrainRecords(),
    activeContextFocusId: options.activeContextFocusId || '',
    activeContextFocusSummary: options.activeContextFocusSummary || '',
    activeContextRecordIds: Array.isArray(options.activeContextRecordIds) ? options.activeContextRecordIds : [],
  };

  const profiles = {
    low_resource: {
      chat: 'qwen3:1.7b',
      reasoning: 'qwen3:8b',
      code: 'qwen3:8b',
      embedding: 'nomic-embed-text:latest',
    },
    balanced: {
      chat: 'qwen3:8b',
      reasoning: 'qwen3:14b',
      code: 'qwen3:14b',
      embedding: 'nomic-embed-text:latest',
    },
    local_test: {
      chat: 'qwen3:14b',
      reasoning: 'qwen3:14b',
      code: 'qwen3-coder:30b',
      embedding: 'nomic-embed-text:latest',
    },
    large_code: {
      chat: 'qwen3-coder:30b',
      reasoning: 'qwen3:14b',
      code: 'qwen3-coder:30b',
      embedding: 'nomic-embed-text:latest',
    },
  };

  const availability = {
    chat: state.reachable,
    reasoning: state.reachable,
    code: state.reachable,
    embedding: state.reachable,
  };

  return vi.fn(async (url, init = {}) => {
    const method = (init.method || 'GET').toUpperCase();
    const path = new URL(url, 'http://localhost').pathname;
    const query = new URL(url, 'http://localhost').searchParams;
    let pendingAction = state.pendingAction || null;

    if (path === '/personas') {
      return okJson({
        personas: {
          default: { name: 'default', model: 'qwen3:8b' },
        },
      });
    }

    if (path === '/runtime/models' && method === 'GET') {
      if (state.failModels) {
        return errorText(503, 'runtime models unavailable');
      }

      return okJson({
        available_profiles: Object.keys(profiles),
        profiles,
        active_profile: state.activeProfile,
        profile_source: state.source,
        resolved_models: profiles[state.activeProfile],
        availability,
        ollama: {
          reachable: state.reachable,
          base_url: 'http://ollama:11434',
          models: state.reachable ? ['qwen3:8b'] : [],
          error: state.reachable ? null : { type: 'ConnectError', message: 'connection refused' },
        },
        config_error: null,
      });
    }

    if (path === '/runtime/models/active' && method === 'GET') {
      return okJson({
        active_profile: state.activeProfile,
        profile_source: state.source,
        resolved_models: profiles[state.activeProfile],
        role_aliases: { default: 'chat' },
        availability,
        ollama: {
          reachable: state.reachable,
          base_url: 'http://ollama:11434',
          models: state.reachable ? ['qwen3:8b'] : [],
          error: state.reachable ? null : { type: 'ConnectError', message: 'connection refused' },
        },
        config_error: null,
      });
    }

    if (path === '/runtime/models/effective' && method === 'GET') {
      return okJson({
        active_profile: state.activeProfile,
        profile_source: state.source,
        effective_models: profiles[state.activeProfile],
        role_aliases: { default: 'chat' },
        config_error: null,
      });
    }

    if (path === '/api/runtime/models/active' && method === 'PUT') {
      const body = JSON.parse(init.body || '{}');
      state.activeProfile = body.profile;
      state.source = 'runtime_override';
      return okJson({
        active_profile: state.activeProfile,
        profile_source: state.source,
        resolved_models: profiles[state.activeProfile],
        role_aliases: { default: 'chat' },
        availability,
        ollama: {
          reachable: state.reachable,
          base_url: 'http://ollama:11434',
          models: state.reachable ? ['qwen3:8b'] : [],
          error: state.reachable ? null : { type: 'ConnectError', message: 'connection refused' },
        },
        config_error: null,
      });
    }

    if (path === '/api/runtime/models/active' && method === 'DELETE') {
      state.activeProfile = 'balanced';
      state.source = 'env';
      return okJson({
        active_profile: state.activeProfile,
        profile_source: state.source,
        resolved_models: profiles[state.activeProfile],
        role_aliases: { default: 'chat' },
        availability,
        ollama: {
          reachable: state.reachable,
          base_url: 'http://ollama:11434',
          models: state.reachable ? ['qwen3:8b'] : [],
          error: state.reachable ? null : { type: 'ConnectError', message: 'connection refused' },
        },
        config_error: null,
      });
    }

    if (path === '/api/sessions' && method === 'POST') {
      return okJson({ session_id: 'session-1', current_persona: 'default', metadata: {}, messages: [] });
    }

    if (path === '/api/operator/commands' && method === 'GET') {
      const operatorMode = query.get('operator_mode') === 'true';
      return okJson({
        operator_mode: operatorMode,
        commands: [
          { slash: '/scan-repo', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/scan-system', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/scan-cpu', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/scan-gpu', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/scan-disk', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/scan-ports', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/list-disks', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/list-drives', category: 'read_only_scan', mode: 'read_only', risk_level: 'low', visible: true, enabled: true },
          { slash: '/delete-file', category: 'mutation', mode: 'operator', risk_level: 'destructive', visible: operatorMode, enabled: operatorMode },
          { slash: '/write-file', category: 'mutation', mode: 'operator', risk_level: 'medium', visible: operatorMode, enabled: operatorMode },
          { slash: '/format-drive', category: 'high_risk', mode: 'operator', risk_level: 'high', visible: operatorMode, enabled: operatorMode, requires_typed_confirmation: true },
        ],
      });
    }

    if (path === '/api/operator/stage' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      const command = String(body.command_text || '');
      const operatorMode = Boolean(body.operator_mode);
      if (!operatorMode && command.startsWith('/delete-file')) {
        return okJson({
          session_id: 'session-1',
          answer: 'Operator Mode is OFF. This mutation command is blocked until Operator Mode is enabled.',
          executed: false,
          pending_action: null,
          receipt: {
            action_id: 'OP-DENY',
            action_name: 'delete_file',
            status: 'denied',
            mode: 'operator',
            target: '/workspace',
            receipt_label: 'delete_file OP-DENY',
            read_only: false,
            summary: 'denied',
          },
        });
      }

      if (command.startsWith('/delete-file')) {
        pendingAction = {
          action_id: 'OP-PEND-1',
          command_name: 'delete-file',
          target: 'X:/XV7/test-delete.txt',
          command_preview: command,
          risk_level: 'destructive',
          reversible: false,
          requires_typed_confirmation: false,
        };
        state.pendingAction = pendingAction;
        return okJson({
          session_id: 'session-1',
          answer: "I'm ready to perform this operator action, but I need confirmation first.",
          executed: false,
          pending_action: pendingAction,
          receipt: {
            action_id: 'OP-PEND-1',
            action_name: 'delete_file',
            status: 'pending',
            mode: 'operator',
            target: 'X:/XV7/test-delete.txt',
            receipt_label: 'delete_file OP-PEND-1',
            read_only: false,
            summary: 'pending confirmation',
          },
        });
      }

      if (command.startsWith('/format-drive')) {
        pendingAction = {
          action_id: 'OP-PEND-HIGH',
          command_name: 'format-drive',
          target: 'E:',
          command_preview: command,
          risk_level: 'high',
          reversible: false,
          requires_typed_confirmation: true,
          confirmation_phrase: 'FORMAT E:',
        };
        state.pendingAction = pendingAction;
        return okJson({
          session_id: 'session-1',
          answer: "I'm ready to perform this operator action, but I need confirmation first.",
          executed: false,
          pending_action: pendingAction,
          receipt: {
            action_id: 'OP-PEND-HIGH',
            action_name: 'format_drive',
            status: 'pending',
            mode: 'high_risk',
            target: 'E:',
            receipt_label: 'format_drive OP-PEND-HIGH',
            read_only: false,
            summary: 'pending confirmation',
          },
        });
      }
    }

    if (path === '/api/operator/confirm' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      const typed = String(body.typed_confirmation || '');
      if (state.pendingAction?.action_id === 'OP-PEND-HIGH' && typed !== 'FORMAT E:') {
        return okJson({
          session_id: 'session-1',
          answer: 'Typed confirmation did not match. Action is still blocked.',
          pending_action: state.pendingAction,
          receipt: {
            action_id: 'OP-PEND-HIGH',
            action_name: 'format_drive',
            status: 'failed',
            mode: 'high_risk',
            target: 'E:',
            receipt_label: 'format_drive OP-PEND-HIGH',
            read_only: false,
            summary: 'Typed confirmation did not match.',
          },
        });
      }

      const actionName = state.pendingAction?.action_id === 'OP-PEND-HIGH' ? 'format_drive' : 'delete_file';
      const status = state.pendingAction?.action_id === 'OP-PEND-HIGH' ? 'not_implemented' : 'success';
      const target = state.pendingAction?.target || 'unknown';
      state.pendingAction = null;

      return okJson({
        session_id: 'session-1',
        answer: status === 'success' ? 'Operator action delete_file executed successfully.' : 'Action not implemented yet.',
        pending_action: null,
        receipt: {
          action_id: body.action_id,
          action_name: actionName,
          status,
          mode: actionName === 'format_drive' ? 'high_risk' : 'operator',
          target,
          receipt_label: `${actionName} ${body.action_id}`,
          read_only: false,
          summary: status,
        },
      });
    }

    if (path === '/api/operator/cancel' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      const target = state.pendingAction?.target || 'unknown';
      state.pendingAction = null;
      return okJson({
        session_id: 'session-1',
        answer: 'Pending operator action was cancelled.',
        pending_action: null,
        receipt: {
          action_id: body.action_id,
          action_name: 'delete_file',
          status: 'cancelled',
          mode: 'operator',
          target,
          receipt_label: `delete_file ${body.action_id}`,
          read_only: false,
          summary: 'cancelled',
        },
      });
    }

    if (path === '/runtime/brain/records' && method === 'GET') {
      const layer = String(query.get('layer') || '');
      const pendingOnly = query.get('pending_only') === 'true';
      const learnedOnly = query.get('learned_only') === 'true';
      const relevance = String(query.get('relevance') || '');
      const historyOnly = query.get('history_only') === 'true';
      const reviewOnly = query.get('review_only') === 'true';
      const records = state.brainRecords.filter((item) => {
        if (layer && item.layer !== layer) return false;
        if (pendingOnly && !['pending_review', 'pending'].includes(item.status)) return false;
        if (learnedOnly && !item.tags.includes('learned-rule')) return false;
        if (relevance && String(item.effective_relevance_state || item.relevance_state || '') !== relevance) return false;
        if (historyOnly) {
          const rs = String(item.relevance_state || '');
          const re = String(item.effective_relevance_state || rs || '');
          if (!['historical', 'superseded', 'expired'].includes(rs) && !['historical', 'superseded', 'expired'].includes(re)) return false;
        }
        if (reviewOnly) {
          const rs = String(item.relevance_state || '');
          const r = String(item.effective_relevance_state || rs || '');
          const s = String(item.status_label || item.status || '');
          const flags = new Set((Array.isArray(item.hygiene_flags) ? item.hygiene_flags : []).map((flag) => String(flag).toLowerCase()));
          const hasRec = Array.isArray(item.hygiene_recommendations) && item.hygiene_recommendations.length > 0;
          const hasFlag = (
            flags.has('old_phase_reference')
            || flags.has('completed_milestone')
            || flags.has('mixed_historical_and_current')
            || flags.has('mixed_historical_and_operational')
          );
          if (!(r === 'needs_review' || rs === 'needs_review' || s === 'pending' || s === 'pending_review' || hasRec || hasFlag)) return false;
        }
        return true;
      });
      return okJson({ count: records.length, records });
    }

    if (path === '/runtime/context/active' && method === 'GET') {
      const focusId = String(state.activeContextFocusId || '');
      const focusSummary = String(state.activeContextFocusSummary || '').trim();
      const recordIds = [...state.activeContextRecordIds];
      if (focusId && !recordIds.includes(focusId)) {
        recordIds.push(focusId);
      }
      return okJson({
        prompt: '',
        compact_receipt: focusSummary,
        receipt: {
          record_ids: recordIds,
          context_receipts: focusId
            ? [
              {
                layer: 'active_focus',
                record_id: focusId,
                summary: focusSummary,
              },
            ]
            : [],
        },
      });
    }

    if (path.startsWith('/runtime/brain/records/') && method === 'PUT') {
      const recordId = decodeURIComponent(path.split('/').at(-1) || '');
      const body = JSON.parse(init.body || '{}');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.layer = body.layer || current.layer;
      current.title = body.title || current.title;
      current.body = body.body || current.body;
      current.summary = String(current.body || '').slice(0, 160);
      current.tags = Array.isArray(body.tags) ? body.tags : current.tags;
      current.status = body.status || current.status;
      current.status_label = current.status === 'pending_review' ? 'pending' : current.status;
      if (body.relevance_state) {
        current.relevance_state = body.relevance_state;
        current.effective_relevance_state = body.relevance_state;
      }
      current.raw_record = {
        ...current.raw_record,
        layer: current.layer,
        title: current.title,
        body: current.body,
        summary: current.summary,
        tags: current.tags,
        status: current.status,
      };
      return okJson(current);
    }

    if (path.endsWith('/deactivate') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.status = 'archived';
      current.status_label = 'disabled';
      current.relevance_state = 'historical';
      current.effective_relevance_state = 'historical';
      current.raw_record = { ...current.raw_record, status: 'archived' };
      return okJson(current);
    }

    if (path.endsWith('/set-active') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      state.brainRecords.forEach((item) => {
        if (item.layer === 'active_focus') {
          item.status = item.record_id === recordId ? 'active' : 'archived';
          item.status_label = item.status;
          item.relevance_state = item.record_id === recordId ? 'current' : 'superseded';
          item.effective_relevance_state = item.relevance_state;
          item.raw_record = { ...item.raw_record, status: item.status };
        }
      });
      const updated = state.brainRecords.find((item) => item.record_id === recordId);
      if (!updated) return errorText(404, 'Record not found');
      return okJson(updated);
    }

    if (path.endsWith('/approve') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.status = 'active';
      current.status_label = 'active';
      current.relevance_state = 'current';
      current.effective_relevance_state = 'current';
      current.raw_record = { ...current.raw_record, status: 'active' };
      return okJson(current);
    }

    if (path.endsWith('/reject') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.status = 'archived';
      current.status_label = 'archived';
      current.relevance_state = 'historical';
      current.effective_relevance_state = 'historical';
      current.raw_record = { ...current.raw_record, status: 'archived' };
      return okJson(current);
    }

    if (path.endsWith('/mark-current') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.status = 'active';
      current.status_label = 'active';
      current.relevance_state = 'current';
      current.effective_relevance_state = 'current';
      return okJson(current);
    }

    if (path.endsWith('/mark-historical') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.relevance_state = 'historical';
      current.effective_relevance_state = 'historical';
      return okJson(current);
    }

    if (path.endsWith('/mark-superseded') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.status = 'disabled';
      current.status_label = 'disabled';
      current.relevance_state = 'superseded';
      current.effective_relevance_state = 'superseded';
      return okJson(current);
    }

    if (path.endsWith('/apply-recommendation') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      const body = JSON.parse(init.body || '{}');
      if (String(body.recommendation_type || '') === 'split_record') {
        current.relevance_state = 'historical';
        current.effective_relevance_state = 'historical';
        current.hygiene_recommendations = [];
        const created = {
          ...current,
          record_id: 'XV7-KNOWLEDGE-0998',
          layer: 'knowledge',
          title: 'Operational: Bridge status rule',
          status: 'active',
          status_label: 'active',
          relevance_state: 'current',
          effective_relevance_state: 'current',
          hygiene_flags: [],
          hygiene_recommendations: [],
        };
        state.brainRecords.push(created);
        return okJson({ record: current, created_record: created, applied: true, recommendation_type: 'split_record' });
      }
      current.relevance_state = 'historical';
      current.effective_relevance_state = 'historical';
      return okJson({ record: current, applied: true, recommendation_type: 'mark_historical_via_runtime_override' });
    }

    if (path.endsWith('/split') && method === 'POST') {
      const recordId = decodeURIComponent(path.split('/').at(-2) || '');
      const current = state.brainRecords.find((item) => item.record_id === recordId);
      if (!current) return errorText(404, 'Record not found');
      current.relevance_state = 'historical';
      current.effective_relevance_state = 'historical';
      const created = {
        ...current,
        record_id: 'XV7-KNOWLEDGE-0999',
        title: `Operational: ${current.title}`,
        status: 'active',
        status_label: 'active',
        relevance_state: 'current',
        effective_relevance_state: 'current',
      };
      state.brainRecords.push(created);
      return okJson({ applied: true, source_record: current, created_record: created });
    }

    if (path === '/api/sessions/session-1/messages' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      const prompt = String(body.raw_text || '').toLowerCase();
      let operatorReceipts = [];
      let answer = 'XV7_MODEL_PROOF';
      let actionHistory = [];
      let contextReceipt = { compact: 'Context receipt: Verified Status XV7-VERIFIED-0001.' };
      let memoryReceipts = [];

      if (prompt.includes('check the repo')) {
        operatorReceipts = [
          {
            action_id: 'OP-1',
            action_name: 'repo_status',
            status: 'success',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'repo_status OP-1',
            read_only: true,
            started_at: '2026-06-11T00:00:00Z',
            completed_at: '2026-06-11T00:00:01Z',
            exit_code: 0,
            safety: { allowed: true, read_only: true },
            summary: 'repo checked',
            limitation: '',
            data_preview: { branch: 'main' },
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'The repo is on main. The working tree is not clean.';
      } else if (prompt.includes('run validation')) {
        operatorReceipts = [
          {
            action_id: 'OP-VAL-1',
            action_name: 'operator_validation_report',
            status: 'success',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'operator_validation_report OP-VAL-1',
            read_only: true,
            started_at: '2026-06-11T00:01:00Z',
            completed_at: '2026-06-11T00:01:02Z',
            exit_code: 0,
            safety: { allowed: true, read_only: true },
            summary: 'validation passed',
            limitation: '',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'Validation passed.';
      } else if (prompt === 'fix it') {
        operatorReceipts = [
          {
            action_id: 'OP-REP-1',
            action_name: 'operator_repair_report',
            status: 'failed',
            mode: 'operator',
            target: '/workspace',
            receipt_label: 'operator_repair_report OP-REP-1',
            read_only: false,
            started_at: '2026-06-11T00:02:00Z',
            completed_at: '2026-06-11T00:02:03Z',
            exit_code: 1,
            safety: { allowed: true, read_only: false },
            summary: 'patch required',
            limitation: '',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'A concrete approved patch is required.';
      } else if (prompt.includes('apply this patch')) {
        operatorReceipts = [
          {
            action_id: 'OP-PATCH-1',
            action_name: 'operator_patch_report',
            status: 'denied',
            mode: 'operator',
            target: '/workspace',
            receipt_label: 'operator_patch_report OP-PATCH-1',
            read_only: false,
            started_at: '2026-06-11T00:03:00Z',
            completed_at: '2026-06-11T00:03:01Z',
            exit_code: 1,
            safety: { allowed: false, read_only: false },
            summary: 'approval required',
            limitation: '',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'Patch apply denied: repo mutation approval is required.';
      } else if (prompt.includes('containers')) {
        operatorReceipts = [
          {
            action_id: 'OP-2',
            action_name: 'scan_docker',
            status: 'failed',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'scan_docker OP-2',
            read_only: true,
            started_at: '2026-06-11T00:00:02Z',
            completed_at: '2026-06-11T00:00:03Z',
            exit_code: 127,
            safety: { allowed: true, read_only: true },
            summary: 'unavailable',
            limitation: 'Container status cannot be proven.',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'Container status cannot be proven from inside xv7-core.';
      } else if (prompt.includes('processor')) {
        operatorReceipts = [
          {
            action_id: 'OP-CPU-1',
            action_name: 'scan_cpu',
            status: 'failed',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'scan_cpu OP-CPU-1',
            read_only: true,
            started_at: '2026-06-11T00:00:02Z',
            completed_at: '2026-06-11T00:00:03Z',
            exit_code: 503,
            safety: { allowed: true, read_only: true },
            summary: 'Local host scan bridge is not running.',
            limitation: 'Local host scan bridge is not running.',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'I can check that through the local host scan bridge, but the bridge is not running yet.';
      } else if (prompt.includes('delete')) {
        operatorReceipts = [
          {
            action_id: 'OP-3',
            action_name: 'read_only_guard',
            status: 'denied',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'read_only_guard OP-3',
            read_only: true,
            started_at: '2026-06-11T00:00:04Z',
            completed_at: '2026-06-11T00:00:04Z',
            exit_code: null,
            safety: { allowed: false, read_only: true },
            summary: 'denied mutation',
            limitation: '',
            data_preview: {},
          },
        ];
        actionHistory = operatorReceipts;
        answer = 'B7 is read-only right now. I denied that request.';
      } else if (prompt.includes('what is your name')) {
        answer = 'My name is Xoduz.';
        contextReceipt = {
          compact: 'Context receipt: System Prompt XV7-SYSTEM-0001.',
          context_receipts: [
            {
              record_id: 'XV7-SYSTEM-0001',
              layer: 'system_prompt',
              title: 'Xoduz identity and behavior rules',
              receipt_label: 'System Prompt XV7-SYSTEM-0001',
            },
          ],
        };
      } else if (prompt.includes('who are you')) {
        answer = 'I am Xoduz, the XV7 assistant.';
        contextReceipt = {
          compact: 'Context receipt: System Prompt XV7-SYSTEM-0001.',
          context_receipts: [
            {
              record_id: 'XV7-SYSTEM-0001',
              layer: 'system_prompt',
              title: 'Xoduz identity and behavior rules',
              receipt_label: 'System Prompt XV7-SYSTEM-0001',
            },
          ],
        };
      } else if (prompt.includes('what are we working on right now')) {
        answer = 'Current focus is B8.2 brain content fill and communication routing repair after B8 chat-first UI polish.';
        contextReceipt = {
          compact: 'Context receipt: Active Focus XV7-FOCUS-0003.',
          context_receipts: [
            {
              record_id: 'XV7-FOCUS-0003',
              layer: 'active_focus',
              title: 'B8.2 brain content and communication routing repair',
              receipt_label: 'Active Focus XV7-FOCUS-0003',
            },
          ],
        };
      } else if (prompt.includes('implementation prompts')) {
        answer = 'Yes. I can help write precise VS Code/Copilot implementation prompts and acceptance checks.';
        contextReceipt = {
          compact: 'Context receipt: Knowledge XV7-KNOWLEDGE-0002.',
          context_receipts: [
            {
              record_id: 'XV7-KNOWLEDGE-0002',
              layer: 'knowledge',
              title: 'XV7 capability, operator boundary, and UI self-knowledge',
              receipt_label: 'Knowledge XV7-KNOWLEDGE-0002',
            },
          ],
        };
      } else if (prompt.includes('what do you know is verified')) {
        answer = 'Verified facts: runtime and launch checks are passing.';
        contextReceipt = {
          compact: 'Context receipt: Verified Status XV7-VERIFIED-0001.',
          context_receipts: [
            {
              record_id: 'XV7-VERIFIED-0001',
              layer: 'verified_status',
              title: 'B3.2 proven operational status',
              receipt_label: 'Verified Status XV7-VERIFIED-0001',
            },
          ],
        };
      } else if (prompt.includes('remember')) {
        answer = 'Saved that preference as active memory.';
        memoryReceipts = ['Memory receipt: XV7-MEMORY-0002 active.'];
        contextReceipt = { compact: 'Context receipt: Memory XV7-MEMORY-0002.' };
      }

      return okJson({
        session_id: 'session-1',
        current_persona: 'default',
        metadata: {
          operator_action_history: actionHistory,
          model_use_receipt: {
            model_profile: state.activeProfile,
            profile_source: state.source,
            runtime_role: 'chat',
            model_tag: profiles[state.activeProfile].chat,
            model_selection_source: 'registry_effective_profile',
            request_id: 'req-1',
          },
        },
        messages: [
          { role: 'user', content: 'x' },
          {
            role: 'assistant',
            content: answer,
            metadata: {
              visible_text: answer,
              context_receipt: contextReceipt,
              operator_receipts: operatorReceipts,
              operator_result: (() => {
                if (prompt.includes('check the repo')) {
                  return {
                    action_name: 'operator_status_report',
                    status: 'passed',
                    changed_files: ['core/main.py', 'public/app.js'],
                    validation_commands_run: [],
                    first_failure: '',
                    safety_notes: ['No git commit or push was performed.'],
                    commit_push_state: {
                      commit_created: false,
                      push_performed: false,
                      requires_separate_approval: true,
                    },
                    local_only_files_warning: ['docker-compose.yml', 'docker-compose.local.diff'],
                  };
                }
                if (prompt.includes('run validation')) {
                  return {
                    action_name: 'operator_validation_report',
                    status: 'passed',
                    changed_files: [],
                    validation_commands_run: [
                      'python -m ruff format --check core tests scripts',
                      'python -m ruff check core tests scripts',
                    ],
                    first_failure: '',
                    safety_notes: ['No git commit or push was performed.'],
                    commit_push_state: {
                      commit_created: false,
                      push_performed: false,
                      requires_separate_approval: true,
                    },
                    local_only_files_warning: [],
                  };
                }
                if (prompt === 'fix it') {
                  return {
                    action_name: 'operator_repair_report',
                    status: 'needs_patch',
                    changed_files: [],
                    validation_commands_run: ['python -m pytest'],
                    first_failure: 'python -m pytest',
                    safety_notes: ['A concrete approved patch is required.'],
                    commit_push_state: {
                      commit_created: false,
                      push_performed: false,
                      requires_separate_approval: true,
                    },
                    local_only_files_warning: [],
                  };
                }
                if (prompt.includes('apply this patch')) {
                  return {
                    action_name: 'operator_patch_report',
                    status: 'needs_approval',
                    changed_files: [],
                    validation_commands_run: [],
                    first_failure: '',
                    safety_notes: ['Repo mutation requires explicit approval.'],
                    commit_push_state: {
                      commit_created: false,
                      push_performed: false,
                      requires_separate_approval: true,
                    },
                    local_only_files_warning: [],
                  };
                }
                return {};
              })(),
              memory_receipts: memoryReceipts,
              model_use_receipt: {
                model_tag: profiles[state.activeProfile].chat,
              },
              policy_provenance: { policy_source: 'operator_manager' },
              warnings: [],
              action_history_refs: operatorReceipts.map((item) => item.action_id),
            },
          },
        ],
      });
    }

    return errorText(404, `${method} ${path} not mocked`);
  });
}

export async function flushAsync() {
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await Promise.resolve();
}

export function buildSpeechSynthesisMock(voices = []) {
  return {
    speak: vi.fn(),
    cancel: vi.fn(),
    getVoices: vi.fn(() => voices),
    onvoiceschanged: null,
  };
}
