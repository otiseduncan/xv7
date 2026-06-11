// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Xv7UI } from './app.js';

function okJson(payload) {
  return {
    ok: true,
    status: 200,
    async json() {
      return payload;
    },
    async text() {
      return JSON.stringify(payload);
    },
  };
}

function errorText(status, message) {
  return {
    ok: false,
    status,
    async json() {
      return { detail: message };
    },
    async text() {
      return message;
    },
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
    <section id="chatTimeline"></section>
    <textarea id="promptInput"></textarea>
    <button id="sendButton"></button>

    <span id="modelActiveProfile"></span>
    <span id="modelProfileSource"></span>
    <span id="modelOllamaReachable"></span>
    <span id="modelEffectiveChat"></span>
    <select id="modelProfileSelect"></select>
    <input id="modelApiKeyInput" type="password" />
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
    const path = new URL(url).pathname;

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

    if (path === '/runtime/models/active' && method === 'PUT') {
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

    if (path === '/runtime/models/active' && method === 'DELETE') {
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

    if (path === '/sessions' && method === 'POST') {
      return okJson({ session_id: 'session-1', current_persona: 'default', metadata: {}, messages: [] });
    }

    if (path === '/sessions/session-1/messages' && method === 'POST') {
      return okJson({
        session_id: 'session-1',
        current_persona: 'default',
        metadata: {
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
          { role: 'assistant', content: 'XV7_MODEL_PROOF' },
        ],
      });
    }

    return errorText(404, `${method} ${path} not mocked`);
  });
}

function headerValue(headers, name) {
  if (!headers) return undefined;
  if (typeof headers.get === 'function') {
    return headers.get(name);
  }
  return headers[name];
}

async function flushAsync() {
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await Promise.resolve();
}

describe('ModelProfileControl', () => {
  beforeEach(() => {
    buildDom();
    window.__XV7_DISABLE_AUTO_INIT = true;
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

  it('does not display raw API key text in panel output', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    const apiKeyInput = document.getElementById('modelApiKeyInput');
    apiKeyInput.value = 'super-secret-key';
    apiKeyInput.dispatchEvent(new Event('input'));

    const pageText = document.body.textContent;
    expect(pageText.includes('super-secret-key')).toBe(false);
  });

  it('apply action sends PUT /runtime/models/active with API key header', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const select = document.getElementById('modelProfileSelect');
    select.value = 'local_test';
    select.dispatchEvent(new Event('change'));

    const apiKeyInput = document.getElementById('modelApiKeyInput');
    apiKeyInput.value = 'apply-key';
    apiKeyInput.dispatchEvent(new Event('input'));

    document.getElementById('modelApplyButton').click();
    await flushAsync();

    const putCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0]).pathname === '/runtime/models/active' && (init.method || '').toUpperCase() === 'PUT';
    });

    expect(putCalls.length).toBe(1);
    expect(headerValue(putCalls[0][1].headers, 'X-XV7-API-Key')).toBe('apply-key');
    expect(JSON.parse(putCalls[0][1].body)).toEqual({
      profile: 'local_test',
      require_available: true,
    });
    expect(document.getElementById('modelEffectiveChat').textContent).toBe('qwen3:14b');
  });

  it('renders model-use receipt after send action', async () => {
    const fetchMock = createRuntimeFetchMock({ source: 'runtime_override', activeProfile: 'local_test' });
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const apiKeyInput = document.getElementById('modelApiKeyInput');
    apiKeyInput.value = 'chat-key';
    apiKeyInput.dispatchEvent(new Event('input'));

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Return exactly: XV7_MODEL_PROOF';
    document.getElementById('sendButton').click();
    await flushAsync();

    const sessionCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0]).pathname === '/sessions' && (init.method || '').toUpperCase() === 'POST';
    });
    const messageCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0]).pathname === '/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST';
    });

    expect(headerValue(sessionCalls[0][1].headers, 'X-XV7-API-Key')).toBe('chat-key');
    expect(headerValue(messageCalls[0][1].headers, 'X-XV7-API-Key')).toBe('chat-key');

    expect(document.getElementById('chatReceiptProfile').textContent).toBe('local_test');
    expect(document.getElementById('chatReceiptModelTag').textContent).toBe('qwen3:14b');
    expect(document.getElementById('chatReceiptRole').textContent).toBe('chat');
    expect(document.getElementById('chatReceiptSelectionSource').textContent).toBe('registry_effective_profile');
    expect(document.getElementById('chatReceiptRequestId').textContent).toBe('req-1');
  });

  it('does not attempt chat send without API key', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Return exactly: XV7_MODEL_PROOF';
    document.getElementById('sendButton').click();
    await flushAsync();

    const sessionCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0]).pathname === '/sessions' && (init.method || '').toUpperCase() === 'POST';
    });

    expect(sessionCalls.length).toBe(0);
    expect(document.getElementById('alertBox').textContent).toContain('API key is required for chat');
  });

  it('clear action sends DELETE /runtime/models/active with API key header', async () => {
    const fetchMock = createRuntimeFetchMock({ source: 'runtime_override', activeProfile: 'local_test' });
    global.fetch = fetchMock;

    new Xv7UI();
    await flushAsync();

    const apiKeyInput = document.getElementById('modelApiKeyInput');
    apiKeyInput.value = 'clear-key';
    apiKeyInput.dispatchEvent(new Event('input'));

    document.getElementById('modelClearButton').click();
    await flushAsync();

    const deleteCalls = fetchMock.mock.calls.filter((call) => {
      const init = call[1] || {};
      return new URL(call[0]).pathname === '/runtime/models/active' && (init.method || '').toUpperCase() === 'DELETE';
    });

    expect(deleteCalls.length).toBe(1);
    expect(headerValue(deleteCalls[0][1].headers, 'X-XV7-API-Key')).toBe('clear-key');
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

  it('does not attempt mutation without API key', async () => {
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
      return new URL(call[0]).pathname === '/runtime/models/active' && (init.method || '').toUpperCase() === 'PUT';
    });

    expect(putCalls.length).toBe(0);
    expect(document.getElementById('modelApplyButton').disabled).toBe(true);
  });
});
