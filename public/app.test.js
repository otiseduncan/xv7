// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Xv7UI } from './app.js';

function okJson(payload) {
  return {
    ok: true,
    status: 200,
    async json() { return payload; },
    async text() { return JSON.stringify(payload); },
  };
}

function errorText(status, message) {
  return {
    ok: false,
    status,
    async json() { return { detail: message }; },
    async text() { return message; },
  };
}

function buildDom() {
  document.body.innerHTML = `
    <select id="personaSelect"></select>
    <p id="personaHint"></p>
    <span id="sessionIdValue"></span>
    <span id="memoryCountValue"></span>
    <span id="hardwareLoadValue"></span>
    <div id="hardwareLoadBar"></div>
    <section id="alertBox" class="hidden"></section>
    <ul id="retrievalJournal"></ul>
    <button id="copyChatButton"></button>
    <div id="copyToast" class="hidden"></div>
    <div id="chatTimeline"></div>
    <button id="operatorModeToggle"></button>
    <div id="operatorModeBanner" class="hidden"></div>
    <div id="operatorConfirmArea" class="hidden"></div>
    <textarea id="promptInput"></textarea>
    <div id="slashMenu" class="hidden"></div>
    <button id="micButton"></button>
    <button id="sendButton"></button>
    <section id="avatarCard" class="avatar-card">
      <button id="avatarToggleButton" aria-expanded="true"></button>
      <div id="avatarCardBody"></div>
      <div id="avatarShell"></div>
      <video id="avatarVideo"></video>
      <div id="avatarFallback"></div>
      <p id="avatarStateText"></p>
      <p id="avatarVoiceLabel"></p>
    </section>
    <div id="voiceStatus"></div>
    <p id="voiceSettingsStatus"></p>
    <select id="voiceSelect"></select>
    <input id="voiceVolume" type="range" />
    <input id="sidebarVoiceVolume" type="range" />
    <span id="sidebarVoiceVolumeValue"></span>
    <input id="voiceRate" type="range" />
    <input id="voicePitch" type="range" />
    <input id="voiceMute" type="checkbox" />
    <button id="sidebarVoiceMuteButton"></button>
    <span id="sidebarVoiceMuteIconOn"></span>
    <span id="sidebarVoiceMuteIconOff"></span>
    <span id="sidebarVoiceMuteLabel"></span>
    <span id="sidebarVoiceMuteState"></span>
    <button id="voiceTestButton"></button>
    <button id="voiceStopButton"></button>
    <span id="avatarDiagState"></span>
    <span id="avatarDiagClip"></span>
    <span id="avatarDiagLoaded"></span>
    <span id="avatarDiagVisible"></span>
    <span id="avatarDiagEvent"></span>
    <span id="voiceDiagInput"></span>
    <span id="voiceDiagMicState"></span>
    <span id="voiceDiagOutput"></span>
    <span id="voiceDiagSpeaking"></span>
    <span id="voiceDiagVoiceCount"></span>
    <span id="voiceDiagSelected"></span>
    <span id="voiceDiagVolume"></span>
    <span id="voiceDiagRate"></span>
    <span id="voiceDiagPitch"></span>
    <span id="modelActiveProfile"></span>
    <span id="modelProfileSource"></span>
    <span id="modelOllamaReachable"></span>
    <span id="modelEffectiveChat"></span>
    <select id="modelProfileSelect"></select>
    <button id="modelApplyButton"></button>
    <button id="modelClearButton"></button>
    <span id="modelResolvedChat"></span>
    <span id="modelResolvedReasoning"></span>
    <span id="modelResolvedCode"></span>
    <span id="modelResolvedEmbedding"></span>
    <span id="modelAvailabilityChat"></span>
    <span id="modelAvailabilityReasoning"></span>
    <span id="modelAvailabilityCode"></span>
    <span id="modelAvailabilityEmbedding"></span>
    <p id="modelPanelStatus"></p>
    <span id="chatReceiptProfile"></span>
    <span id="chatReceiptSource"></span>
    <span id="chatReceiptRole"></span>
    <span id="chatReceiptModelTag"></span>
    <span id="chatReceiptSelectionSource"></span>
    <span id="chatReceiptRequestId"></span>
    <ul id="operatorActivityList"></ul>
    <span id="statusCoreApi"></span>
    <span id="statusRuntimeHealth"></span>
    <span id="statusActiveProfile"></span>
    <span id="statusOperatorMode"></span>
    <span id="statusMemory"></span>
    <span id="statusLastAction"></span>
    <span id="statusLastChecked"></span>
    <span id="statusCoreApiChip"></span>
    <span id="statusRuntimeHealthChip"></span>
    <span id="statusActiveProfileChip"></span>
    <span id="statusOperatorModeChip"></span>
    <span id="statusLastCheckedChip"></span>
    <div id="operatorSummaryChip" class="hidden"></div>
    <aside id="diagnosticsDrawer"></aside>
    <div id="diagnosticsBackdrop" class="hidden"></div>
    <button id="diagnosticsToggleButton"></button>
    <button id="diagnosticsCloseButton"></button>
    <p id="brainRecordsStatus"></p>
    <div id="brainRecordsViews">
      <button data-view="now"></button>
      <button data-view="review"></button>
      <button data-view="history"></button>
      <button data-view="library"></button>
    </div>
    <p id="brainNowCounts"></p>
    <div id="brainReviewToolbar" class="hidden">
      <button id="brainRecordsApplyCleanupButton"></button>
    </div>
    <p id="brainNowFocus"></p>
    <p id="brainNowSelectedRecords"></p>
    <p id="brainNowAnswerMeta"></p>
    <div id="brainLibraryControls" class="hidden"></div>
    <select id="brainLibraryLayerFilter">
      <option value="all">all</option>
      <option value="active_focus">active_focus</option>
      <option value="memory">memory</option>
      <option value="knowledge">knowledge</option>
      <option value="verified_status">verified_status</option>
      <option value="system_prompt">system_prompt</option>
    </select>
    <select id="brainLibraryStatusFilter">
      <option value="active">active</option>
      <option value="pending">pending</option>
      <option value="disabled">disabled</option>
      <option value="archived">archived</option>
      <option value="all">all</option>
    </select>
    <select id="brainLibraryRelevanceFilter">
      <option value="all">all</option>
      <option value="current">current</option>
      <option value="needs_review">needs_review</option>
      <option value="historical">historical</option>
      <option value="superseded">superseded</option>
      <option value="expired">expired</option>
    </select>
    <select id="brainLibrarySourceFilter">
      <option value="all">all</option>
      <option value="runtime">runtime</option>
      <option value="seed">seed</option>
    </select>
    <input id="brainLibrarySearch" />
    <input id="brainLibraryShowArchived" type="checkbox" />
    <input id="brainLibraryShowRawJson" type="checkbox" />
    <ul id="brainRecordsList"></ul>
    <div id="brainRecordEditor" class="hidden"></div>
    <span id="brainRecordEditorId"></span>
    <select id="brainRecordEditorLayer"></select>
    <input id="brainRecordEditorTitle" />
    <textarea id="brainRecordEditorBody"></textarea>
    <input id="brainRecordEditorTags" />
    <select id="brainRecordEditorStatus"></select>
    <button id="brainRecordEditorSaveButton"></button>
    <button id="brainRecordEditorCancelButton"></button>
    <textarea id="brainRecordEditorRaw"></textarea>
  `;
}

function createRuntimeFetchMock(options = {}) {
  const state = {
    activeProfile: options.activeProfile || 'balanced',
    source: options.source || 'env',
    reachable: options.reachable ?? true,
    failModels: options.failModels ?? false,
    brainRecords: [
      {
        record_id: 'XV7-FOCUS-0005',
        layer: 'active_focus',
        title: 'Communication-first continuity',
        summary: 'Keep communication continuity and avoid fallback drift.',
        body: 'Focus on communication continuity and deterministic routing.',
        status: 'active',
        status_label: 'active',
        relevance_state: 'current',
        effective_relevance_state: 'current',
        priority: 300,
        tags: ['focus', 'communication'],
        source: 'runtime_override',
        writable: true,
        updated_at: '2026-06-11T00:00:00Z',
        raw_record: {
          record_id: 'XV7-FOCUS-0005',
          layer: 'active_focus',
          title: 'Communication-first continuity',
          summary: 'Keep communication continuity and avoid fallback drift.',
          body: 'Focus on communication continuity and deterministic routing.',
          status: 'active',
          priority: 300,
          tags: ['focus', 'communication'],
        },
      },
      {
        record_id: 'XV7-SYSTEM-0001',
        layer: 'system_prompt',
        title: 'Identity baseline',
        summary: 'System identity and answer contract.',
        body: 'Core system prompt baseline.',
        status: 'active',
        status_label: 'active',
        relevance_state: 'current',
        effective_relevance_state: 'current',
        priority: 320,
        tags: ['seed'],
        source: 'seed',
        writable: false,
        updated_at: '2026-06-11T00:00:05Z',
        raw_record: {
          record_id: 'XV7-SYSTEM-0001',
          layer: 'system_prompt',
          title: 'Identity baseline',
          summary: 'System identity and answer contract.',
          body: 'Core system prompt baseline.',
          status: 'active',
          priority: 320,
          tags: ['seed'],
        },
      },
      {
        record_id: 'XV7-MEMORY-0002',
        layer: 'memory',
        title: 'Communication preference',
        summary: 'Keep status answers concise unless debug requested.',
        body: 'Active memory preference.',
        status: 'active',
        status_label: 'active',
        relevance_state: 'current',
        effective_relevance_state: 'current',
        priority: 240,
        tags: ['runtime', 'learned-rule'],
        source: 'runtime_override',
        writable: true,
        updated_at: '2026-06-11T00:00:06Z',
        raw_record: {
          record_id: 'XV7-MEMORY-0002',
          layer: 'memory',
          title: 'Communication preference',
          summary: 'Keep status answers concise unless debug requested.',
          body: 'Active memory preference.',
          status: 'active',
          priority: 240,
          tags: ['runtime', 'learned-rule'],
        },
      },
      {
        record_id: 'XV7-VERIFIED-0001',
        layer: 'verified_status',
        title: 'Verified milestones and current phase status',
        summary: 'Verified: B9.5 and B9.7 passed; current in progress: B9.8 local bridge hardening.',
        body: 'Proven: B3.2 passed, B9.5 passed, B9.7 passed. Current in progress: B9.8 local bridge behavior.',
        status: 'active',
        status_label: 'active',
        relevance_state: 'current',
        effective_relevance_state: 'needs_review',
        hygiene_reason: 'Contains old completed milestones and current operational bridge rule content.',
        hygiene_flags: ['old_phase_reference', 'completed_milestone', 'mixed_historical_and_current'],
        hygiene_recommendations: [
          { type: 'split_record', record_id: 'XV7-VERIFIED-0001' },
          { type: 'mark_historical_via_runtime_override', record_id: 'XV7-VERIFIED-0001' },
        ],
        priority: 210,
        tags: ['seed'],
        source: 'seed',
        writable: false,
        updated_at: '2026-06-11T00:00:08Z',
        raw_record: {
          record_id: 'XV7-VERIFIED-0001',
          layer: 'verified_status',
          title: 'Verified milestones and current phase status',
          summary: 'Verified: B9.5 and B9.7 passed; current in progress: B9.8 local bridge hardening.',
          body: 'Proven: B3.2 passed, B9.5 passed, B9.7 passed. Current in progress: B9.8 local bridge behavior.',
          status: 'active',
          priority: 210,
          tags: ['seed'],
        },
      },
      {
        record_id: 'XV7-KNOWLEDGE-0007',
        layer: 'knowledge',
        title: 'Require proof before CI claims',
        summary: 'When asked about CI status, require GitHub Actions proof before claiming state.',
        body: 'Learned diagnostic rule: verify Actions before claiming CI status.',
        status: 'pending_review',
        status_label: 'pending',
        relevance_state: 'needs_review',
        effective_relevance_state: 'needs_review',
        priority: 180,
        tags: ['learned-rule', 'proof-required', 'diagnostic-rule'],
        source: 'runtime_override',
        writable: true,
        updated_at: '2026-06-11T00:00:10Z',
        raw_record: {
          record_id: 'XV7-KNOWLEDGE-0007',
          layer: 'knowledge',
          title: 'Require proof before CI claims',
          summary: 'When asked about CI status, require GitHub Actions proof before claiming state.',
          body: 'Learned diagnostic rule: verify Actions before claiming CI status.',
          status: 'pending_review',
          priority: 180,
          tags: ['learned-rule', 'proof-required', 'diagnostic-rule'],
        },
      },
      {
        record_id: 'XV7-KNOWLEDGE-0003',
        layer: 'knowledge',
        title: 'Legacy archived seed',
        summary: 'Historical archived seed record.',
        body: 'Old seed record.',
        status: 'archived',
        status_label: 'archived',
        relevance_state: 'historical',
        effective_relevance_state: 'historical',
        priority: 90,
        tags: ['seed'],
        source: 'seed',
        writable: false,
        updated_at: '2026-06-11T00:00:11Z',
        raw_record: {
          record_id: 'XV7-KNOWLEDGE-0003',
          layer: 'knowledge',
          title: 'Legacy archived seed',
          summary: 'Historical archived seed record.',
          body: 'Old seed record.',
          status: 'archived',
          priority: 90,
          tags: ['seed'],
        },
      },
    ],
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

async function flushAsync() {
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await Promise.resolve();
}

function buildSpeechSynthesisMock(voices = []) {
  return {
    speak: vi.fn(),
    cancel: vi.fn(),
    getVoices: vi.fn(() => voices),
    onvoiceschanged: null,
  };
}

describe('ModelProfileControl', () => {
  beforeEach(() => {
    buildDom();
    if (!HTMLMediaElement.prototype.play || !('mock' in HTMLMediaElement.prototype.play)) {
      Object.defineProperty(HTMLMediaElement.prototype, 'play', {
        configurable: true,
        value: vi.fn().mockResolvedValue(undefined),
      });
    }
    if (!HTMLMediaElement.prototype.load || !('mock' in HTMLMediaElement.prototype.load)) {
      Object.defineProperty(HTMLMediaElement.prototype, 'load', {
        configurable: true,
        value: vi.fn(),
      });
    }
    window.__XV7_DISABLE_AUTO_INIT = true;
    navigator.clipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    window.SpeechRecognition = undefined;
    window.webkitSpeechRecognition = undefined;
    window.speechSynthesis = undefined;
    window.SpeechSynthesisUtterance = undefined;
    window.localStorage.clear();
  });

  it('renders active profile and available profiles', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('modelActiveProfile').textContent).toBe('balanced');
    expect(document.getElementById('modelEffectiveChat').textContent).toBe('qwen3:8b');

    const optionValues = [...document.querySelectorAll('#modelProfileSelect option')].map((item) => item.value);
    expect(optionValues).toEqual(['low_resource', 'balanced', 'local_test', 'large_code']);
  });

  it('does not render an API key input in normal UI', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('modelApiKeyInput')).toBe(null);
    const pageText = document.body.textContent || '';
    expect(pageText.toLowerCase().includes('api key')).toBe(false);
    expect(pageText.toLowerCase().includes('enter api key')).toBe(false);
  });

  it('apply action sends PUT /api/runtime/models/active via proxy path', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const select = document.getElementById('modelProfileSelect');
    select.value = 'local_test';
    select.dispatchEvent(new Event('change'));

    document.getElementById('modelApplyButton').click();
    await flushAsync();

    const putCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname === '/api/runtime/models/active' && (init.method || '').toUpperCase() === 'PUT';
    });

    expect(putCalls.length).toBe(1);
    expect(JSON.parse(putCalls[0][1].body)).toEqual({
      profile: 'local_test',
      require_available: true,
    });
    expect(document.getElementById('modelEffectiveChat').textContent).toBe('qwen3:14b');
  });

  it('chat send uses /api proxy paths and renders model-use receipt', async () => {
    const fetchMock = createRuntimeFetchMock({ source: 'runtime_override', activeProfile: 'local_test' });
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Return exactly: XV7_MODEL_PROOF';
    document.getElementById('sendButton').click();
    await flushAsync();

    const sessionCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname === '/api/sessions' && (init.method || '').toUpperCase() === 'POST';
    });
    const messageCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST';
    });

    expect(sessionCalls.length).toBe(1);
    expect(messageCalls.length).toBe(1);

    expect(document.getElementById('chatReceiptProfile').textContent).toBe('local_test');
    expect(document.getElementById('chatReceiptModelTag').textContent).toBe('qwen3:14b');
    expect(document.getElementById('chatReceiptRole').textContent).toBe('chat');
    expect(document.getElementById('chatReceiptSelectionSource').textContent).toBe('registry_effective_profile');
    expect(document.getElementById('chatReceiptRequestId').textContent).toBe('req-1');
  });

  it('renders an inline code artifact card inside the assistant chat flow', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard('user', 'Before artifact', null, null, '2026-06-11T00:00:00Z');
    ui.appendMessageCard(
      'assistant',
      'Generated a draft artifact.',
      null,
      {
        code_artifacts: [
          {
            filename: 'src/demo.ts',
            language: 'typescript',
            content: 'export const demo = 1;\n',
          },
        ],
      },
      '2026-06-11T00:00:01Z',
    );
    ui.appendMessageCard('user', 'After artifact', null, null, '2026-06-11T00:00:02Z');

    const timelineCards = [...document.querySelectorAll('.chat-card')];
    expect(timelineCards[0].textContent || '').toContain('Before artifact');
    expect(timelineCards[1].querySelector('.code-artifact-card')).toBeTruthy();
    expect(timelineCards[1].querySelector('.code-artifact-filename')?.textContent).toBe('src/demo.ts');
    expect(timelineCards[1].querySelector('.code-artifact-badge-language')?.textContent).toBe('TypeScript');
    expect(timelineCards[1].querySelector('.code-artifact-badge-status')?.textContent).toBe('Draft only');
    expect([...timelineCards[1].querySelectorAll('.code-artifact-button')].map((node) => node.textContent)).toEqual([
      'Copy',
      'Download',
      'Preview',
    ]);
    expect(timelineCards[1].querySelector('.code-artifact-footer-copy')?.textContent).toContain('not been applied to the repo');
    expect(timelineCards[2].textContent || '').toContain('After artifact');
  });

  it('enables preview for HTML artifacts and swaps to the preview pane', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'HTML artifact ready.',
      null,
      {
        code_artifacts: [
          {
            filename: 'preview.html',
            language: 'html',
            previewable: true,
            content: '<main id="artifact-preview">Preview works</main>',
          },
        ],
      },
      '2026-06-11T00:00:03Z',
    );

    const artifactCard = document.querySelector('.code-artifact-card');
    expect(artifactCard).toBeTruthy();

    const previewButton = [...artifactCard.querySelectorAll('.code-artifact-button')].find((node) =>
      (node.textContent || '').includes('Preview'),
    );
    expect(previewButton?.disabled).toBe(false);

    previewButton?.click();
    await flushAsync();

    expect(artifactCard.querySelector('.code-artifact-pane-code')?.classList.contains('hidden')).toBe(true);
    expect(artifactCard.querySelector('.code-artifact-pane-preview')?.classList.contains('hidden')).toBe(false);
    expect(artifactCard.querySelector('iframe')?.getAttribute('srcdoc')).toContain('Preview works');
  });

  it('renders a singular code_artifact payload inline in the assistant chat flow', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Here is a draft HTML artifact for index.html.',
      null,
      {
        code_artifact: {
          type: 'code_artifact',
          filename: 'index.html',
          language: 'html',
          previewable: true,
          applied: false,
          content: '<!doctype html><html><body><main>Draft</main></body></html>',
        },
      },
      '2026-06-11T00:00:04Z',
    );

    const artifactCard = document.querySelector('.code-artifact-card');
    expect(artifactCard).toBeTruthy();
    expect(artifactCard.querySelector('.code-artifact-filename')?.textContent).toBe('index.html');
    expect(artifactCard.querySelector('.code-artifact-badge-language')?.textContent).toBe('HTML');
    expect(artifactCard.querySelector('.code-artifact-badge-status')?.textContent).toBe('Draft only');
    expect(artifactCard.querySelector('.code-artifact-button:last-child')?.textContent).toBe('Preview');
  });

  it('renders operator receipt chip and expandable details', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('Operator: repo_status success'),
    );
    expect(chip).toBeTruthy();

    const details = [...document.querySelectorAll('.receipt-details summary')].find((node) =>
      (node.textContent || '').includes('repo_status OP-1'),
    );
    expect(details).toBeTruthy();
  });

  it('renders failed and denied receipt status styles', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Are containers running?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const failedChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('scan_docker failed'),
    );
    expect(failedChip).toBeTruthy();
    expect(failedChip.className.includes('status-failed')).toBe(true);

    prompt.value = 'Delete a file.';
    document.getElementById('sendButton').click();
    await flushAsync();

    // operatorChipLabel maps read_only_guard+denied → 'mutation denied'
    const deniedChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('mutation denied'),
    );
    expect(deniedChip).toBeTruthy();
    expect(deniedChip.className.includes('status-denied')).toBe(true);
  });

  it('renders operator activity panel from recent action history', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const items = [...document.querySelectorAll('.operator-activity-item')];
    expect(items.length).toBeGreaterThan(0);
    expect((items[0].textContent || '').toLowerCase()).toContain('repo_status');
  });

  it('clear action sends DELETE /api/runtime/models/active via proxy path', async () => {
    const fetchMock = createRuntimeFetchMock({ source: 'runtime_override', activeProfile: 'local_test' });
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('modelClearButton').click();
    await flushAsync();

    const deleteCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname === '/api/runtime/models/active' && (init.method || '').toUpperCase() === 'DELETE';
    });

    expect(deleteCalls.length).toBe(1);
  });

  it('handles unreachable and failure state honestly', async () => {
    global.fetch = createRuntimeFetchMock({ reachable: false });

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('modelOllamaReachable').textContent).toBe('no');
    expect(document.getElementById('modelAvailabilityChat').textContent).toBe('unavailable');

    global.fetch = createRuntimeFetchMock({ failModels: true });
    await new Xv7UI().refreshModelProfileControl();
    await flushAsync();

    expect(document.getElementById('modelPanelStatus').textContent).toContain('runtime models unavailable');
  });

  it('profile mutation does not require browser API key field', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const select = document.getElementById('modelProfileSelect');
    select.value = 'local_test';
    select.dispatchEvent(new Event('change'));

    document.getElementById('modelApplyButton').click();
    await flushAsync();

    const putCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname === '/api/runtime/models/active' && (init.method || '').toUpperCase() === 'PUT';
    });

    expect(putCalls.length).toBe(1);
  });

  it('Enter sends prompt; Shift+Enter does not send', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();
    fetchMock.mockClear();

    const input = document.getElementById('promptInput');
    input.value = 'hello';

    // Shift+Enter must NOT send
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true }));
    await flushAsync();
    const afterShift = fetchMock.mock.calls.filter((c) =>
      new URL(c[0], 'http://localhost').pathname === '/api/sessions' && (c[1]?.method || '').toUpperCase() === 'POST'
    );
    expect(afterShift.length).toBe(0);

    // Plain Enter MUST send
    input.value = 'hello';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', shiftKey: false, bubbles: true }));
    await flushAsync();
    const afterEnter = fetchMock.mock.calls.filter((c) =>
      new URL(c[0], 'http://localhost').pathname === '/api/sessions' && (c[1]?.method || '').toUpperCase() === 'POST'
    );
    expect(afterEnter.length).toBe(1);
  });

  it('renders operator mode toggle with OFF default', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const toggle = document.getElementById('operatorModeToggle');
    expect(toggle.textContent).toContain('OFF');
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    expect(document.getElementById('operatorModeBanner').classList.contains('hidden')).toBe(true);
  });

  it('slash menu shows scan commands in normal mode and mutation commands in operator mode', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const input = document.getElementById('promptInput');
    input.value = '/';
    input.dispatchEvent(new Event('input'));
    await flushAsync();

    const menuTextNormal = document.getElementById('slashMenu').textContent || '';
    expect(menuTextNormal).toContain('/scan-repo');
    expect(menuTextNormal).toContain('/scan-ports');
    expect(menuTextNormal).toContain('/scan-cpu');
    expect(menuTextNormal).toContain('/scan-gpu');
    expect(menuTextNormal).toContain('/scan-disk');
    expect(menuTextNormal).toContain('/list-disks');
    expect(menuTextNormal).toContain('/list-drives');
    expect(menuTextNormal).not.toContain('/delete-file');

    document.getElementById('operatorModeToggle').click();
    await flushAsync();

    input.value = '/';
    input.dispatchEvent(new Event('input'));
    await flushAsync();

    const menuTextOperator = document.getElementById('slashMenu').textContent || '';
    expect(menuTextOperator).toContain('/delete-file');
  });

  it('stages delete-file and renders confirmation card before execution', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('operatorModeToggle').click();
    await flushAsync();

    const input = document.getElementById('promptInput');
    input.value = '/delete-file X:/XV7/test-delete.txt';
    document.getElementById('sendButton').click();
    await flushAsync();

    const confirmArea = document.getElementById('operatorConfirmArea');
    expect(confirmArea.classList.contains('hidden')).toBe(false);
    expect(confirmArea.textContent).toContain('Pending confirmation');

    const receiptChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('pending_confirmation'),
    );
    expect(receiptChip).toBeTruthy();
  });

  it('natural-language hardware scan failure renders operator receipt without mutation confirmation card', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const input = document.getElementById('promptInput');
    input.value = 'what processor am i running';
    document.getElementById('sendButton').click();
    await flushAsync();

    const timelineText = document.getElementById('chatTimeline').textContent || '';
    expect(timelineText.toLowerCase()).toContain('local host scan bridge');

    const receiptChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('scan_cpu failed'),
    );
    expect(receiptChip).toBeTruthy();

    expect(document.getElementById('operatorConfirmArea').classList.contains('hidden')).toBe(true);
  });

  it('cancel button cancels staged action and clears confirmation card', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('operatorModeToggle').click();
    await flushAsync();

    const input = document.getElementById('promptInput');
    input.value = '/delete-file X:/XV7/test-delete.txt';
    document.getElementById('sendButton').click();
    await flushAsync();

    const cancelButton = [...document.querySelectorAll('#operatorConfirmArea button')].find((node) =>
      (node.textContent || '').includes('Cancel'),
    );
    cancelButton.click();
    await flushAsync();

    const confirmArea = document.getElementById('operatorConfirmArea');
    expect(confirmArea.classList.contains('hidden')).toBe(true);
    expect((document.getElementById('chatTimeline').textContent || '').toLowerCase()).toContain('cancelled');
  });

  it('high-risk command requires exact typed confirmation phrase', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('operatorModeToggle').click();
    await flushAsync();

    const input = document.getElementById('promptInput');
    input.value = '/format-drive E:';
    document.getElementById('sendButton').click();
    await flushAsync();

    const typedInput = document.querySelector('.operator-typed-confirm-input');
    expect(typedInput).toBeTruthy();
    typedInput.value = 'WRONG PHRASE';

    const confirmButton = [...document.querySelectorAll('#operatorConfirmArea button')].find((node) =>
      (node.textContent || '').includes('Confirm Action'),
    );
    confirmButton.click();
    await flushAsync();

    expect((document.getElementById('chatTimeline').textContent || '').toLowerCase()).toContain('did not match');
    expect(document.getElementById('operatorConfirmArea').classList.contains('hidden')).toBe(false);
  });

  it('disables mic and shows unsupported message when speech recognition is unavailable', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const micButton = document.getElementById('micButton');
    expect(micButton.disabled).toBe(true);

    ui.toggleVoiceInput();
    expect(document.getElementById('alertBox').textContent).toContain('Voice input is not supported in this browser.');
  });

  it('writes transcript to prompt and does not auto-send', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onstart) this.onstart();
      }

      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;

    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    const ui = new Xv7UI();
    await flushAsync();
    fetchMock.mockClear();

    ui.toggleVoiceInput();
    expect(document.getElementById('micButton').textContent).toContain('Listening...');

    ui.speechRecognition.onresult({
      results: [[{ transcript: 'voice draft text' }]],
    });
    await flushAsync();

    expect(document.getElementById('promptInput').value).toBe('voice draft text');

    const messageCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname.includes('/messages') && (init.method || '').toUpperCase() === 'POST';
    });
    expect(messageCalls.length).toBe(0);
  });

  it('shows permission denied message from microphone errors', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onerror) this.onerror({ error: 'not-allowed' });
      }

      stop() {}
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.toggleVoiceInput();
    expect(document.getElementById('alertBox').textContent).toContain('Microphone permission was denied.');
    expect(document.getElementById('voiceStatus').textContent).toContain('Allow microphone permission in the browser to use voice input.');
  });

  it('recognition error clears listening state and records last error state', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }
      start() {
        if (this.onstart) this.onstart();
        if (this.onerror) this.onerror({ error: 'no-speech' });
      }
      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.toggleVoiceInput();
    ui.speechRecognition.onend();
    await flushAsync();

    expect(ui.voiceState.listening).toBe(false);
    expect(ui.voiceState.lastVoiceError).toContain('No speech was detected');
  });

  it('mic button has correct idle aria-label', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('micButton').getAttribute('aria-label')).toBe('Start voice input');
  });

  it('supported speech recognition starts listening and clicking again stops listening', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onstart) this.onstart();
      }

      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    document.getElementById('micButton').click();
    expect(document.getElementById('micButton').textContent).toContain('Listening...');
    expect(document.getElementById('micButton').getAttribute('aria-label')).toBe('Stop voice input');
    expect(document.getElementById('voiceStatus').textContent).toContain('Listening...');

    document.getElementById('micButton').click();
    expect(document.getElementById('micButton').textContent).toBe('Mic');
    expect(document.getElementById('micButton').getAttribute('aria-label')).toBe('Start voice input');
  });

  it('transcript appends to existing prompt text and does not auto-send', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onstart) this.onstart();
      }

      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    const ui = new Xv7UI();
    await flushAsync();
    fetchMock.mockClear();

    document.getElementById('promptInput').value = 'hello';
    ui.toggleVoiceInput();
    ui.speechRecognition.onresult({ results: [[{ transcript: 'world' }]] });
    ui.speechRecognition.onend();
    await flushAsync();

    expect(document.getElementById('promptInput').value).toBe('hello world');
    expect(document.getElementById('voiceStatus').textContent).toContain('Voice captured. Review and send.');
    expect(ui.voiceState.transcriptPending).toBe(true);

    const messageCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0], 'http://localhost').pathname.includes('/messages') && (init.method || '').toUpperCase() === 'POST';
    });
    expect(messageCalls.length).toBe(0);
  });

  it('recognition end returns mic to idle and send clears transcript pending status', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onstart) this.onstart();
      }

      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.toggleVoiceInput();
    ui.speechRecognition.onresult({ results: [[{ transcript: 'draft prompt' }]] });
    ui.speechRecognition.onend();
    await flushAsync();

    expect(document.getElementById('voiceStatus').textContent).toContain('Voice captured. Review and send.');

    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.getElementById('voiceStatus').textContent).toBe('');
    expect(document.getElementById('micButton').textContent).toBe('Mic');
    expect(ui.voiceState.transcriptPending).toBe(false);
  });

  it('renders read-aloud button on assistant messages and speech uses visible text only', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };

    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const audioButtons = [...document.querySelectorAll('.message-audio-button')];
    expect(audioButtons.length).toBeGreaterThan(0);
    expect(audioButtons[0].getAttribute('aria-label')).toBe('Stop reading aloud');

    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
    expect(window.speechSynthesis.speak.mock.calls[0][0].text).toContain('The repo is on main. The working tree is not clean.');
    expect(window.speechSynthesis.speak.mock.calls[0][0].text).not.toContain('Operator:');

    audioButtons[0].click();
    await flushAsync();
    expect(audioButtons[0].getAttribute('aria-label')).toBe('Read assistant response aloud');
  });

  it('read-aloud toggle stops active speech', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };

    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const audioButton = document.querySelector('.message-audio-button');
    audioButton.click();
    await flushAsync();

    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    expect(audioButton.getAttribute('aria-label')).toBe('Read assistant response aloud');
  });

  it('read-aloud normalizes legacy Xoduz text to Exodus for speech only', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const article = ui.appendMessageCard('assistant', 'My name is Xoduz — pronounced Exodus.', null, {}, ui.nowIso());
    await ui.toggleReadAloud(article);

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    expect(utterance.text).toContain('Exodus');
    expect(utterance.text).not.toContain('Xoduz');
    expect(article.querySelector('.chat-visible-text').textContent).toContain('Xoduz');
  });

  it('read-aloud strips receipt/debug content from spoken output', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const contaminated = [
      'My name is Xoduz — pronounced Exodus.',
      'Receipts:',
      '- System: XV7-SYSTEM-0001',
      'Operator receipt: repo_status OP-1 success.',
      'Context receipt: System Prompt XV7-SYSTEM-0001.',
      'Knowledge: XV7-KNOWLEDGE-0002',
      'Model: qwen3:8b',
    ].join('\n');

    const article = ui.appendMessageCard('assistant', contaminated, null, {}, ui.nowIso());
    await ui.toggleReadAloud(article);

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    const spoken = utterance.text;
    expect(spoken).toContain('Exodus');
    expect(spoken).not.toContain('Operator receipt');
    expect(spoken).not.toContain('Receipts:');
    expect(spoken).not.toContain('Context receipt');
    expect(spoken).not.toContain('System Prompt');
    expect(spoken).not.toContain('XV7-SYSTEM');
    expect(spoken).not.toContain('XV7-KNOWLEDGE');
    expect(spoken).not.toContain('qwen3');
  });

  it('normalizeSpeechText converts XV7 and XV-7 to X V Seven', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const spoken = ui.normalizeSpeechText('I am Xoduz, the XV7 assistant in XV-7 mode.');
    expect(spoken).toContain('X V Seven assistant');
    expect(spoken).toContain('X V Seven mode');
    expect(spoken).not.toContain('XV7');
    expect(spoken).not.toContain('XV-7');
  });

  it('normalizeSpeechText strips markdown, bullets, code fences, backticks, and receipt/meta lines', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const raw = [
      '### **Backend**',
      '- Planning',
      '- Architecture',
      '- Testing',
      '```json',
      '{"hidden":true}',
      '```',
      'Use `npm test` now.',
      'Operator receipt: repo_status OP-1 success.',
      'System: XV7-SYSTEM-0001',
      'Knowledge: XV7-KNOWLEDGE-0002',
      'Model: qwen3:8b',
    ].join('\n');

    const spoken = ui.normalizeSpeechText(raw);
    expect(spoken).toContain('Backend');
    expect(spoken).toContain('Planning.');
    expect(spoken).toContain('Architecture.');
    expect(spoken).toContain('Testing.');
    expect(spoken).toContain('Use npm test now.');
    expect(spoken).not.toContain('###');
    expect(spoken).not.toContain('**');
    expect(spoken).not.toContain('```');
    expect(spoken).not.toContain('`');
    expect(spoken).not.toContain('Operator receipt');
    expect(spoken).not.toContain('XV7-SYSTEM');
    expect(spoken).not.toContain('XV7-KNOWLEDGE');
    expect(spoken).not.toContain('qwen3:8b');
  });

  it('name answer read-aloud stays natural and does not speak pronounced explanation', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'What is your name?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const visible = [...document.querySelectorAll('.chat-visible-text')].at(-1).textContent;
    expect(visible).toBe('My name is Xoduz.');

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    expect(utterance.text).toBe('My name is Exodus.');
    expect(utterance.text.toLowerCase()).not.toContain('pronounced');
  });

  it('starting read-aloud cancels previous speech first', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();
    document.getElementById('promptInput').value = 'What is your name?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const audioButtons = [...document.querySelectorAll('.message-audio-button')];
    audioButtons[0].click();
    await flushAsync();
    audioButtons[1].click();
    await flushAsync();

    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
  });

  it('read-aloud clears speaking state on end', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    expect(utterance).toBeTruthy();
    utterance.onend();
    await flushAsync();

    expect(ui.voiceState.speaking).toBe(false);
    expect(document.getElementById('voiceStatus').textContent).toContain('Read-aloud stopped.');
  });

  it('read-aloud clears speaking state on error', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    expect(utterance).toBeTruthy();
    utterance.onerror();
    await flushAsync();

    expect(ui.voiceState.speaking).toBe(false);
    expect(ui.voiceState.lastVoiceError).toContain('Browser blocked voice playback. Try clicking Read again.');
  });

  it('custom voice events fire for listening start stop and transcript captured', async () => {
    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }
      start() {
        if (this.onstart) this.onstart();
      }
      stop() {
        if (this.onend) this.onend();
      }
    }

    window.SpeechRecognition = SpeechRecognitionMock;
    global.fetch = createRuntimeFetchMock();

    const listeningStart = vi.fn();
    const listeningStop = vi.fn();
    const transcriptCaptured = vi.fn();
    window.addEventListener('xv7:voice-listening-start', listeningStart);
    window.addEventListener('xv7:voice-listening-stop', listeningStop);
    window.addEventListener('xv7:voice-transcript-captured', transcriptCaptured);

    const ui = new Xv7UI();
    await flushAsync();

    ui.toggleVoiceInput();
    ui.speechRecognition.onresult({ results: [[{ transcript: 'voice event text' }]] });
    ui.speechRecognition.onend();
    await flushAsync();

    expect(listeningStart).toHaveBeenCalled();
    expect(listeningStop).toHaveBeenCalled();
    expect(transcriptCaptured).toHaveBeenCalled();
  });

  it('custom voice events fire for speaking start and stop', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    const speakingStart = vi.fn();
    const speakingStop = vi.fn();
    window.addEventListener('xv7:voice-speaking-start', speakingStart);
    window.addEventListener('xv7:voice-speaking-stop', speakingStop);

    const ui = new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const utterance = window.speechSynthesis.speak.mock.calls.at(-1)[0];
    expect(utterance).toBeTruthy();
    utterance.onend();
    await flushAsync();

    expect(speakingStart).toHaveBeenCalled();
    expect(speakingStop).toHaveBeenCalled();
  });

  it('voice diagnostics renders supported and unsupported states', async () => {
    global.fetch = createRuntimeFetchMock();

    window.speechSynthesis = undefined;
    window.SpeechSynthesisUtterance = undefined;
    const uiUnsupported = new Xv7UI();
    await flushAsync();
    expect(document.getElementById('voiceDiagInput').textContent).toBe('unsupported');
    expect(document.getElementById('voiceDiagOutput').textContent).toBe('no');

    class SpeechRecognitionMock {
      constructor() {
        this.onstart = null;
        this.onend = null;
        this.onresult = null;
        this.onerror = null;
      }

      start() {
        if (this.onstart) this.onstart();
      }

      stop() {
        if (this.onend) this.onend();
      }
    }
    window.SpeechRecognition = SpeechRecognitionMock;
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Online (Natural)', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };

    buildDom();
    global.fetch = createRuntimeFetchMock();
    new Xv7UI();
    await flushAsync();
    expect(document.getElementById('voiceDiagInput').textContent).toBe('supported');
    expect(document.getElementById('voiceDiagOutput').textContent).toBe('yes');
  });

  it('voice selector renders and prefers a female-like voice when available', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Zira Desktop', lang: 'en-US', default: false },
      { name: 'Microsoft David Desktop', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const optionValues = [...document.querySelectorAll('#voiceSelect option')].map((option) => option.value);
    expect(optionValues).toContain('Microsoft Zira Desktop');
    expect(document.getElementById('voiceSelect').value).toBe('Microsoft Zira Desktop');
    expect(document.getElementById('voiceSettingsStatus').textContent).toContain('Using Microsoft Zira Desktop.');
    expect(document.getElementById('voiceDiagVoiceCount').textContent).toBe('2');
    expect(document.getElementById('voiceDiagSelected').textContent).toBe('Microsoft Zira Desktop');
  });

  it('voice settings persist to localStorage and restore on reload', async () => {
    window.localStorage.setItem('xv7.voice.voiceName', 'Microsoft Jenny Desktop');
    window.localStorage.setItem('xv7.voice.volume', '0.7');
    window.localStorage.setItem('xv7.voice.rate', '1.3');
    window.localStorage.setItem('xv7.voice.pitch', '1.4');
    window.localStorage.setItem('xv7.voice.muted', 'true');

    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Desktop', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('voiceSelect').value).toBe('Microsoft Jenny Desktop');
    expect(document.getElementById('voiceVolume').value).toBe('0.7');
    expect(document.getElementById('voiceRate').value).toBe('1.3');
    expect(document.getElementById('voicePitch').value).toBe('1.4');
    expect(document.getElementById('voiceMute').checked).toBe(true);
  });

  it('applies selected voice settings to utterances and the test voice phrase', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Desktop', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('voiceSelect').value = 'Microsoft Jenny Desktop';
    document.getElementById('voiceSelect').dispatchEvent(new Event('change', { bubbles: true }));
    document.getElementById('voiceVolume').value = '0.6';
    document.getElementById('voiceVolume').dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('voiceRate').value = '1.4';
    document.getElementById('voiceRate').dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('voicePitch').value = '1.2';
    document.getElementById('voicePitch').dispatchEvent(new Event('input', { bubbles: true }));

    document.getElementById('voiceTestButton').click();
    await flushAsync();

    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
    const utterance = window.speechSynthesis.speak.mock.calls[0][0];
    expect(utterance.text).toBe('Hello Otis. I am Exodus. This is my selected voice.');
    expect(utterance.voice.name).toBe('Microsoft Jenny Desktop');
    expect(utterance.volume).toBeCloseTo(0.6, 1);
    expect(utterance.rate).toBeCloseTo(1.4, 1);
    expect(utterance.pitch).toBeCloseTo(1.2, 1);
  });

  it('muted state lowers playback volume and stop voice cancels playback', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Jenny Desktop', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('voiceMute').checked = true;
    document.getElementById('voiceMute').dispatchEvent(new Event('change', { bubbles: true }));
    document.getElementById('voiceTestButton').click();
    await flushAsync();

    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
    expect(window.speechSynthesis.speak.mock.calls[0][0].volume).toBe(0);

    document.getElementById('voiceMute').checked = false;
    document.getElementById('voiceMute').dispatchEvent(new Event('change', { bubbles: true }));
    document.getElementById('voiceTestButton').click();
    await flushAsync();
    document.getElementById('voiceStopButton').click();

    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
  });

  it('unsupported speech synthesis disables read-aloud gracefully', async () => {
    window.speechSynthesis = undefined;
    window.SpeechSynthesisUtterance = undefined;
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const audioButton = document.querySelector('.message-audio-button');
    expect(audioButton).toBeTruthy();
    expect(audioButton.disabled).toBe(true);
  });

  it('copies entire chat with visible content and compact receipts only', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    document.getElementById('copyChatButton').click();
    await flushAsync();

    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1);
    const copiedText = navigator.clipboard.writeText.mock.calls[0][0];
    expect(copiedText).toContain('User:');
    expect(copiedText).toContain('Xoduz:');
    expect(copiedText).toContain('Receipts:');
    expect(copiedText).toContain('- Operator: repo_status success');
    expect(copiedText).toContain('- Verified: XV7-VERIFIED-0001');
    expect(copiedText).toContain('- Model: qwen3:8b');
    expect(copiedText).not.toContain('Receipt:\n');
    expect(copiedText).not.toContain('{"');
    expect(document.getElementById('copyToast').textContent).toContain('Chat copied.');
  });

  it('copies individual message content and keeps assistant receipts compact', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const copyButtons = [...document.querySelectorAll('.message-copy-button')];
    expect(copyButtons.length).toBeGreaterThan(1);

    copyButtons[0].click();
    await flushAsync();
    const userCopy = navigator.clipboard.writeText.mock.calls.at(-1)[0];
    expect(userCopy).toContain('User:');

    copyButtons[1].click();
    await flushAsync();
    const assistantCopy = navigator.clipboard.writeText.mock.calls.at(-1)[0];
    expect(assistantCopy).toContain('Xoduz:');
    expect(assistantCopy).toContain('Receipts:');
    expect(assistantCopy).toContain('- Operator: repo_status success');
    expect(document.getElementById('copyToast').textContent).toContain('Copied.');
  });

  it('visible chat answer does not embed raw receipt text', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const assistantText = document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent || '';
    expect(assistantText).toContain('The repo is on main. The working tree is not clean.');
    expect(assistantText).not.toContain('Receipt:');
    expect(assistantText).not.toContain('Operator receipt:');
    expect(assistantText).not.toContain('Context receipt:');
  });

  it('renders system receipt as System label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'What is your name?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text === 'System: XV7-SYSTEM-0001')).toBe(true);
  });

  it('renders focus receipt as Focus label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'What are we working on right now?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text === 'Focus: XV7-FOCUS-0003')).toBe(true);
  });

  it('renders knowledge receipt as Knowledge label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Can you help write implementation prompts for VS Code/Copilot?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text === 'Knowledge: XV7-KNOWLEDGE-0002')).toBe(true);
  });

  it('renders verified receipt as Verified label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'What do you know is verified?';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text === 'Verified: XV7-VERIFIED-0001')).toBe(true);
  });

  it('renders memory receipts with Memory label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Remember this preference';
    document.getElementById('sendButton').click();
    await flushAsync();

    const memoryChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').includes('Memory:'),
    );
    expect(memoryChip).toBeTruthy();
  });

  it('does not render operator/context mislabel strings in chips', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text.includes('Operator receipt: context'))).toBe(false);
    expect(chips.some((text) => text.includes('Context: Operator receipt'))).toBe(false);
  });

  it('renders legacy fallback compact context safely', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'fallback context test',
      null,
      {
        context_receipt: { compact: 'Context receipt: something_custom_without_ids.' },
        operator_receipts: [],
        memory_receipts: [],
        model_use_receipt: {},
      },
      '2026-06-11T00:00:00Z',
    );

    const chips = [...document.querySelectorAll('.receipt-chip')].map((node) => (node.textContent || '').trim());
    expect(chips.some((text) => text.startsWith('Context:'))).toBe(true);
  });

  it('renders operator action receipts with Operator label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const operatorChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').startsWith('Operator:'),
    );
    expect(operatorChip).toBeTruthy();
  });

  it('renders model receipt with Model label', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Return exactly: XV7_MODEL_PROOF';
    document.getElementById('sendButton').click();
    await flushAsync();

    const modelChip = [...document.querySelectorAll('.receipt-chip')].find((node) =>
      (node.textContent || '').startsWith('Model:'),
    );
    expect(modelChip).toBeTruthy();
  });

  it('renders per-message Why this answer drawer with focus metadata', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Focus-guided response',
      null,
      {
        source_record_ids: ['XV7-FOCUS-0005', 'XV7-KNOWLEDGE-0006'],
        active_focus_id: 'XV7-FOCUS-0005',
        focus_applied: true,
        context_includes_focus: true,
        fallback_used: false,
        fallback_reason: 'not-needed',
        response_mode: 'active_focus_guided',
        context_receipt: {
          context_receipts: [
            { layer: 'active_focus', record_id: 'XV7-FOCUS-0005' },
            { layer: 'knowledge', record_id: 'XV7-KNOWLEDGE-0006' },
          ],
        },
        model_use_receipt: { model_tag: 'policy_only' },
        policy_provenance: {
          intent_class: 'active_focus_follow_up',
          response_mode: 'active_focus_guided',
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const drawer = document.querySelector('.why-answer-drawer');
    expect(drawer).toBeTruthy();
    expect((drawer?.textContent || '').toLowerCase()).toContain('why this answer');
    expect(drawer?.textContent || '').toContain('active_focus_follow_up');
    expect(drawer?.textContent || '').toContain('XV7-FOCUS-0005');
    expect(drawer?.textContent || '').toContain('Focus');
  });

  it('renders NOW/REVIEW/HISTORY and LIBRARY relevance filters with lifecycle actions', async () => {
    global.fetch = createRuntimeFetchMock();
    new Xv7UI();
    await flushAsync();

    document.getElementById('diagnosticsToggleButton').click();
    await flushAsync();

    const cards = [...document.querySelectorAll('.brain-record-card')];
    expect(cards.length).toBeGreaterThan(0);

    expect(document.getElementById('brainRecordsOpenLibraryButton')).toBeNull();
    expect(document.getElementById('brainRecordsAnalyzeButton')).toBeNull();
    expect(document.getElementById('brainRecordsPendingLink')).toBeNull();
    expect(document.getElementById('brainRecordsRefreshButton')).toBeNull();
    expect((document.getElementById('brainNowCounts').textContent || '')).toContain('current=');
    expect((document.getElementById('brainNowCounts').textContent || '')).toContain('review=');
    expect(document.getElementById('brainReviewToolbar').classList.contains('hidden')).toBe(true);

    const nowText = document.getElementById('brainRecordsList').textContent || '';
    expect(nowText).toContain('XV7-SYSTEM-0001');
    expect(nowText).toContain('XV7-FOCUS-0005');
    expect(nowText).not.toContain('XV7-VERIFIED-0001');
    expect(nowText).toContain('Edit / Tune');
    expect(nowText).not.toContain('Approve');
    expect(nowText).not.toContain('Reject');
    expect((document.getElementById('brainRecordsStatus').textContent || '').toLowerCase()).toContain('current=');
    expect((document.querySelector('#brainRecordsViews button[data-view="review"]')?.textContent || '')).toContain('REVIEW (2)');
    expect((document.querySelector('#brainRecordsViews button[data-view="history"]')?.textContent || '')).toContain('HISTORY (1)');
    expect((document.querySelector('#brainRecordsViews button[data-view="library"]')?.textContent || '')).toContain('LIBRARY (6)');
    expect((document.querySelector('#brainRecordsViews button[data-view="now"]')?.textContent || '')).toContain('NOW (3)');
    expect(document.getElementById('brainRecordsList').textContent || '').not.toContain('XV7-KNOWLEDGE-0007');
    expect(document.getElementById('brainRecordsList').textContent || '').not.toContain('XV7-KNOWLEDGE-0003');

    const reviewView = document.querySelector('#brainRecordsViews button[data-view="review"]');
    expect(reviewView).toBeTruthy();
    reviewView.click();
    await flushAsync();

    const reviewText = document.getElementById('brainRecordsList').textContent || '';
    expect(reviewText).toContain('XV7-KNOWLEDGE-0007');
    expect(reviewText).toContain('XV7-VERIFIED-0001');
    expect(reviewText).not.toContain('XV7-FOCUS-0005');
    expect(reviewText).toContain('Approve');
    expect(reviewText).toContain('Reject');
    expect(reviewText).toContain('More');
    expect(reviewText).not.toContain('Mark Historical');
    expect(reviewText).not.toContain('Split to Current Rule');
    expect(reviewText).toContain('Reason: Contains old completed milestones and current operational bridge rule content.');

    const reviewMoreButton = [...document.querySelectorAll('.brain-record-actions button')]
      .find((button) => (button.textContent || '') === 'More');
    expect(reviewMoreButton).toBeTruthy();
    reviewMoreButton.click();
    await flushAsync();

    const approveCleanupButton = [...document.querySelectorAll('.brain-record-more-action')]
      .find((button) => (button.textContent || '').includes('Approve Recommendation'));
    expect(approveCleanupButton).toBeTruthy();
    approveCleanupButton.click();
    await flushAsync();

    const applyCleanupButton = document.getElementById('brainRecordsApplyCleanupButton');
    expect(applyCleanupButton).toBeTruthy();
    expect(document.getElementById('brainReviewToolbar').classList.contains('hidden')).toBe(false);
    expect((applyCleanupButton.textContent || '')).toContain('(1)');
    applyCleanupButton.click();
    await flushAsync();

    const nowViewAfterCleanup = document.querySelector('#brainRecordsViews button[data-view="now"]');
    expect(nowViewAfterCleanup).toBeTruthy();
    nowViewAfterCleanup.click();
    await flushAsync();
    const nowAfterCleanupText = document.getElementById('brainRecordsList').textContent || '';
    expect(nowAfterCleanupText).toContain('XV7-KNOWLEDGE-0998');

    const reviewViewAfterCleanup = document.querySelector('#brainRecordsViews button[data-view="review"]');
    expect(reviewViewAfterCleanup).toBeTruthy();
    reviewViewAfterCleanup.click();
    await flushAsync();

    const historyView = document.querySelector('#brainRecordsViews button[data-view="history"]');
    expect(historyView).toBeTruthy();
    historyView.click();
    await flushAsync();

    const historyText = document.getElementById('brainRecordsList').textContent || '';
    expect(historyText).toContain('XV7-VERIFIED-0001');
    expect(historyText).toContain('Restore / Mark Current');
    expect(historyText).toContain('More');
    expect(historyText).not.toContain('Mark Superseded');
    expect(document.getElementById('brainReviewToolbar').classList.contains('hidden')).toBe(true);

    const libraryView = document.querySelector('#brainRecordsViews button[data-view="library"]');
    expect(libraryView).toBeTruthy();
    libraryView.click();
    await flushAsync();

    expect(document.getElementById('brainLibraryControls').classList.contains('hidden')).toBe(false);
    const libraryText = document.getElementById('brainRecordsList').textContent || '';
    expect(libraryText).toContain('XV7-SYSTEM-0001');
    expect(libraryText).toContain('CURRENT');
    expect(libraryText).toContain('Edit / Tune');
    expect(libraryText).toContain('More');
    expect(libraryText).not.toContain('Copy/Edit Runtime Override');
    expect(libraryText).not.toContain('XV7-KNOWLEDGE-0003');

    document.getElementById('brainLibraryShowArchived').checked = true;
    document.getElementById('brainLibraryShowArchived').dispatchEvent(new Event('change'));
    await flushAsync();

    document.getElementById('brainLibraryStatusFilter').value = 'all';
    document.getElementById('brainLibraryStatusFilter').dispatchEvent(new Event('change'));
    await flushAsync();

    expect(document.getElementById('brainRecordsList').textContent || '').toContain('XV7-KNOWLEDGE-0003');

    document.getElementById('brainLibraryRelevanceFilter').value = 'needs_review';
    document.getElementById('brainLibraryRelevanceFilter').dispatchEvent(new Event('change'));
    await flushAsync();
    const relevanceText = document.getElementById('brainRecordsList').textContent || '';
    expect(relevanceText).toContain('XV7-KNOWLEDGE-0007');
    expect(relevanceText).not.toContain('XV7-SYSTEM-0001');

    document.getElementById('brainLibraryRelevanceFilter').value = 'all';
    document.getElementById('brainLibraryRelevanceFilter').dispatchEvent(new Event('change'));
    await flushAsync();

    document.getElementById('brainLibrarySearch').value = 'proof before ci';
    document.getElementById('brainLibrarySearch').dispatchEvent(new Event('input'));
    await flushAsync();

    const filteredText = document.getElementById('brainRecordsList').textContent || '';
    expect(filteredText).toContain('XV7-KNOWLEDGE-0007');
    expect(filteredText).not.toContain('XV7-FOCUS-0005');

    document.getElementById('brainLibrarySearch').value = '';
    document.getElementById('brainLibrarySearch').dispatchEvent(new Event('input'));
    await flushAsync();

    const reviewViewAgain = document.querySelector('#brainRecordsViews button[data-view="review"]');
    expect(reviewViewAgain).toBeTruthy();
    reviewViewAgain.click();
    await flushAsync();

    const reviewMoreButtonAgain = [...document.querySelectorAll('.brain-record-actions button')]
      .find((button) => (button.textContent || '') === 'More');
    expect(reviewMoreButtonAgain).toBeTruthy();
    reviewMoreButtonAgain.click();
    await flushAsync();

    const splitButton = [...document.querySelectorAll('.brain-record-more-action')]
      .find((button) => (button.textContent || '').includes('Split to Current Rule'));
    expect(splitButton).toBeTruthy();
    splitButton.click();
    await flushAsync();

    const libraryViewAgain = document.querySelector('#brainRecordsViews button[data-view="library"]');
    expect(libraryViewAgain).toBeTruthy();
    libraryViewAgain.click();
    await flushAsync();

    const libraryMoreButton = [...document.querySelectorAll('.brain-record-actions button')]
      .find((button) => (button.textContent || '') === 'More');
    expect(libraryMoreButton).toBeTruthy();
    libraryMoreButton.click();
    await flushAsync();

    const rawJsonButton = [...document.querySelectorAll('.brain-record-more-action')]
      .find((button) => (button.textContent || '').includes('Raw JSON'));
    expect(rawJsonButton).toBeTruthy();
    rawJsonButton.click();
    await flushAsync();

    const calls = global.fetch.mock.calls.map(([url, init]) => ({
      url: String(url),
      method: String(init?.method || 'GET').toUpperCase(),
    }));
    expect(calls.some((call) => call.method === 'POST' && call.url.includes('/runtime/brain/records/XV7-VERIFIED-0001/apply-recommendation'))).toBe(true);
    expect(calls.some((call) => call.method === 'POST' && call.url.includes('/runtime/brain/records/') && call.url.includes('/split'))).toBe(true);
  });

  it('binds virtual NOW focus card from active context when focus record is absent from library', async () => {
    global.fetch = createRuntimeFetchMock({
      activeContextFocusId: 'XV7-FOCUS-0006',
      activeContextFocusSummary: 'on correct communication with your operator Otis and understanding his workflows',
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('diagnosticsToggleButton').click();
    await flushAsync();

    const nowTab = document.querySelector('#brainRecordsViews button[data-view="now"]');
    expect(nowTab).toBeTruthy();
    const nowLabel = nowTab?.textContent || '';
    expect(nowLabel).toContain('NOW (');
    const countMatch = nowLabel.match(/NOW \((\d+)\)/);
    expect(countMatch).toBeTruthy();
    const nowCount = Number(countMatch[1]);
    expect(nowCount).toBeGreaterThanOrEqual(1);

    const focusCard = [...document.querySelectorAll('.brain-record-card')].find((card) =>
      (card.textContent || '').includes('XV7-FOCUS-0006'));
    expect(focusCard).toBeTruthy();
    const focusActions = [...focusCard.querySelectorAll('.brain-record-actions button')]
      .map((button) => (button.textContent || '').trim());
    expect(focusActions).toEqual(['View']);
  });

  it('renders avatar card with Xoduz label and idle default state', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('avatarCard')).toBeTruthy();
    expect(document.getElementById('avatarStateText').textContent).toBe('Idle');
    expect(document.getElementById('avatarDiagState').textContent).toBe('idle');
    expect(document.getElementById('avatarDiagClip').textContent).toContain('xoduz-idle.mp4');
    expect(document.getElementById('avatarDiagClip').textContent).not.toContain('(disabled)');
    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-idle.mp4');
  });

  it('listening/captured/speaking voice events update avatar state and speaking stop returns idle', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    window.dispatchEvent(new CustomEvent('xv7:voice-listening-start'));
    expect(document.getElementById('avatarStateText').textContent).toBe('Listening');
    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-idle.mp4');

    window.dispatchEvent(new CustomEvent('xv7:voice-transcript-captured', { detail: { transcript: 'hello' } }));
    expect(document.getElementById('avatarStateText').textContent).toBe('Captured');
    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-idle.mp4');

    window.dispatchEvent(new CustomEvent('xv7:voice-speaking-start', { detail: { messageId: 'm1' } }));
    expect(document.getElementById('avatarStateText').textContent).toBe('Speaking');
    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-speaking.mp4');

    window.dispatchEvent(new CustomEvent('xv7:voice-speaking-stop', { detail: { messageId: 'm1' } }));
    expect(document.getElementById('avatarStateText').textContent).toBe('Idle');
  });

  it('send message sets avatar to thinking and returns to idle after assistant response', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Check the repo.';
    document.getElementById('sendButton').click();
    expect(document.getElementById('avatarStateText').textContent).toBe('Thinking');
    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-thinking.mp4');

    await flushAsync();
    expect(document.getElementById('avatarStateText').textContent).toBe('Idle');
  });

  it('voice error switches avatar to error then resets to idle', async () => {
    vi.useFakeTimers();
    try {
      global.fetch = createRuntimeFetchMock();

      new Xv7UI();

      window.dispatchEvent(new CustomEvent('xv7:voice-error', { detail: { error: 'not-allowed' } }));
      expect(document.getElementById('avatarStateText').textContent).toBe('Voice error');

      vi.advanceTimersByTime(2000);
      expect(document.getElementById('avatarStateText').textContent).toBe('Idle');
    } finally {
      vi.useRealTimers();
    }
  });

  it('avatar collapse toggle works and updates diagnostics visibility', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const toggle = document.getElementById('avatarToggleButton');
    const card = document.getElementById('avatarCard');

    toggle.click();
    expect(card.classList.contains('collapsed')).toBe(true);
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(document.getElementById('avatarDiagVisible').textContent).toBe('no');

    toggle.click();
    expect(card.classList.contains('collapsed')).toBe(false);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById('avatarDiagVisible').textContent).toBe('yes');
  });

  it('missing avatar clip falls back safely and diagnostics show not loaded', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.avatarClips.idle = '/avatar/does-not-exist.mp4';
    ui.setAvatarState('idle', 'test-missing-clip');
    document.getElementById('avatarVideo').dispatchEvent(new Event('error'));

    expect(document.getElementById('avatarDiagLoaded').textContent).toBe('no');
    expect(document.getElementById('avatarFallback').classList.contains('hidden')).toBe(false);
  });

  it('avatar diagnostics are populated and voice label is synced', async () => {
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft Susan - English (United Kingdom)', lang: 'en-GB', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('avatarDiagEvent').textContent.length).toBeGreaterThan(0);
    expect(document.getElementById('avatarDiagClip').textContent.length).toBeGreaterThan(0);
    expect(document.getElementById('avatarVoiceLabel').textContent).toContain('Voice:');
  });

  it('explicit avatar media disable still forces fallback', async () => {
    document.body.dataset.avatarMedia = 'off';
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const video = document.getElementById('avatarVideo');
    expect(video.getAttribute('src')).toBeNull();
    expect(document.getElementById('avatarDiagClip').textContent).toContain('(disabled)');
    expect(document.getElementById('avatarFallback').classList.contains('hidden')).toBe(false);
  });

  it('avatar media remains enabled by default without an opt-out flag', async () => {
    delete document.body.dataset.avatarMedia;
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('avatarVideo').getAttribute('src')).toBe('/avatar/xoduz-idle.mp4');
    expect(document.getElementById('avatarDiagClip').textContent).not.toContain('(disabled)');
  });
});
