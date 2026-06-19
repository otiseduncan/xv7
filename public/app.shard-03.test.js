// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Xv7UI } from './app.js';
import { buildDom } from './app-test-dom.js';
import { buildSpeechSynthesisMock, createRuntimeFetchMock, errorText, flushAsync, okJson } from './app-test-support.js';

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
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    window.localStorage.clear();
  });

  it('suppresses stale site bundle payloads on non-site operator responses', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const staleBundle = {
      artifact_type: 'site_bundle',
      files: [
        {
          path: 'index.html',
          language: 'html',
          content: '<!doctype html><html><body>stale</body></html>',
        },
      ],
      entry: 'index.html',
      active_file: 'index.html',
    };

    const resolved = ui.getMessageSiteBundle({
      operator_result: {
        action_name: 'operator_status_report',
        status: 'passed',
      },
      site_bundle: staleBundle,
    });

    expect(resolved).toBeNull();
  });


  it('omits Why this answer section when there are no meaningful why fields', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Operator-only metadata response.',
      null,
      {
        operator_result: {
          action_name: 'operator_status_report',
          status: 'passed',
          changed_files: ['public/app.js'],
          validation_commands_run: [],
          first_failure: '',
          safety_notes: [],
          local_only_files_warning: [],
          commit_push_state: {
            commit_created: false,
            push_performed: false,
            requires_separate_approval: true,
          },
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const drawer = document.querySelector('.chat-card-assistant:last-child .response-details-disclosure');
    expect(drawer).toBeTruthy();
    const detailText = (drawer?.textContent || '').toLowerCase();
    expect(detailText).toContain('operator result');
    expect(detailText).not.toContain('why this answer');
  });


  it('fix it shows needs_patch and first failure in response details disclosure', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'fix it';
    document.getElementById('sendButton').click();
    await flushAsync();

    const cardText = (document.querySelector('.response-details-disclosure')?.textContent || '').toLowerCase();
    expect(cardText).toContain('operator_repair_report');
    expect(cardText).toContain('needs_patch');
    expect(cardText).toContain('patch');
    expect(cardText).toContain('first_failure');
    expect(cardText).toContain('python -m pytest');
  });


  it('apply this patch without approval shows needs_approval in response details disclosure', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'apply this patch';
    document.getElementById('sendButton').click();
    await flushAsync();

    const cardText = (document.querySelector('.response-details-disclosure')?.textContent || '').toLowerCase();
    expect(cardText).toContain('operator_patch_report');
    expect(cardText).toContain('needs_approval');
    expect(cardText).toContain('approval');
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


  it('slash menu shows scan and mutation commands without requiring operator toggle', async () => {
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
    expect(menuTextNormal).toContain('/delete-file');

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


});
