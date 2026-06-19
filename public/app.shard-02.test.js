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

  it('renders an inline code artifact card inside the assistant chat flow', async () => {
    global.fetch = createRuntimeFetchMock();

    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

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
    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
    expect(timelineCards[1].querySelector('.code-artifact-filename')?.textContent).toBe('src/demo.ts');
    expect(timelineCards[1].querySelector('.code-artifact-badge-language')?.textContent).toBe('TypeScript');
    expect(timelineCards[1].querySelector('.code-artifact-badge-status')?.textContent).toBe('Draft only');
    expect([...timelineCards[1].querySelectorAll('.code-artifact-button')].map((node) => node.textContent)).toEqual([
      'Copy',
      'Download',
      'Preview',
    ]);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', inline: 'nearest' });
    expect(timelineCards[1].querySelectorAll('.code-artifact-header')).toHaveLength(1);
    expect(timelineCards[1].querySelectorAll('.code-artifact-footer')).toHaveLength(1);
    expect(timelineCards[1].querySelector('.code-artifact-footer-copy')?.textContent).toContain('not been applied to the repo');

    const copyButton = timelineCards[1].querySelector('.code-artifact-button');
    const downloadButton = [...timelineCards[1].querySelectorAll('.code-artifact-button')][1];
    const createObjectURLSpy = vi.fn(() => 'blob:artifact');
    const revokeObjectURLSpy = vi.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURLSpy,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURLSpy,
    });
    const anchorClickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    copyButton?.click();
    downloadButton?.click();
    await flushAsync();

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('export const demo = 1;\n');
    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(anchorClickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(timelineCards[2].textContent || '').toContain('After artifact');
  });


  it('dedupes duplicate artifact metadata and fallback payloads into one card', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        const sharedArtifact = {
          filename: 'index.html',
          language: 'html',
          previewable: true,
          applied: false,
          content: '<!doctype html><html><body><main>Draft</main></body></html>',
        };
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            last_assistant_payload: {
              visible_text: 'Here is a draft HTML artifact for index.html.',
              code_artifact: sharedArtifact,
            },
          },
          messages: [
            { role: 'user', content: 'Before artifact', metadata: {} },
            {
              role: 'assistant',
              content: 'Here is a draft HTML artifact for index.html.',
              metadata: {
                code_artifacts: [sharedArtifact],
              },
            },
          ],
        });
      }
      return fetchMock(input, init);
    });

    const ui = new Xv7UI();
    await flushAsync();

    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    document.getElementById('promptInput').value = 'Generate a small HTML code artifact for a one-page website.';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
    expect(document.querySelectorAll('.code-artifact-header')).toHaveLength(1);
    expect(document.querySelectorAll('.code-artifact-footer')).toHaveLength(1);
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
    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
    expect(artifactCard.querySelectorAll('.code-artifact-header')).toHaveLength(1);
    expect(artifactCard.querySelectorAll('.code-artifact-footer')).toHaveLength(1);
    expect(artifactCard.querySelector('.code-artifact-code-panel')?.hidden).toBe(false);
    expect(artifactCard.querySelector('.code-artifact-preview-panel')?.hidden).toBe(true);
    expect(artifactCard.querySelector('.code-artifact-preview-panel')?.style.minHeight).toBe('480px');
    expect(artifactCard.querySelector('.code-artifact-code-panel')?.style.minHeight).toBe('480px');
    expect(artifactCard.querySelector('.code-artifact-tab.is-active')?.textContent).toBe('Code');

    const previewButton = [...artifactCard.querySelectorAll('.code-artifact-button')].find((node) =>
      (node.textContent || '').includes('Preview'),
    );
    expect(previewButton?.disabled).toBe(false);

    previewButton?.click();
    await flushAsync();

    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
    expect(artifactCard.querySelector('.code-artifact-code-panel')?.hidden).toBe(true);
    expect(artifactCard.querySelector('.code-artifact-preview-panel')?.hidden).toBe(false);
    expect(artifactCard.querySelector('.code-artifact-tab.is-active')?.textContent).toBe('Preview');
    expect(artifactCard.querySelector('iframe')?.getAttribute('srcdoc')).toContain('Preview works');

    const codeTab = [...artifactCard.querySelectorAll('.code-artifact-tab')].find((node) =>
      (node.textContent || '').includes('Code'),
    );
    codeTab?.click();
    await flushAsync();

    expect(artifactCard.querySelector('.code-artifact-code-panel')?.hidden).toBe(false);
    expect(artifactCard.querySelector('.code-artifact-preview-panel')?.hidden).toBe(true);
    expect(artifactCard.querySelector('.code-artifact-tab.is-active')?.textContent).toBe('Code');
  });


  it('renders row-based highlighted HTML source without executing raw source', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const htmlSource = [
      '<!doctype html>',
      '<html lang="en">',
      '<head>',
      '  <style>',
      '    body { margin: 0; color: #fff; font-family: "IBM Plex Mono"; }',
      '  </style>',
      '</head>',
      '<body>',
      '  <!-- cart hero -->',
      '  <main class="cart">Hot dogs</main>',
      '</body>',
      '</html>',
    ].join('\n');

    ui.appendMessageCard(
      'assistant',
      'HTML source ready.',
      null,
      {
        code_artifacts: [
          {
            filename: 'index.html',
            language: 'html',
            previewable: true,
            content: htmlSource,
          },
        ],
      },
      '2026-06-11T00:00:04Z',
    );

    const artifactCard = document.querySelector('.code-artifact-card');
    expect(artifactCard).toBeTruthy();
    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);

    const rows = [...artifactCard.querySelectorAll('.code-artifact-line')];
    expect(rows).toHaveLength(htmlSource.split('\n').length);
    expect(rows[0].querySelector('.code-artifact-line-number')?.textContent).toBe('1');
    expect(rows[0].querySelector('.code-artifact-line-code')).toBeTruthy();
    expect(rows.every((row) => row.querySelector('.code-artifact-line-number'))).toBe(true);
    expect(rows.every((row) => row.querySelector('.code-artifact-line-code'))).toBe(true);
    expect(rows.some((row) => row.classList.contains('is-odd'))).toBe(true);
    expect(rows.some((row) => row.classList.contains('is-even'))).toBe(true);
    expect(artifactCard.querySelectorAll('.code-token-html-tag').length).toBeGreaterThan(0);
    expect(artifactCard.querySelectorAll('.code-token-html-attr').length).toBeGreaterThan(0);
    expect(artifactCard.querySelectorAll('.code-token-html-string').length).toBeGreaterThan(0);
    expect(artifactCard.querySelectorAll('.code-token-css-property').length).toBeGreaterThan(0);
    expect(artifactCard.querySelectorAll('.code-token-css-string').length).toBeGreaterThan(0);
    expect(artifactCard.querySelectorAll('.code-token-html-comment').length).toBeGreaterThan(0);
    expect((artifactCard.textContent || '')).toContain('<main class="cart">');
    expect(artifactCard.querySelector('main')).toBe(null);

    const previewButton = [...artifactCard.querySelectorAll('.code-artifact-button')].find((node) =>
      (node.textContent || '').includes('Preview'),
    );
    previewButton?.click();
    await flushAsync();

    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
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
    expect(document.querySelectorAll('.code-artifact-card')).toHaveLength(1);
    expect(artifactCard.querySelector('.code-artifact-filename')?.textContent).toBe('index.html');
    expect(artifactCard.querySelector('.code-artifact-badge-language')?.textContent).toBe('HTML');
    expect(artifactCard.querySelector('.code-artifact-badge-status')?.textContent).toBe('Draft only');
    expect(artifactCard.querySelector('.code-artifact-button:last-child')?.textContent).toBe('Preview');
  });


  it('renders inline artifact card from real response metadata fallback path', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init?.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            last_assistant_payload: {
              visible_text: 'Here is a draft HTML artifact for index.html.',
              code_artifact: {
                type: 'code_artifact',
                filename: 'index.html',
                language: 'html',
                previewable: true,
                applied: false,
                content: '<!doctype html><html><body><main>Draft</main></body></html>',
              },
            },
          },
          messages: [
            { role: 'user', content: 'Before artifact', metadata: {} },
            { role: 'assistant', content: 'Here is a draft HTML artifact for index.html.', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    const ui = new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Generate a small HTML code artifact for a one-page website.';
    document.getElementById('sendButton').click();
    await flushAsync();

    ui.appendMessageCard('user', 'After artifact', null, null, '2026-06-11T00:00:05Z');

    const cards = [...document.querySelectorAll('.chat-card')];
    const artifactCard = cards[1].querySelector('.code-artifact-card');
    expect(cards[1].querySelector('.chat-visible-text')?.textContent).toBe('Here is a draft HTML artifact for index.html.');
    expect(artifactCard).toBeTruthy();
    expect(artifactCard.querySelector('.code-artifact-filename')?.textContent).toBe('index.html');
    expect(artifactCard.querySelector('.code-artifact-badge-language')?.textContent).toBe('HTML');
    expect(artifactCard.querySelector('.code-artifact-badge-status')?.textContent).toBe('Draft only');
    expect([...artifactCard.querySelectorAll('.code-artifact-button')].map((node) => node.textContent)).toEqual([
      'Copy',
      'Download',
      'Preview',
    ]);
    expect(artifactCard.querySelector('.code-artifact-footer-copy')?.textContent).toContain('not been applied to the repo');
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', inline: 'nearest' });
    expect(cards[2].textContent || '').toContain('After artifact');
  });


  it('renders one collapsed response details disclosure with operator info', async () => {
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

    const disclosures = [...document.querySelectorAll('.chat-card-assistant .response-details-disclosure')];
    expect(disclosures).toHaveLength(1);
    const disclosure = disclosures[0];
    expect(disclosure).toBeTruthy();
    expect(disclosure?.hasAttribute('open')).toBe(false);
    expect(disclosure?.querySelector('.response-details-summary')?.textContent).toContain('Details');
    expect(document.querySelector('.operator-result-disclosure')).toBeNull();
    expect(document.querySelector('.why-answer-drawer')).toBeNull();
    expect(document.querySelector('.receipt-details')).toBeNull();

    disclosure.open = true;
    await flushAsync();

    expect(document.querySelector('.site-bundle-card')).toBeNull();
    expect(document.querySelector('.site-bundle-mode-button')).toBeNull();
    const text = (disclosure?.textContent || '').toLowerCase();
    expect(text).toContain('trace summary');
    expect(text).toContain('response type');
    expect(text).toContain('operator');
    expect(text).toContain('action taken');
    expect(text).toContain('check the repo');
    expect(text).toContain('safety/approval');
    expect(text).toContain('approval required');
    expect(text).toContain('operator status');
    expect(text).toContain('repo_status op-1');
    expect(text).toContain('operator_status_report');
    expect(text).toContain('passed');
    expect(text).toContain('changed_files');
    expect(text).toContain('local_only');
    expect(text).toContain('commit_push');
    expect(text).toContain('commit_created=false');
    expect(text).toContain('push_performed=false');
    expect(text).toContain('why this answer');
    expect(text).toContain('model_used');
    expect(text).not.toContain('intent_class');
    expect(text).not.toContain('speech_act');
    expect(text).not.toContain('validation_commands');
  });


  it('renders safe trace metadata inside the single collapsed Details drawer', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Safe trace response.',
      null,
      {
        response_mode: 'operator_response',
        context_receipt: {
          context_receipts: [
            { layer: 'active_focus', record_id: 'XV7-FOCUS-0005' },
            { layer: 'knowledge', record_id: 'XV7-KNOWLEDGE-0006' },
          ],
        },
        operator_receipts: [
          {
            action_id: 'OP-TRACE-1',
            action_name: 'operator_validation_report',
            status: 'success',
            read_only: true,
            receipt_label: 'operator_validation_report OP-TRACE-1',
            summary: 'validation passed',
            safety: { allowed: true, read_only: true },
          },
        ],
        operator_result: {
          action_name: 'operator_validation_report',
          status: 'passed',
          changed_files: [],
          validation_commands_run: ['npm test'],
          validation_summary: {
            status: 'passed',
            passed: 12,
            failed: 0,
          },
          first_failure: '',
          safety_notes: [],
          local_only_files_warning: [],
          commit_push_state: {},
        },
        hidden_reasoning: 'PRIVATE_CHAIN_OF_THOUGHT',
        raw_model_prompt: 'RAW_PROMPT_SHOULD_NOT_RENDER',
        debug_blob: { secret: 'DEBUG_BLOB_SHOULD_NOT_RENDER' },
      },
      '2026-06-11T00:00:00Z',
    );

    const card = document.querySelector('.chat-card-assistant:last-child');
    const disclosures = [...card.querySelectorAll('.response-details-disclosure')];
    expect(disclosures).toHaveLength(1);
    expect(disclosures[0]?.hasAttribute('open')).toBe(false);

    const trace = disclosures[0]?.querySelector('.response-details-section');
    const detailText = (disclosures[0]?.textContent || '').toLowerCase();
    expect((trace?.textContent || '').toLowerCase()).toContain('trace summary');
    expect(detailText).toContain('response type');
    expect(detailText).toContain('operator_response');
    expect(detailText).toContain('action taken');
    expect(detailText).toContain('run validation');
    expect(detailText).toContain('status');
    expect(detailText).toContain('passed');
    expect(detailText).toContain('source layers');
    expect(detailText).toContain('focus, knowledge');
    expect(detailText).toContain('safety/approval');
    expect(detailText).toContain('read-only');
    expect(detailText).toContain('validation summary');
    expect(detailText).toContain('pass=12; fail=0');
    expect(detailText).not.toContain('private_chain_of_thought');
    expect(detailText).not.toContain('raw_prompt_should_not_render');
    expect(detailText).not.toContain('debug_blob_should_not_render');
  });


  it('suppresses placeholder operator result cards without meaningful payload', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Website artifact ready.',
      null,
      {
        operator_result: {
          action_name: 'operator_action',
          status: 'unknown',
          changed_files: [],
          validation_commands_run: [],
          safety_notes: [],
          local_only_files_warning: [],
          commit_push_state: {},
        },
      },
      new Date().toISOString(),
    );

    expect(document.querySelector('.response-details-disclosure')).toBeFalsy();
    expect((document.querySelector('.chat-card-assistant:last-child')?.textContent || '').toLowerCase()).not.toContain('operator_action');
    expect((document.querySelector('.chat-card-assistant:last-child')?.textContent || '').toLowerCase()).not.toContain('unknown');
  });


  it('hides default operator_action unknown metadata in response details', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Receipt response.',
      null,
      {
        operator_receipts: [
          {
            action_id: 'OP-UNKNOWN-1',
            action_name: 'operator_action',
            status: 'unknown',
            receipt_label: 'operator_action OP-UNKNOWN-1',
            read_only: true,
            summary: 'receipt available',
          },
        ],
      },
      '2026-06-11T00:00:00Z',
    );

    const drawer = document.querySelector('.chat-card-assistant:last-child .response-details-disclosure');
    expect(drawer).toBeTruthy();
    const text = (drawer?.textContent || '').toLowerCase();
    expect(text).toContain('receipt available');
    expect(text).not.toContain('action_name:operator_action');
    expect(text).not.toContain('status:unknown');
    expect(text).not.toContain('operator_action unknown');
  });


  it('does not render hidden reasoning in a second details drawer', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Visible answer.',
      'PRIVATE REASONING SHOULD NOT RENDER',
      {
        response_mode: 'direct_answer',
      },
      '2026-06-11T00:00:00Z',
    );

    const card = document.querySelector('.chat-card-assistant:last-child');
    expect([...card.querySelectorAll('details')]).toHaveLength(1);
    expect([...card.querySelectorAll('.response-details-disclosure')]).toHaveLength(1);
    expect(card.textContent || '').not.toContain('PRIVATE REASONING SHOULD NOT RENDER');
    expect(card.textContent || '').not.toContain('Cognitive Reasoning History');
  });


  it('run validation shows validation commands summary inside response details disclosure', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'run validation';
    document.getElementById('sendButton').click();
    await flushAsync();

    const cardText = (document.querySelector('.response-details-disclosure')?.textContent || '').toLowerCase();
    expect(cardText).toContain('operator_validation_report');
    expect(cardText).toContain('validation_commands');
    expect(cardText).toContain('python -m ruff format --check core tests scripts');
  });


  it('renders compact operator runtime cards for repo, validation, and commit/push flows', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Repo check complete.',
      null,
      {
        operator_result: {
          action_name: 'operator_status_report',
          status: 'passed',
          changed_files: ['public/app.js', 'public/styles.css'],
          validation_commands_run: [],
          first_failure: '',
          safety_notes: [],
          local_only_files_warning: [],
          repo_state: {
            branch: 'ui/p1-operator-runtime-cards',
            clean: true,
            sync: 'synced',
          },
          commit_push_state: {},
        },
      },
      '2026-06-11T00:00:00Z',
    );

    ui.appendMessageCard(
      'assistant',
      'Validation complete.',
      null,
      {
        operator_result: {
          action_name: 'operator_validation_report',
          status: 'passed',
          changed_files: [],
          validation_commands_run: ['python -m ruff check core tests scripts'],
          first_failure: '',
          safety_notes: [],
          local_only_files_warning: [],
          validation_summary: {
            status: 'passed',
            passed: 1,
            failed: 0,
          },
          commit_push_state: {},
        },
      },
      '2026-06-11T00:00:01Z',
    );

    ui.appendMessageCard(
      'assistant',
      'Commit and push request staged.',
      null,
      {
        operator_result: {
          action_name: 'operator_commit_report',
          status: 'needs_approval',
          changed_files: [],
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
      '2026-06-11T00:00:02Z',
    );

    const cards = [...document.querySelectorAll('.chat-card-assistant .operator-runtime-card')];
    expect(cards).toHaveLength(3);
    expect(cards[0]?.textContent || '').toContain('Check the repo');
    expect(cards[1]?.textContent || '').toContain('Run validation');
    expect(cards[2]?.textContent || '').toContain('Commit and push');
    expect(cards[2]?.textContent || '').toContain('Approval required');
    expect(cards[0]?.textContent || '').toContain('Branch');
    expect(cards[0]?.textContent || '').toContain('ui/p1-operator-runtime-cards');
    expect(cards[0]?.textContent || '').toContain('Working tree');
    expect(cards[0]?.textContent || '').toContain('Clean');
    expect(cards[0]?.textContent || '').toContain('Remote');
    expect(cards[0]?.textContent || '').toContain('Synced');
    expect(cards[1]?.textContent || '').toContain('Validation');
    expect(cards[1]?.textContent || '').toContain('passed');
    expect(cards[1]?.textContent || '').toContain('pass=1; fail=0');
    expect(cards[2]?.textContent || '').toContain('Approval');
    expect(cards[2]?.textContent || '').toContain('Required');
    expect(cards[2]?.textContent || '').toContain('commit=not created; push=not performed');
    expect((document.body.textContent || '').toLowerCase()).not.toContain('operator_action unknown');
  });


  it('stages final assistant response sections in progressive reveal order', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    vi.useFakeTimers();
    try {
      const article = ui.appendMessageCard(
        'assistant',
        'Repo check complete.',
        null,
        {
          operator_receipts: [
            {
              action_id: 'OP-1',
              action_name: 'repo_status',
              status: 'success',
              read_only: true,
              receipt_label: 'repo_status OP-1',
              summary: 'repo checked',
            },
          ],
          operator_result: {
            action_name: 'operator_status_report',
            status: 'passed',
            changed_files: [],
            validation_commands_run: [],
            first_failure: '',
            safety_notes: [],
            local_only_files_warning: [],
            commit_push_state: {},
          },
          model_use_receipt: {
            model_tag: 'qwen3:8b',
          },
        },
        '2026-06-11T00:00:00Z',
      );

      const body = article.querySelector('.response-reveal--body');
      const artifact = article.querySelector('.operator-runtime-card.response-reveal--artifact');
      const chipRow = article.querySelector('.receipt-chip-row.response-reveal--actions');
      const actions = article.querySelector('.message-actions.response-reveal--actions');
      const details = article.querySelector('.response-details-disclosure.response-reveal--details');
      const children = [...article.children];

      expect(body?.textContent).toContain('Repo check complete.');
      expect(artifact?.textContent).toContain('Check the repo');
      expect(details?.hasAttribute('open')).toBe(false);
      expect(children.indexOf(body)).toBeLessThan(children.indexOf(artifact));
      expect(children.indexOf(artifact)).toBeLessThan(children.indexOf(chipRow));
      expect(children.indexOf(actions)).toBeLessThan(children.indexOf(details));
      expect(body?.classList.contains('is-visible')).toBe(false);
      expect(artifact?.classList.contains('is-visible')).toBe(false);

      vi.advanceTimersByTime(0);
      expect(body?.classList.contains('is-visible')).toBe(true);
      expect(artifact?.classList.contains('is-visible')).toBe(false);

      vi.advanceTimersByTime(80);
      expect(artifact?.classList.contains('is-visible')).toBe(true);

      vi.advanceTimersByTime(60);
      expect(chipRow?.classList.contains('is-visible')).toBe(true);
      expect(actions?.classList.contains('is-visible')).toBe(true);
      expect(details?.classList.contains('is-visible')).toBe(false);

      vi.advanceTimersByTime(70);
      expect(details?.classList.contains('is-visible')).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });


  it('reduced motion reveals assistant response sections immediately', async () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    const article = ui.appendMessageCard(
      'assistant',
      'Commit and push request staged.',
      null,
      {
        operator_result: {
          action_name: 'operator_commit_report',
          status: 'needs_approval',
          changed_files: [],
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
      '2026-06-11T00:00:02Z',
    );

    const revealSections = [...article.querySelectorAll('.response-reveal')];
    expect(revealSections.length).toBeGreaterThan(0);
    expect(revealSections.every((section) => section.classList.contains('is-visible'))).toBe(true);
    expect(article.querySelector('.operator-runtime-card')?.textContent || '').toContain('Approval required');
  });


});
