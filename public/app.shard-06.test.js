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

  it('does not render preview/code artifact cards for text-only website responses without structured metadata', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {},
          messages: [
            {
              role: 'assistant',
              content: 'Here is a 4-page site bundle for Demo Site. Files: index.html, about.html, services.html, contact.html.',
              metadata: {
                visible_text: 'Here is a 4-page site bundle for Demo Site. Files: index.html, about.html, services.html, contact.html.',
                site_bundle: {},
                code_artifact: {},
                code_artifacts: [],
              },
            },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'Generate a website preview';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.querySelector('.site-bundle-card')).toBeNull();
    expect(document.querySelector('.code-artifact-card')).toBeNull();
    expect((document.querySelector('.chat-card-assistant .chat-visible-text')?.textContent || '').toLowerCase()).toContain('site bundle');
  });


  it('does not break single-file artifact card when site_bundle absent', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {},
          messages: [
            { role: 'user', content: 'create an artifact', metadata: {} },
            {
              role: 'assistant',
              content: 'Here is your artifact.',
              metadata: {
                code_artifacts: [
                  { filename: 'index.html', language: 'html', content: '<!doctype html><html><body>Tony\'s Tavern</body></html>' },
                ],
              },
            },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'create a html artifact';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.querySelector('.site-bundle-card')).toBeFalsy();
    expect(document.querySelector('.code-artifact-card')).toBeTruthy();
    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
  });


  it('site bundle render failure shows diagnostic and recovers send state', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          visible_text: 'Here is the bundle.',
          site_bundle: {
            artifact_type: 'site_bundle',
            title: 'Tony\'s Tavern',
            slug: 'tonys-tavern',
            entry: 'index.html',
            site_bundle: {
              files: [
                { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
              ],
            },
          },
          metadata: {},
          messages: [
            { role: 'user', content: 'create', metadata: {} },
            { role: 'assistant', content: 'bundle', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    const ui = new Xv7UI();
    await flushAsync();

    vi.spyOn(ui, 'appendSiteBundleCard').mockImplementation(() => {
      throw new Error('bundle render failed');
    });

    document.getElementById('promptInput').value = 'create a website for Tony';
    document.getElementById('sendButton').click();
    await flushAsync();

    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
    expect(document.querySelector('.chat-render-error')).toBeTruthy();
  });


  it('renders editor and preview panels for explicit products/faq site bundle prompts', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          visible_text: 'Here is a 5-page website artifact for Smoky Joe\'s Vape and CBD.',
          site_bundle: {
            artifact_type: 'site_bundle',
            artifact_id: 'smoky-joes-vape-and-cbd-bundle',
            title: "Smoky Joe's Vape and CBD",
            slug: 'smoky-joes-vape-and-cbd',
            entry: 'index.html',
            active_file: 'index.html',
            preview_entrypoint: 'index.html',
            render_mode: 'code_editor_preview',
            files: [
              { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
              { path: 'products.html', language: 'html', content: '<!doctype html><html><body>products</body></html>' },
              { path: 'about.html', language: 'html', content: '<!doctype html><html><body>about</body></html>' },
              { path: 'faq.html', language: 'html', content: '<!doctype html><html><body>faq</body></html>' },
              { path: 'contact.html', language: 'html', content: '<!doctype html><html><body>contact</body></html>' },
              { path: 'assets/site.css', language: 'css', content: 'body { background: #050805; color: #d9ffe0; }' },
              { path: 'assets/site.js', language: 'javascript', content: 'console.log("ready");' },
            ],
            route_manifest: [
              { path: 'index.html', label: 'Home', route: '/', is_entry: true },
              { path: 'products.html', label: 'Products', route: '/products.html', is_entry: false },
              { path: 'about.html', label: 'About', route: '/about.html', is_entry: false },
              { path: 'faq.html', label: 'FAQ', route: '/faq.html', is_entry: false },
              { path: 'contact.html', label: 'Contact', route: '/contact.html', is_entry: false },
            ],
          },
          metadata: {},
          messages: [
            {
              role: 'user',
              content: 'Build a multi-page website for Smoky Joe\'s Vape and CBD. Include Home, Products, About, FAQ, and Contact pages.',
              metadata: {},
            },
            { role: 'assistant', content: 'Site artifact ready.', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value =
      'Build a multi-page website for Smoky Joe\'s Vape and CBD. Include Home, Products, About, FAQ, and Contact pages.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const artifacts = [...document.querySelectorAll('.code-artifact-card')];
    // Site bundle messages must NOT produce individual per-file code artifact cards.
    expect(artifacts.length).toBe(0);

    // Instead, one unified site-bundle-card should be rendered.
    const bundleCards = [...document.querySelectorAll('.site-bundle-card')];
    expect(bundleCards.length).toBeGreaterThan(0);
    const bundleCard = bundleCards[0];
    expect(bundleCard.querySelector('.site-bundle-files-disclosure')?.hasAttribute('open')).toBe(false);
    expect(bundleCard.querySelector('.site-bundle-workspace')).toBeNull();
    expect(bundleCard.querySelector('.site-bundle-list-panel')).toBeNull();
    expect(bundleCard.querySelector('.site-bundle-mode-button.is-active')?.textContent).toBe('Code');
    expect(bundleCard.querySelector('.site-bundle-preview-panel')?.hidden).toBe(true);

    // The site bundle card file list must include products.html and faq.html.
    const filesDisclosure = bundleCard.querySelector('.site-bundle-files-disclosure');
    filesDisclosure.open = true;
    await flushAsync();

    const fileItems = [...bundleCard.querySelectorAll('.site-bundle-file-item')];
    const filePaths = fileItems.map((li) => li.textContent.trim().split(' ')[0]);
    expect(filePaths).toContain('products.html');
    expect(filePaths).toContain('faq.html');
    expect(filePaths).not.toContain('services.html');
    expect(filePaths).not.toContain('gallery.html');

    const productsButton = [...bundleCard.querySelectorAll('.site-bundle-file-button')].find((button) =>
      (button.textContent || '').includes('Products'),
    );
    expect(productsButton).toBeTruthy();
    productsButton?.click();
    await flushAsync();
    expect(bundleCard.querySelector('.site-bundle-active-label')?.textContent).toContain('products.html');

    const previewButton = [...bundleCard.querySelectorAll('.site-bundle-mode-button')].find((button) =>
      (button.textContent || '').includes('Preview'),
    );
    expect(previewButton?.disabled).toBe(false);
    previewButton?.click();
    await flushAsync();

    expect(bundleCard.querySelector('.site-bundle-preview-panel')?.hidden).toBe(false);
    expect(bundleCard.querySelector('.site-bundle-preview-panel iframe')?.getAttribute('srcdoc')).toContain('<body>products</body>');
  });


  it('renders revised artifact content for premium + Specials follow-up prompts', async () => {
    const fetchMock = createRuntimeFetchMock();
    let messagePostCount = 0;
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        messagePostCount += 1;
        if (messagePostCount === 1) {
          return okJson({
            session_id: 'session-1',
            current_persona: 'default',
            metadata: {},
            messages: [
              { role: 'user', content: "Build a one-page website for Harry's Hot Dogs.", metadata: {} },
              {
                role: 'assistant',
                content: 'Here is a draft HTML artifact for index.html.',
                metadata: {
                  code_artifact: {
                    type: 'code_artifact',
                    filename: 'index.html',
                    language: 'html',
                    previewable: true,
                    applied: false,
                    content:
                      "<!doctype html><html><body><main><h1>Harry's Hot Dogs</h1><p>Classic street-style hot dogs served fast.</p></main></body></html>",
                  },
                },
              },
            ],
          });
        }
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {},
          messages: [
            { role: 'user', content: "Build a one-page website for Harry's Hot Dogs.", metadata: {} },
            {
              role: 'assistant',
              content: 'Here is a draft HTML artifact for index.html.',
              metadata: {
                code_artifact: {
                  type: 'code_artifact',
                  filename: 'index.html',
                  language: 'html',
                  previewable: true,
                  applied: false,
                  content:
                    "<!doctype html><html><body><main><h1>Harry's Hot Dogs</h1><p>Classic street-style hot dogs served fast.</p></main></body></html>",
                },
              },
            },
            { role: 'user', content: 'Make this site look more premium and add a Specials section.', metadata: {} },
            {
              role: 'assistant',
              content: 'Updated the draft artifact with premium styling and a Specials section.',
              metadata: {
                code_artifact: {
                  type: 'code_artifact',
                  filename: 'index.html',
                  language: 'html',
                  previewable: true,
                  applied: false,
                  content:
                    "<!doctype html><html><body><main><h1 class='premium'>Harry's Hot Dogs</h1><p>Premium presentation.</p><section class='specials'><h2>Specials</h2><ul><li>Classic Dog Combo</li></ul></section></main></body></html>",
                },
              },
            },
          ],
        });
      }
      return fetchMock(input, init);
    });

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = "Build a one-page website for Harry's Hot Dogs.";
    document.getElementById('sendButton').click();
    await flushAsync();

    document.getElementById('promptInput').value = 'Make this site look more premium and add a Specials section.';
    document.getElementById('sendButton').click();
    await flushAsync();

    const artifacts = [...document.querySelectorAll('.code-artifact-card')];
    expect(artifacts.length).toBeGreaterThan(1);

    const latest = artifacts[artifacts.length - 1];
    expect(latest.getAttribute('data-filename')).toBe('index.html');
    expect((latest.textContent || '').toLowerCase()).toContain('specials');
    expect((latest.textContent || '').toLowerCase()).toContain('premium');

    const previewButton = [...latest.querySelectorAll('.code-artifact-button')].find((node) =>
      (node.textContent || '').includes('Preview'),
    );
    previewButton?.click();
    await flushAsync();

    const iframe = latest.querySelector('iframe');
    expect(iframe?.getAttribute('srcdoc') || '').toContain('Specials');
    expect(iframe?.getAttribute('srcdoc') || '').toContain('premium');
  });


});
