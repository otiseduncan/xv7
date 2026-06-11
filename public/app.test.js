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
    <textarea id="promptInput"></textarea>
    <button id="micButton"></button>
    <button id="sendButton"></button>
    <div id="voiceStatus"></div>
    <p id="voiceSettingsStatus"></p>
    <select id="voiceSelect"></select>
    <input id="voiceVolume" type="range" />
    <input id="voiceRate" type="range" />
    <input id="voicePitch" type="range" />
    <input id="voiceMute" type="checkbox" />
    <button id="voiceTestButton"></button>
    <button id="voiceStopButton"></button>
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
  `;
}

function createRuntimeFetchMock(options = {}) {
  const state = {
    activeProfile: options.activeProfile || 'balanced',
    source: options.source || 'env',
    reachable: options.reachable ?? true,
    failModels: options.failModels ?? false,
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
            action_name: 'docker_compose_ps',
            status: 'failed',
            mode: 'read_only',
            target: '/workspace',
            receipt_label: 'docker_compose_ps OP-2',
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
      (node.textContent || '').includes('docker_compose_ps failed'),
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
    expect(audioButtons[0].getAttribute('aria-label')).toBe('Read assistant response aloud');

    audioButtons[0].click();
    expect(window.speechSynthesis.speak).toHaveBeenCalledTimes(1);
    expect(window.speechSynthesis.speak.mock.calls[0][0].text).toContain('The repo is on main. The working tree is not clean.');
    expect(window.speechSynthesis.speak.mock.calls[0][0].text).not.toContain('Operator:');
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
    audioButton.click();
    await flushAsync();

    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    expect(audioButton.getAttribute('aria-label')).toBe('Read assistant response aloud');
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

    const audioButton = document.querySelector('.message-audio-button');
    audioButton.click();
    await flushAsync();

    ui.activeUtterance.onend();
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

    const audioButton = document.querySelector('.message-audio-button');
    audioButton.click();
    await flushAsync();

    ui.activeUtterance.onerror();
    await flushAsync();

    expect(ui.voiceState.speaking).toBe(false);
    expect(ui.voiceState.lastVoiceError).toContain('Browser blocked voice playback. Try clicking Test Voice again.');
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

    const audioButton = document.querySelector('.message-audio-button');
    audioButton.click();
    await flushAsync();
    ui.activeUtterance.onend();
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
    expect(utterance.text).toBe('Hello Otis. I am Xoduz. This is my selected voice.');
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
    expect(copiedText).toContain('Operator receipt:');
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
    expect(assistantCopy).toContain('Receipt:');
    expect(document.getElementById('copyToast').textContent).toContain('Copied.');
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
});
