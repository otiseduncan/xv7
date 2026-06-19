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
    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(document.getElementById('promptInput').disabled).toBe(false);
  });


  it('does not render a persistent runtime status bar in the composer', async () => {
    global.fetch = createRuntimeFetchMock();

    new Xv7UI();
    await flushAsync();

    expect(document.getElementById('runtimeStatus')).toBeNull();
  });


  it('shows stop mode and a pending assistant card while a normal request is in flight and replaces it on success', async () => {
    const fetchMock = createRuntimeFetchMock({ source: 'runtime_override', activeProfile: 'local_test' });
    let resolveMessage;

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve) => {
          resolveMessage = () => resolve(okJson({
            session_id: 'session-1',
            current_persona: 'default',
            metadata: {},
            messages: [
              { role: 'user', content: 'Prompt in flight', metadata: {} },
              { role: 'assistant', content: 'Recovered after pending.', metadata: {} },
            ],
          }));
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    const sendButton = document.getElementById('sendButton');
    prompt.value = 'Prompt in flight';
    sendButton.click();
    await flushAsync();

    const pendingCard = document.querySelector('.pending-assistant');
    expect(sendButton.textContent).toBe('Stop');
    expect(sendButton.disabled).toBe(false);
    expect(sendButton.classList.contains('is-stop')).toBe(true);
    expect(prompt.disabled).toBe(true);
    expect(pendingCard?.getAttribute('data-runtime-phase')).toBe('thinking');
    expect(pendingCard?.textContent).toContain('Thinking');
    expect(typeof resolveMessage).toBe('function');

    resolveMessage();
    await flushAsync();

    expect(sendButton.textContent).toBe('Send');
    expect(sendButton.disabled).toBe(false);
    expect(sendButton.classList.contains('is-stop')).toBe(false);
    expect(prompt.disabled).toBe(false);
    expect(document.querySelector('.pending-assistant')).toBeNull();
    expect(document.querySelectorAll('.chat-card-assistant')).toHaveLength(1);
    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('Recovered after pending.');
  });


  it('shows website preview status in a pending assistant card and preserves site bundle rendering', async () => {
    const fetchMock = createRuntimeFetchMock();
    let resolveMessage;

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve) => {
          resolveMessage = () => resolve(okJson({
            session_id: 'session-1',
            current_persona: 'default',
            visible_text: 'Here is a 2-page site bundle for Thinking Test Hot Dog Cart.',
            site_bundle: {
              artifact_type: 'site_bundle',
              artifact_id: 'thinking-test-hot-dog-cart',
              title: 'Thinking Test Hot Dog Cart',
              slug: 'thinking-test-hot-dog-cart',
              entry: 'index.html',
              site_bundle: {
                files: [
                  { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
                  { path: 'menu.html', language: 'html', content: '<!doctype html><html><body>menu</body></html>' },
                ],
              },
            },
          }));
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Build me a website for Thinking Test Hot Dog Cart.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const pendingCard = document.querySelector('.pending-assistant');
    expect(pendingCard?.getAttribute('data-runtime-phase')).toBe('running');
    expect(pendingCard?.textContent).toContain('Building site preview');

    resolveMessage();
    await flushAsync();

    expect(document.querySelector('.pending-assistant')).toBeNull();
    expect(document.querySelector('.site-bundle-card')).toBeTruthy();
  });


  it('inlines local site bundle CSS and JS into preview iframe srcdoc', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const article = ui.appendMessageCard('assistant', 'Bundle ready.', null, null, '2026-06-11T00:00:10Z');
    ui.appendSiteBundleCard(article, {
      artifact_type: 'site_bundle',
      title: 'Styled Bundle',
      slug: 'styled-bundle',
      entry: 'index.html',
      active_file: 'index.html',
      files: [
        {
          path: 'index.html',
          language: 'html',
          content: [
            '<!doctype html>',
            '<html>',
            '<head>',
            '  <link rel="stylesheet" href="assets/site.css">',
            '</head>',
            '<body>',
            '  <main class="hero">Bundle preview</main>',
            '  <script src="assets/site.js"></script>',
            '</body>',
            '</html>',
          ].join('\n'),
        },
        {
          path: 'assets/site.css',
          language: 'css',
          content: '.hero { background: rgb(8, 12, 24); color: rgb(240, 250, 255); }',
        },
        {
          path: 'assets/site.js',
          language: 'javascript',
          content: 'window.__sitePreviewLoaded = true;',
        },
      ],
    });

    const card = document.querySelector('.site-bundle-card');
    expect(card).toBeTruthy();

    const codePanel = card.querySelector('.site-bundle-code-panel');
    const previewPanel = card.querySelector('.site-bundle-preview-panel');
    expect(codePanel?.hidden).toBe(false);
    expect(previewPanel?.hidden).toBe(true);

    const previewTab = [...card.querySelectorAll('.site-bundle-mode-button')].find((node) =>
      (node.textContent || '').trim() === 'Preview',
    );
    previewTab?.click();
    await flushAsync();

    const iframe = card.querySelector('iframe.code-artifact-preview-frame');
    const srcdoc = String(iframe?.getAttribute('srcdoc') || '');
    expect(codePanel?.hidden).toBe(true);
    expect(previewPanel?.hidden).toBe(false);
    expect(srcdoc).toContain('<style data-site-bundle-inline="assets/site.css">');
    expect(srcdoc).toContain('.hero { background: rgb(8, 12, 24); color: rgb(240, 250, 255); }');
    expect(srcdoc).toContain('<script data-site-bundle-inline="assets/site.js">window.__sitePreviewLoaded = true;</script>');
    expect(srcdoc).not.toContain('href="assets/site.css"');
    expect(srcdoc).not.toContain('src="assets/site.js"');

    const codeText = card.querySelector('.site-bundle-code-panel .code-artifact-codeview')?.textContent || '';
    expect(codeText).toContain('<link rel="stylesheet" href="assets/site.css">');
    expect(codeText).toContain('<script src="assets/site.js"></script>');
  });


  it('resolves relative bundle assets from nested HTML files', async () => {
    global.fetch = createRuntimeFetchMock();

    const ui = new Xv7UI();
    await flushAsync();

    const article = ui.appendMessageCard('assistant', 'Bundle ready.', null, null, '2026-06-11T00:00:11Z');
    ui.appendSiteBundleCard(article, {
      artifact_type: 'site_bundle',
      title: 'Nested Bundle',
      slug: 'nested-bundle',
      entry: 'pages/about.html',
      active_file: 'pages/about.html',
      files: [
        {
          path: 'pages/about.html',
          language: 'html',
          content: [
            '<!doctype html>',
            '<html>',
            '<head>',
            '  <link rel="stylesheet" href="../assets/site.css">',
            '</head>',
            '<body>',
            '  <main class="hero">About</main>',
            '</body>',
            '</html>',
          ].join('\n'),
        },
        {
          path: 'assets/site.css',
          language: 'css',
          content: '.hero { border: 1px solid rgb(11, 99, 180); }',
        },
      ],
    });

    const card = document.querySelector('.site-bundle-card');
    expect(card).toBeTruthy();

    const previewTab = [...card.querySelectorAll('.site-bundle-mode-button')].find((node) =>
      (node.textContent || '').trim() === 'Preview',
    );
    previewTab?.click();
    await flushAsync();

    const srcdoc = String(card.querySelector('iframe.code-artifact-preview-frame')?.getAttribute('srcdoc') || '');
    expect(srcdoc).toContain('<style data-site-bundle-inline="assets/site.css">');
    expect(srcdoc).toContain('.hero { border: 1px solid rgb(11, 99, 180); }');
  });


  it('shows checking repo status for operator prompts in a pending assistant card while active', async () => {
    const fetchMock = createRuntimeFetchMock();
    let resolveMessage;

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve) => {
          resolveMessage = () => resolve(fetchMock(input, init));
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'check the repo';
    document.getElementById('sendButton').click();
    await flushAsync();

    const pendingCard = document.querySelector('.pending-assistant');
    expect(pendingCard?.getAttribute('data-runtime-phase')).toBe('running');
    expect(pendingCard?.textContent).toContain('Checking repository...');

    resolveMessage();
    await flushAsync();

    expect(document.querySelector('.site-bundle-card')).toBeNull();
    expect(document.querySelector('.site-bundle-mode-button')).toBeNull();
  });


  it('shows running validation status for validation prompts in a pending assistant card while active', async () => {
    const fetchMock = createRuntimeFetchMock();
    let resolveMessage;

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve) => {
          resolveMessage = () => resolve(fetchMock(input, init));
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'run validation';
    document.getElementById('sendButton').click();
    await flushAsync();

    const pendingCard = document.querySelector('.pending-assistant');
    expect(pendingCard?.getAttribute('data-runtime-phase')).toBe('running');
    expect(pendingCard?.textContent).toContain('Running validation...');

    resolveMessage();
    await flushAsync();
  });


  it('shows commit/push approval check label for commit prompts in a pending assistant card while active', async () => {
    const fetchMock = createRuntimeFetchMock();
    let resolveMessage;

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve) => {
          resolveMessage = () => resolve(fetchMock(input, init));
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'commit and push';
    document.getElementById('sendButton').click();
    await flushAsync();

    const pendingCard = document.querySelector('.pending-assistant');
    expect(pendingCard?.textContent).toContain('Checking commit/push approval...');

    resolveMessage();
    await flushAsync();
  });


  it('stop click updates the pending assistant card and restores send mode', async () => {
    const fetchMock = createRuntimeFetchMock();

    global.fetch = vi.fn((input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            reject(new DOMException('Request cancelled.', 'AbortError'));
          }, { once: true });
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Hello X.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const sendButton = document.getElementById('sendButton');
    sendButton.click();
    await flushAsync();

    expect(sendButton.textContent).toBe('Send');
    expect(sendButton.classList.contains('is-stop')).toBe(false);
    expect(document.querySelector('.pending-assistant')).toBeNull();
    expect(document.querySelectorAll('.chat-card-assistant')).toHaveLength(1);
    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('Stopped. Request cancelled.');
  });


  it('shows failed status in the pending assistant card when a request errors and restores send mode', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return errorText(500, 'server exploded');
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Hello X.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const sendButton = document.getElementById('sendButton');
    expect(sendButton.textContent).toBe('Send');
    expect(sendButton.disabled).toBe(false);
    expect(document.querySelector('.pending-assistant')).toBeNull();
    const assistantCard = document.querySelector('.chat-card-assistant');
    expect(assistantCard?.getAttribute('data-runtime-phase')).toBe('failed');
    expect(assistantCard?.textContent).toContain('Failed: server exploded');
  });


  it('shows approval-required operator receipts without exposing hidden reasoning', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            operator_action_history: [
              {
                action_id: 'OP-COMMIT-1',
                action_name: 'operator_commit_report',
                status: 'needs_approval',
              },
            ],
          },
          messages: [
            { role: 'user', content: 'commit and push', metadata: {} },
            { role: 'assistant', content: 'Internal reasoning should never appear here.', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'commit and push';
    document.getElementById('sendButton').click();
    await flushAsync();

    const assistantText = document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent || '';
    expect(assistantText).not.toContain('Internal reasoning');
    expect(assistantText).not.toContain('chain-of-thought');
    expect(assistantText).toBe('Response withheld for safety.');
  });


  it('prefers the latest assistant role message over metadata fallback payload', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            last_assistant_payload: {
              visible_text: 'Metadata fallback text should not win.',
            },
          },
          messages: [
            { role: 'user', content: 'First', metadata: {} },
            { role: 'assistant', content: 'Assistant in messages should win.', metadata: {} },
            { role: 'tool', content: 'trailing non-assistant event', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Prefer assistant from messages';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('Assistant in messages should win.');
  });


  it('recovers from a malformed assistant response and still unlocks the composer', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {},
          messages: [],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Return a safe response even if the payload is malformed.';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(prompt.disabled).toBe(false);
    expect(document.querySelector('.chat-render-error')?.textContent).toContain('Xoduz response was received, but the UI could not render the assistant message.');
    expect(document.querySelector('.chat-render-error')?.textContent).toContain('response had messages array: true');
    expect(document.querySelector('.chat-render-error')?.textContent).toContain('assistant message found: false');
    expect(document.querySelector('.chat-render-error')?.textContent).toContain('last_assistant_payload found: false');
    expect(document.querySelectorAll('.chat-card-assistant')).toHaveLength(1);
    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('No assistant content returned.');
    expect(document.getElementById('alertBox').textContent).toContain('Recovered from malformed assistant response');
  });


  it('recovers from assistant artifact render failures without hanging the UI', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            last_assistant_payload: {
              visible_text: 'Here is your artifact.',
              code_artifacts: [
                {
                  filename: 'index.html',
                  language: 'html',
                  content: '<main>artifact</main>',
                },
              ],
            },
          },
          messages: [
            { role: 'user', content: 'Before artifact', metadata: {} },
            {
              role: 'assistant',
              content: 'Here is your artifact.',
              metadata: {
                visible_text: 'Here is your artifact.',
                code_artifacts: [
                  {
                    filename: 'index.html',
                    language: 'html',
                    content: '<main>artifact</main>',
                  },
                ],
              },
            },
          ],
        });
      }
      return fetchMock(input, init);
    });

    const ui = new Xv7UI();
    await flushAsync();
    vi.spyOn(ui, 'createCodeArtifactCard').mockImplementation(() => {
      throw new Error('render exploded');
    });

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Render an artifact safely even if the card render fails.';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(document.querySelector('.chat-render-error')?.textContent).toContain('The assistant response rendered, but the code artifact card could not be displayed.');
    expect(document.querySelectorAll('.chat-card-assistant')).toHaveLength(1);
    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('Here is your artifact.');
    expect(document.getElementById('alertBox').textContent).toContain('Recovered from assistant artifact rendering failure');
  });


  it('shows error feedback and unlocks composer for non-200 backend responses', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return errorText(500, 'backend exploded');
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    const prompt = document.getElementById('promptInput');
    prompt.value = 'Force a 500';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(prompt.disabled).toBe(false);
    expect(document.getElementById('alertBox').textContent).toContain('backend exploded');
  });


  it('times out hanging chat requests and restores the composer', async () => {
    const fetchMock = vi.fn((url, init = {}) => {
      const path = new URL(url, 'http://localhost').pathname;
      if (path === '/personas') {
        return Promise.resolve(okJson({ personas: { default: { name: 'default', model: 'qwen3:8b' } } }));
      }
      if (path === '/runtime/models' && (init.method || '').toUpperCase() === 'GET') {
        return Promise.resolve(okJson({
          available_profiles: ['balanced'],
          profiles: { balanced: { chat: 'qwen3:8b', reasoning: 'qwen3:8b', code: 'qwen3:8b', embedding: 'nomic-embed-text:latest' } },
          active_profile: 'balanced',
          profile_source: 'env',
          resolved_models: { chat: 'qwen3:8b', reasoning: 'qwen3:8b', code: 'qwen3:8b', embedding: 'nomic-embed-text:latest' },
          availability: { chat: true, reasoning: true, code: true, embedding: true },
          ollama: { reachable: true, base_url: 'http://ollama:11434', models: ['qwen3:8b'], error: null },
          config_error: null,
        }));
      }
      if (path === '/runtime/models/active' && (init.method || '').toUpperCase() === 'GET') {
        return Promise.resolve(okJson({
          active_profile: 'balanced',
          profile_source: 'env',
          resolved_models: { chat: 'qwen3:8b', reasoning: 'qwen3:8b', code: 'qwen3:8b', embedding: 'nomic-embed-text:latest' },
          role_aliases: { default: 'chat' },
          availability: { chat: true, reasoning: true, code: true, embedding: true },
          ollama: { reachable: true, base_url: 'http://ollama:11434', models: ['qwen3:8b'], error: null },
          config_error: null,
        }));
      }
      if (path === '/runtime/models/effective' && (init.method || '').toUpperCase() === 'GET') {
        return Promise.resolve(okJson({
          active_profile: 'balanced',
          profile_source: 'env',
          effective_models: { chat: 'qwen3:8b', reasoning: 'qwen3:8b', code: 'qwen3:8b', embedding: 'nomic-embed-text:latest' },
          role_aliases: { default: 'chat' },
          config_error: null,
        }));
      }
      if (path === '/api/sessions' && (init.method || '').toUpperCase() === 'POST') {
        return Promise.resolve(okJson({ session_id: 'session-1', current_persona: 'default', metadata: {}, messages: [] }));
      }
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return new Promise((resolve, reject) => {
          const onAbort = () => {
            const abortError = new Error('aborted');
            abortError.name = 'AbortError';
            reject(abortError);
          };
          init.signal?.addEventListener('abort', onAbort, { once: true });
        });
      }
      return Promise.resolve(errorText(404, `${init.method || 'GET'} ${path} not mocked`));
    });
    global.fetch = fetchMock;

    const ui = new Xv7UI();
    ui.chatMessageTimeoutMs = 1;
    await flushAsync();

    document.getElementById('promptInput').value = 'Hang long enough to trigger the timeout recovery.';
    document.getElementById('sendButton').click();
    await new Promise((resolve) => setTimeout(resolve, 10));
    await flushAsync();

    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(document.getElementById('alertBox').textContent).toContain('The request timed out or stayed pending too long. The UI recovered so you can retry.');
    expect(document.querySelectorAll('.chat-card-assistant')).toHaveLength(1);
    expect(document.querySelector('.pending-assistant')).toBeNull();
    expect(document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent).toContain('The request timed out or stayed pending too long. The UI recovered so you can retry.');
  });


});
