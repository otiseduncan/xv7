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
    <select id="brainLibraryLayerFilter"><option value="all">all</option></select>
    <select id="brainLibraryStatusFilter"><option value="active">active</option></select>
    <select id="brainLibraryRelevanceFilter"><option value="all">all</option></select>
    <select id="brainLibrarySourceFilter"><option value="all">all</option></select>
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

function createCode8FetchMock() {
  const activeFocus = {
    id: 'XV7-FOCUS-0800',
    summary: 'browser/UI proof and receipt visibility',
  };
  const profiles = {
    balanced: {
      chat: 'qwen3:8b',
      reasoning: 'qwen3:14b',
      code: 'qwen3:14b',
      embedding: 'nomic-embed-text:latest',
    },
  };
  const activeFocusRecord = {
    record_id: activeFocus.id,
    layer: 'active_focus',
    title: 'Browser/UI proof and receipt visibility',
    summary: activeFocus.summary,
    body: activeFocus.summary,
    status: 'active',
    status_label: 'active',
    relevance_state: 'current',
    effective_relevance_state: 'current',
    priority: 300,
    tags: ['code8', 'ui-proof'],
    source: 'runtime_override',
    writable: true,
    updated_at: '2026-06-12T00:00:00Z',
    raw_record: {
      record_id: activeFocus.id,
      layer: 'active_focus',
      summary: activeFocus.summary,
      status: 'active',
    },
  };

  return vi.fn(async (url, init = {}) => {
    const method = (init.method || 'GET').toUpperCase();
    const parsed = new URL(url, 'http://localhost');
    const path = parsed.pathname;
    const query = parsed.searchParams;

    if (path === '/personas') {
      return okJson({ personas: { default: { name: 'default', model: profiles.balanced.chat } } });
    }

    if (path === '/runtime/models' && method === 'GET') {
      return okJson({
        available_profiles: ['balanced'],
        profiles,
        active_profile: 'balanced',
        profile_source: 'env',
        resolved_models: profiles.balanced,
        availability: { chat: true, reasoning: true, code: true, embedding: true },
        ollama: { reachable: true, base_url: 'http://ollama:11434', models: [profiles.balanced.chat], error: null },
        config_error: null,
      });
    }

    if (path === '/runtime/models/active' && method === 'GET') {
      return okJson({
        active_profile: 'balanced',
        profile_source: 'env',
        resolved_models: profiles.balanced,
        role_aliases: { default: 'chat' },
        availability: { chat: true, reasoning: true, code: true, embedding: true },
        ollama: { reachable: true, base_url: 'http://ollama:11434', models: [profiles.balanced.chat], error: null },
        config_error: null,
      });
    }

    if (path === '/runtime/models/effective' && method === 'GET') {
      return okJson({
        active_profile: 'balanced',
        profile_source: 'env',
        effective_models: profiles.balanced,
        role_aliases: { default: 'chat' },
        config_error: null,
      });
    }

    if (path === '/api/operator/commands' && method === 'GET') {
      return okJson({ operator_mode: query.get('operator_mode') === 'true', commands: [] });
    }

    if (path === '/runtime/brain/records' && method === 'GET') {
      return okJson({ count: 1, records: [activeFocusRecord] });
    }

    if (path === '/runtime/context/active' && method === 'GET') {
      return okJson({
        prompt: '',
        compact_receipt: activeFocus.summary,
        receipt: {
          record_ids: [activeFocus.id],
          context_receipts: [
            { layer: 'active_focus', record_id: activeFocus.id, summary: activeFocus.summary },
          ],
        },
      });
    }

    if (path === '/api/sessions' && method === 'POST') {
      return okJson({ session_id: 'session-1', current_persona: 'default', metadata: {}, messages: [] });
    }

    if (path === '/api/sessions/session-1/messages' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      const prompt = String(body.raw_text || '').toLowerCase();
      const visibleText = prompt.includes('what did i just change')
        ? `Your active focus is ${activeFocus.summary}.`
        : `Updating active focus to ${activeFocus.summary}.`;
      const assistantMetadata = {
        visible_text: visibleText,
        context_receipt: {
          compact: `Context receipt: Active Focus ${activeFocus.id}.`,
          record_ids: [activeFocus.id],
          context_receipts: [
            {
              record_id: activeFocus.id,
              layer: 'active_focus',
              title: 'Browser/UI proof and receipt visibility',
              receipt_label: `Active Focus ${activeFocus.id}`,
            },
          ],
        },
        operator_receipts: [],
        memory_receipts: [],
        model_use_receipt: {},
        policy_provenance: {
          policy_source: 'active_focus_instruction',
          response_mode: 'policy_only',
          focus_applied: true,
          active_focus_id: activeFocus.id,
        },
        response_mode: 'policy_only',
        fallback_used: false,
        focus_applied: true,
        active_focus_id: activeFocus.id,
        source_record_ids: [activeFocus.id],
        warnings: [],
      };

      return okJson({
        session_id: 'session-1',
        current_persona: 'default',
        metadata: { operator_action_history: [], model_use_receipt: {} },
        messages: [
          { role: 'user', content: String(body.raw_text || '') },
          {
            role: 'assistant',
            content: JSON.stringify({ raw_policy_payload: true, policy_provenance: assistantMetadata.policy_provenance }),
            metadata: assistantMetadata,
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

async function sendPrompt(ui, text) {
  const prompt = document.getElementById('promptInput');
  prompt.value = text;
  document.getElementById('sendButton').click();
  await flushAsync();
  await flushAsync();
  return [...document.querySelectorAll('.chat-card-assistant')].at(-1);
}

describe('Code 8 browser/UI receipt visibility proof', () => {
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
    navigator.clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    window.SpeechRecognition = undefined;
    window.webkitSpeechRecognition = undefined;
    window.speechSynthesis = undefined;
    window.SpeechSynthesisUtterance = undefined;
    window.localStorage.clear();
  });

  it('keeps active-focus policy provenance out of the visible assistant answer while showing compact focus receipts', async () => {
    global.fetch = createCode8FetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const assistantCard = await sendPrompt(ui, 'change your active focus to browser/UI proof and receipt visibility');
    const visibleText = assistantCard.querySelector('.chat-visible-text')?.textContent || '';
    const visibleLower = visibleText.toLowerCase();

    expect(visibleLower).toContain('updating active focus');
    expect(visibleLower).toContain('browser/ui proof and receipt visibility');
    expect(visibleText).not.toMatch(/policy_provenance|context_receipt|model_use_receipt|source_record_ids|qwen|model:/i);
    expect(visibleText).not.toContain('{');
    expect(visibleText).not.toContain('}');

    const chips = [...assistantCard.querySelectorAll('.receipt-chip')].map((node) => node.textContent || '');
    expect(chips).toContain('Focus: XV7-FOCUS-0800');
    expect(chips.some((text) => text.startsWith('Model:'))).toBe(false);

    expect(document.getElementById('chatReceiptModelTag').textContent).toBe('-');
    expect(document.getElementById('chatReceiptProfile').textContent).toBe('-');
  });

  it('keeps detailed source/provenance in the closed response details drawer', async () => {
    global.fetch = createCode8FetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const assistantCard = await sendPrompt(ui, 'what did I just change your focus to?');
    const whyDrawer = assistantCard.querySelector('.response-details-disclosure');
    const whyText = whyDrawer?.textContent || '';

    expect(whyDrawer).toBeTruthy();
    expect(whyDrawer.open).toBe(false);
    expect(whyDrawer.querySelector('summary')?.textContent).toBe('Details');
    expect(whyText.toLowerCase()).toContain('why this answer');
    expect(whyText).toContain('response_mode');
    expect(whyText).toContain('policy_only');
    expect(whyText).toContain('active_focus_id');
    expect(whyText).toContain('XV7-FOCUS-0800');
    expect(whyText).not.toContain('fallback_used');
    expect(whyText).toContain('context_includes_focus');
    expect(whyText).toContain('true');
  });

  it('copies only visible answer plus compact receipt summary, not raw provenance metadata', async () => {
    global.fetch = createCode8FetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const assistantCard = await sendPrompt(ui, 'what did I just change your focus to?');
    await ui.copySingleMessage(assistantCard);

    const copied = navigator.clipboard.writeText.mock.calls.at(-1)?.[0] || '';
    expect(copied).toContain('Xoduz:');
    expect(copied).toContain('Your active focus is browser/UI proof and receipt visibility.');
    expect(copied).toContain('Receipts:');
    expect(copied).toContain('- Focus: XV7-FOCUS-0800');
    expect(copied).not.toMatch(/policy_provenance|context_receipt|model_use_receipt|source_record_ids|qwen|model:/i);
  });
});
