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


  it('voice selector prefers Google US (en-US) over European Susan', async () => {
    // Test that Google US voice is preferred over Microsoft Susan (European)
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Google US English', lang: 'en-US', default: false },
      { name: 'Microsoft Susan - English (United Kingdom)', lang: 'en-GB', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('voiceSelect').value).toBe('Google US English');
    expect(document.getElementById('voiceSettingsStatus').textContent).toContain('Using Google US English.');
    expect(document.getElementById('voiceDiagSelected').textContent).toBe('Google US English');
  });


  it('voice selector prefers en-US voices when Google US not available', async () => {
    // Test that en-US voices are preferred when Google US is not available
    window.speechSynthesis = buildSpeechSynthesisMock([
      { name: 'Microsoft David Desktop', lang: 'en-GB', default: false },
      { name: 'Microsoft Zira Desktop', lang: 'en-US', default: false },
    ]);
    window.SpeechSynthesisUtterance = function SpeechSynthesisUtterance(text) {
      this.text = text;
      this.onend = null;
      this.onerror = null;
    };
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('voiceSelect').value).toBe('Microsoft Zira Desktop');
    expect(document.getElementById('voiceSettingsStatus').textContent).toContain('Using Microsoft Zira Desktop.');
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


  it('renders why-this-answer metadata inside response details disclosure', async () => {
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

    const drawer = document.querySelector('.response-details-disclosure');
    expect(drawer).toBeTruthy();
    expect(drawer?.hasAttribute('open')).toBe(false);
    expect((drawer?.textContent || '').toLowerCase()).toContain('details');
    expect((drawer?.textContent || '').toLowerCase()).toContain('why this answer');
    expect(drawer?.textContent || '').toContain('active_focus_follow_up');
    expect(drawer?.textContent || '').toContain('XV7-FOCUS-0005');
    expect(drawer?.textContent || '').toContain('Focus');
  });


  it('renders prompt fidelity metadata inside response details disclosure', async () => {
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
          content: '<!doctype html><html><head><title>Tony Tavern</title><style>body{background:black;color:yellow}.hero{border-color:green}</style></head><body><h1>Tony Tavern</h1><p>Pet grooming services.</p></body></html>',
          prompt_fidelity: {
            status: 'repaired',
            requested_business_name: 'Tony Tavern',
            requested_business_type: 'grooming',
            requested_colors: ['black', 'yellow', 'green'],
            forbidden_terms_checked: ['Soggy Doggy', 'white', 'purple'],
            repair_attempted: true,
          },
        },
        policy_provenance: {
          artifact_generation: 'local_model',
          prompt_fidelity: {
            status: 'repaired',
            requested_business_name: 'Tony Tavern',
            requested_business_type: 'grooming',
            requested_colors: ['black', 'yellow', 'green'],
            repair_attempted: true,
          },
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const drawer = document.querySelector('.response-details-disclosure');
    expect(drawer).toBeTruthy();
    const text = drawer?.textContent || '';
    expect(text).toContain('prompt_fidelity_status');
    expect(text).toContain('repaired');
    expect(text).toContain('Tony Tavern');
    expect(text).toContain('black, yellow, green');
  });


});
