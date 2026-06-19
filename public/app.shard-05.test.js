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

  it('renders fallback_reason and source_record_ids when they are provided', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Metadata-rich response',
      null,
      {
        source_record_ids: ['XV7-FOCUS-0004'],
        fallback_reason: 'operator_action',
        model_use_receipt: { model_tag: 'policy_only' },
        context_receipt: {
          context_receipts: [
            { layer: 'active_focus', record_id: 'XV7-FOCUS-0004' },
          ],
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const drawer = document.querySelector('.chat-card-assistant:last-child .response-details-disclosure');
    expect(drawer).toBeTruthy();
    const detailText = (drawer?.textContent || '').toLowerCase();
    expect(detailText).toContain('fallback_reason');
    expect(detailText).toContain('operator_action');
    expect(detailText).toContain('source_record_ids');
    expect(detailText).toContain('xv7-focus-0004');
  });


  it('renders artifact patch proposal with diff and draft/apply controls', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'I prepared a patch proposal from the active artifact. No files were changed.',
      null,
      {
        artifact_patch_proposal: {
          type: 'artifact_patch_proposal',
          proposal_id: 'patch-123',
          source_artifact_id: 'soggy-doggy-artifact:r2',
          filename: 'index.html',
          target_path: 'generated-sites/soggy-doggy/index.html',
          operation: 'create',
          language: 'html',
          applied: false,
          requires_confirmation: true,
          content: '<!doctype html><html><head><style>body{background:white}</style></head><body><h1>Soggy Doggy</h1></body></html>',
          diff: '--- /dev/null\n+++ b/generated-sites/soggy-doggy/index.html\n@@\n+<!doctype html>',
          validation: {
            status: 'passed',
            checks: [{ name: 'target_path_inside_repo', status: 'passed' }],
          },
        },
        policy_provenance: {
          artifact_patch: 'proposed',
          target_path: 'generated-sites/soggy-doggy/index.html',
          validation: 'passed',
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const panel = document.querySelector('.artifact-patch-proposal');
    expect(panel).toBeTruthy();
  expect(panel?.querySelector('.artifact-patch-proposal-header strong')?.textContent).toBe('Patch proposal');
    expect(panel?.textContent || '').toContain('generated-sites/soggy-doggy/index.html');
    expect(panel?.textContent || '').toContain('draft only / not applied');
    expect(panel?.textContent || '').toContain('validation: passed');
    expect((panel?.querySelector('.artifact-patch-diff')?.textContent || '')).toContain('+++ b/generated-sites/soggy-doggy/index.html');
    expect(panel?.querySelector('.artifact-patch-apply-button')?.textContent).toBe('Apply Patch');
  });


  it('renders post-apply verification, preview, and targeted validation details', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Post-apply verification passed for generated-sites/soggy-doggy/index.html. Checked 6 items with 0 failure(s).',
      null,
      {
        artifact_patch_proposal: {
          type: 'artifact_patch_proposal',
          proposal_id: 'patch-124',
          source_artifact_id: 'soggy-doggy-artifact:r3',
          filename: 'index.html',
          target_path: 'generated-sites/soggy-doggy/index.html',
          preview_path: '/generated-sites/soggy-doggy/index.html',
          operation: 'update',
          language: 'html',
          applied: true,
          requires_confirmation: true,
          content: '<!doctype html><html><head><style>body{background:white}</style></head><body><h1>Soggy Doggy</h1></body></html>',
          diff: '--- a/generated-sites/soggy-doggy/index.html\n+++ b/generated-sites/soggy-doggy/index.html\n@@\n+<!doctype html>',
          validation: {
            status: 'passed',
            checks: [{ name: 'target_path_inside_repo', status: 'passed' }],
          },
          post_apply_verification: {
            status: 'passed',
            checks: [{ name: 'file_exists', status: 'passed' }],
          },
          targeted_validation: {
            status: 'passed',
            checks: [{ name: 'html_inline_css', status: 'passed' }],
          },
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const panel = document.querySelector('.artifact-patch-proposal');
    expect(panel).toBeTruthy();
    expect(panel?.querySelector('.artifact-patch-proposal-header strong')?.textContent).toBe('Post-apply verification');
    expect(panel?.textContent || '').toContain('post-apply verify: passed');
    expect(panel?.textContent || '').toContain('targeted validation: passed');
    expect(panel?.textContent || '').toContain('preview: /generated-sites/soggy-doggy/index.html');
    expect(panel?.textContent || '').toContain('verify file_exists: passed');
    expect(panel?.textContent || '').toContain('targeted html_inline_css: passed');
    expect(panel?.querySelector('.artifact-patch-apply-button')).toBeNull();
  });


  it('renders preview ready, targeted validation, and full-test guard post-apply titles', async () => {
    global.fetch = createRuntimeFetchMock();
    const ui = new Xv7UI();
    await flushAsync();

    ui.appendMessageCard(
      'assistant',
      'Preview path is /generated-sites/tony-tavern/index.html. If the local app is running, open that route in your browser to view generated-sites/tony-tavern/index.html.',
      null,
      {
        artifact_patch_proposal: {
          type: 'artifact_patch_proposal',
          proposal_id: 'patch-125',
          source_artifact_id: 'tony-tavern-artifact:r1',
          filename: 'index.html',
          target_path: 'generated-sites/tony-tavern/index.html',
          preview_path: '/generated-sites/tony-tavern/index.html',
          operation: 'update',
          language: 'html',
          applied: true,
          requires_confirmation: true,
          content: '<!doctype html><html><head><style>body{background:black}</style></head><body><h1>Tony Tavern</h1></body></html>',
          diff: '--- a/generated-sites/tony-tavern/index.html\n+++ b/generated-sites/tony-tavern/index.html\n@@\n+<!doctype html>',
          validation: {
            status: 'passed',
            checks: [{ name: 'target_path_inside_repo', status: 'passed' }],
          },
          post_apply_verification: {
            status: '',
            checks: [],
          },
          targeted_validation: {
            status: '',
            checks: [],
          },
        },
        provenance: {
          artifact_patch: 'post_apply_preview',
          applied: true,
          requires_confirmation: true,
          target_path: 'generated-sites/tony-tavern/index.html',
          preview_path: '/generated-sites/tony-tavern/index.html',
          commit_created: false,
          push_performed: false,
        },
      },
      '2026-06-11T00:00:00Z',
    );

    ui.appendMessageCard(
      'assistant',
      'Targeted validation passed for generated-sites/tony-tavern/index.html. Only focused file checks were run; no broad test suites were executed.',
      null,
      {
        artifact_patch_proposal: {
          type: 'artifact_patch_proposal',
          proposal_id: 'patch-126',
          source_artifact_id: 'tony-tavern-artifact:r2',
          filename: 'index.html',
          target_path: 'generated-sites/tony-tavern/index.html',
          preview_path: '/generated-sites/tony-tavern/index.html',
          operation: 'update',
          language: 'html',
          applied: true,
          requires_confirmation: true,
          content: '<!doctype html><html><head><style>body{background:black}</style></head><body><h1>Tony Tavern</h1></body></html>',
          diff: '--- a/generated-sites/tony-tavern/index.html\n+++ b/generated-sites/tony-tavern/index.html\n@@\n+<!doctype html>',
          validation: {
            status: 'passed',
            checks: [{ name: 'target_path_inside_repo', status: 'passed' }],
          },
          targeted_validation: {
            status: 'passed',
            checks: [{ name: 'html_inline_css', status: 'passed' }],
          },
        },
        provenance: {
          artifact_patch: 'post_apply_targeted_validation',
          applied: true,
          requires_confirmation: true,
          target_path: 'generated-sites/tony-tavern/index.html',
          preview_path: '/generated-sites/tony-tavern/index.html',
          targeted_validation: 'passed',
          commit_created: false,
          push_performed: false,
        },
      },
      '2026-06-11T00:00:00Z',
    );

    ui.appendMessageCard(
      'assistant',
      'I did not run full tests automatically. I can only run the focused checks for the applied file in this lane. If you want full-suite validation, ask me explicitly and I will request confirmation before running it.',
      null,
      {
        artifact_patch_proposal: {
          type: 'artifact_patch_proposal',
          proposal_id: 'patch-127',
          source_artifact_id: 'tony-tavern-artifact:r3',
          filename: 'index.html',
          target_path: 'generated-sites/tony-tavern/index.html',
          operation: 'update',
          language: 'html',
          applied: true,
          requires_confirmation: true,
          content: '<!doctype html><html><head><style>body{background:black}</style></head><body><h1>Tony Tavern</h1></body></html>',
          diff: '--- a/generated-sites/tony-tavern/index.html\n+++ b/generated-sites/tony-tavern/index.html\n@@\n+<!doctype html>',
          validation: {
            status: 'passed',
            checks: [{ name: 'target_path_inside_repo', status: 'passed' }],
          },
        },
        provenance: {
          artifact_patch: 'full_test_guard',
          applied: true,
          requires_confirmation: true,
          target_path: 'generated-sites/tony-tavern/index.html',
          tests_run: false,
          commit_created: false,
          push_performed: false,
        },
      },
      '2026-06-11T00:00:00Z',
    );

    const panels = [...document.querySelectorAll('.artifact-patch-proposal')];
    const previewPanel = panels[0];
    const targetedPanel = panels[1];
    const guardPanel = panels[2];

    expect(previewPanel?.querySelector('.artifact-patch-proposal-header strong')?.textContent).toBe('Preview ready');
    expect(previewPanel?.querySelector('.artifact-patch-apply-button')).toBeNull();
    expect(targetedPanel?.querySelector('.artifact-patch-proposal-header strong')?.textContent).toBe('Targeted validation');
    expect(targetedPanel?.querySelector('.artifact-patch-apply-button')).toBeNull();
    expect(guardPanel?.querySelector('.artifact-patch-proposal-header strong')?.textContent).toBe('Full-test guard');
    expect(guardPanel?.querySelector('.artifact-patch-apply-button')).toBeNull();
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

  // ─── Code 21: site bundle frontend rendering tests ──────────────────────────


  it('renders a site bundle card with label, title, and file count', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          visible_text: 'Here is a 5-page site bundle for Tony\'s Tavern.',
          site_bundle: {
            artifact_type: 'site_bundle',
            artifact_id: 'tonys-tavern-bundle',
            title: "Tony's Tavern",
            slug: 'tonys-tavern',
            entry: 'index.html',
            site_bundle: {
              files: [
                { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
                { path: 'about.html', language: 'html', content: '<!doctype html><html><body>about</body></html>' },
                { path: 'menu.html', language: 'html', content: '<!doctype html><html><body>menu</body></html>' },
                { path: 'events.html', language: 'html', content: '<!doctype html><html><body>events</body></html>' },
                { path: 'contact.html', language: 'html', content: '<!doctype html><html><body>contact</body></html>' },
                { path: 'assets/site.css', language: 'css', content: 'body { background: #000; }' },
                { path: 'assets/site.js', language: 'javascript', content: 'console.log("ready");' },
              ],
            },
          },
          metadata: {},
          messages: [
            { role: 'user', content: 'create a website', metadata: {} },
            { role: 'assistant', content: 'Here is a 5-page site bundle.', metadata: {} },
          ],
        });
      }
      return fetchMock(input, init);
    });

    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    new Xv7UI();
    await flushAsync();

    document.getElementById('promptInput').value = 'create a 5 page website for Tony\'s Tavern';
    document.getElementById('sendButton').click();
    await flushAsync();

    const bundleCard = document.querySelector('.site-bundle-card');
    expect(bundleCard).toBeTruthy();
    expect(document.querySelector('.response-details-disclosure')).toBe(null);
    expect(bundleCard.querySelector('.site-bundle-label')?.textContent).toContain('Site bundle artifact');
    expect(bundleCard.querySelector('.site-bundle-title')?.textContent).toContain("Tony's Tavern");
    const meta = bundleCard.querySelector('.site-bundle-meta')?.textContent || '';
    expect(meta).toContain('7 file');
    expect(meta).toContain('index.html');
    expect(bundleCard.querySelector('.site-bundle-mode-button.is-active')?.textContent).toBe('Code');
    expect(bundleCard.querySelectorAll('.site-bundle-file-button').length).toBeGreaterThan(0);
    expect(bundleCard.querySelector('.site-bundle-files-disclosure')?.hasAttribute('open')).toBe(false);
    expect(bundleCard.querySelector('.site-bundle-workspace')).toBeNull();
    expect(bundleCard.querySelector('.site-bundle-list-panel')).toBeNull();
    expect(bundleCard.querySelector('.site-bundle-active-label')?.textContent).toContain('index.html');
    expect(bundleCard.querySelector('.site-bundle-code-panel')?.hidden).toBe(false);
    expect(bundleCard.querySelector('.site-bundle-preview-panel')?.hidden).toBe(true);

    const filesDisclosure = bundleCard.querySelector('.site-bundle-files-disclosure');
    filesDisclosure.open = true;
    await flushAsync();
    expect(filesDisclosure?.open).toBe(true);

    const fileItems = [...bundleCard.querySelectorAll('.site-bundle-file-item')];
    expect(fileItems.length).toBe(7);
    const filePaths = fileItems.map((el) => el.textContent || '');
    expect(filePaths.some((t) => t.includes('index.html'))).toBe(true);
    expect(filePaths.some((t) => t.includes('assets/site.css'))).toBe(true);

    const previewButton = [...bundleCard.querySelectorAll('.site-bundle-mode-button')].find((node) =>
      (node.textContent || '').includes('Preview'),
    );
    previewButton?.click();
    await flushAsync();

    expect(bundleCard.querySelector('.site-bundle-mode-button.is-active')?.textContent).toBe('Preview');
    expect(bundleCard.querySelector('.site-bundle-code-panel')?.hidden).toBe(true);
    expect(bundleCard.querySelector('.site-bundle-preview-panel')?.hidden).toBe(false);
    expect(bundleCard.querySelector('.site-bundle-preview-panel iframe')?.getAttribute('srcdoc')).toContain('<body>home</body>');

    expect(bundleCard.querySelector('.site-bundle-notice')?.textContent).toContain('7 file');
    expect(document.getElementById('sendButton').disabled).toBe(false);
    expect(document.getElementById('sendButton').textContent).toBe('Send');
  });


  it('renders a site bundle card when operator_result is an empty object', async () => {
    const fetchMock = createRuntimeFetchMock();
    global.fetch = vi.fn(async (input, init = {}) => {
      const path = new URL(input, 'http://localhost').pathname;
      if (path === '/api/sessions/session-1/messages' && (init.method || '').toUpperCase() === 'POST') {
        return okJson({
          session_id: 'session-1',
          current_persona: 'default',
          metadata: {
            last_assistant_payload: {
              visible_text: 'Here is a site bundle preview.',
              operator_result: {},
              operator_receipts: [],
              site_bundle: {
                artifact_type: 'site_bundle',
                artifact_id: 'preview-bundle',
                title: 'Preview Bundle',
                slug: 'preview-bundle',
                entry: 'index.html',
                site_bundle: {
                  files: [
                    { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
                    { path: 'assets/site.css', language: 'css', content: 'body { color: #fff; }' },
                  ],
                },
              },
            },
          },
          messages: [
            { role: 'assistant', content: 'Here is a site bundle preview.', metadata: {
              visible_text: 'Here is a site bundle preview.',
              operator_result: {},
              operator_receipts: [],
              site_bundle: {
                artifact_type: 'site_bundle',
                artifact_id: 'preview-bundle',
                title: 'Preview Bundle',
                slug: 'preview-bundle',
                entry: 'index.html',
                site_bundle: {
                  files: [
                    { path: 'index.html', language: 'html', content: '<!doctype html><html><body>home</body></html>' },
                    { path: 'assets/site.css', language: 'css', content: 'body { color: #fff; }' },
                  ],
                },
              },
            } },
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

    expect(document.querySelector('.site-bundle-card')).toBeTruthy();
  });


});
