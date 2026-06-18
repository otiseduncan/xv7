const state = {
  sessionId: null,
  stageId: null,
  lastDraftStageId: null,
};

const els = {
  sessionLabel: document.getElementById('sessionLabel'),
  newSessionButton: document.getElementById('newSessionButton'),
  messages: document.getElementById('messages'),
  requestText: document.getElementById('requestText'),
  sendButton: document.getElementById('sendButton'),
  activeStageLabel: document.getElementById('activeStageLabel'),
  refreshStageButton: document.getElementById('refreshStageButton'),
  refreshDraftButton: document.getElementById('refreshDraftButton'),
  previewButton: document.getElementById('previewButton'),
  validateButton: document.getElementById('validateButton'),
  preparePackageButton: document.getElementById('preparePackageButton'),
  cancelStageButton: document.getElementById('cancelStageButton'),
  operatorContent: document.getElementById('operatorContent'),
  attachContentButton: document.getElementById('attachContentButton'),
  kernelOutput: document.getElementById('kernelOutput'),
  copyOutputButton: document.getElementById('copyOutputButton'),
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setOutput(value) {
  els.kernelOutput.textContent = typeof value === 'string' ? value : pretty(value);
}

function setStageId(stageId) {
  state.stageId = stageId || null;
  els.activeStageLabel.textContent = `stage: ${state.stageId || 'none'}`;
}

function appendMessage(role, text) {
  const article = document.createElement('article');
  const roleClass = role === 'operator' ? 'border-xv7-primary/50 bg-xv7-primary/10' : 'border-xv7-line/50 bg-slate-950/40';
  article.className = `rounded-xl border ${roleClass} p-3 text-sm text-slate-200`;
  const label = document.createElement('p');
  label.className = 'mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-xv7-glow';
  label.textContent = role;
  const body = document.createElement('pre');
  body.className = 'whitespace-pre-wrap font-sans text-sm leading-relaxed';
  body.textContent = text || '';
  article.append(label, body);
  els.messages.appendChild(article);
  els.messages.scrollTop = els.messages.scrollHeight;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return response.json();
}

async function run(label, task) {
  setOutput(`${label}...`);
  try {
    const result = await task();
    setOutput(result);
    return result;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setOutput(`ERROR: ${message}`);
    throw error;
  }
}

async function ensureSession() {
  if (state.sessionId) {
    return state.sessionId;
  }

  const session = await api('/sessions', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  state.sessionId = session.session_id;
  els.sessionLabel.textContent = `session: ${state.sessionId}`;
  return state.sessionId;
}

async function newSession() {
  const session = await api('/sessions', {
    method: 'POST',
    body: JSON.stringify({}),
  });
  state.sessionId = session.session_id;
  els.sessionLabel.textContent = `session: ${state.sessionId}`;
  setStageId(null);
  appendMessage('system', `New session: ${state.sessionId}`);
  return session;
}

function extractAssistantText(response) {
  const messages = Array.isArray(response?.messages) ? response.messages : [];
  const last = messages[messages.length - 1];
  return last?.content || '';
}

async function sendToX() {
  const rawText = els.requestText.value.trim();
  if (!rawText) {
    setOutput('Enter a request first.');
    return null;
  }

  const sessionId = await ensureSession();
  appendMessage('operator', rawText);

  const response = await api(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    body: JSON.stringify({ raw_text: rawText, operator_mode: false }),
  });

  const assistantText = extractAssistantText(response);
  appendMessage('x', assistantText);

  const staged = response?.metadata?.x_kernel_action_stage;
  if (staged?.stage_id) {
    setStageId(staged.stage_id);
  }

  setOutput(response?.metadata || response);
  return response;
}

async function refreshLatestStage() {
  const result = await api('/x-kernel/stages/latest');
  const stageId = result?.stage?.stage_id;
  if (stageId) {
    setStageId(stageId);
  }
  return result;
}

async function refreshLatestDraft() {
  const result = await api('/x-kernel/package-drafts/latest');
  const stageId = result?.draft?.stage_id;
  if (stageId) {
    state.lastDraftStageId = stageId;
  }
  return result;
}

function requireStageId() {
  if (!state.stageId) {
    throw new Error('No active stage ID. Send a write/control request first or refresh latest stage.');
  }
  return state.stageId;
}

async function previewStage() {
  const stageId = requireStageId();
  const result = await api(`/x-kernel/stages/${encodeURIComponent(stageId)}/preview?reason=ui_preview`, {
    method: 'POST',
  });
  return result;
}

async function validateStage() {
  const stageId = requireStageId();
  const approvalPhrase = `APPROVE_STAGE_${stageId}`;
  const result = await api(
    `/x-kernel/stages/${encodeURIComponent(stageId)}/validate-approval?approval_phrase=${encodeURIComponent(approvalPhrase)}&reason=ui_validation`,
    { method: 'POST' },
  );
  return result;
}

async function preparePackage() {
  const stageId = requireStageId();
  const result = await api(`/x-kernel/stages/${encodeURIComponent(stageId)}/prepare-package?reason=ui_prepare_package`, {
    method: 'POST',
  });
  state.lastDraftStageId = stageId;
  return result;
}

async function cancelStage() {
  const stageId = requireStageId();
  const result = await api(`/x-kernel/stages/${encodeURIComponent(stageId)}/cancel?reason=ui_cancel`, {
    method: 'POST',
  });
  return result;
}

async function attachContent() {
  const stageId = state.lastDraftStageId || state.stageId;
  if (!stageId) {
    throw new Error('No package draft stage ID. Prepare or refresh a draft first.');
  }

  const content = els.operatorContent.value.trim();
  if (!content) {
    throw new Error('Enter operator-reviewed content first.');
  }

  const result = await api(`/x-kernel/package-drafts/${encodeURIComponent(stageId)}/attach-content?reason=ui_attach_content`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
  return result;
}

function bind() {
  els.newSessionButton.addEventListener('click', () => run('Creating session', newSession));
  els.sendButton.addEventListener('click', () => run('Sending to X', sendToX));
  els.refreshStageButton.addEventListener('click', () => run('Loading latest stage', refreshLatestStage));
  els.refreshDraftButton.addEventListener('click', () => run('Loading latest draft', refreshLatestDraft));
  els.previewButton.addEventListener('click', () => run('Previewing stage', previewStage));
  els.validateButton.addEventListener('click', () => run('Validating approval intent', validateStage));
  els.preparePackageButton.addEventListener('click', () => run('Preparing package draft', preparePackage));
  els.cancelStageButton.addEventListener('click', () => run('Cancelling stage', cancelStage));
  els.attachContentButton.addEventListener('click', () => run('Attaching content', attachContent));

  els.copyOutputButton.addEventListener('click', async () => {
    await navigator.clipboard.writeText(els.kernelOutput.textContent || '');
    els.copyOutputButton.textContent = 'Copied';
    window.setTimeout(() => { els.copyOutputButton.textContent = 'Copy'; }, 1200);
  });

  document.querySelectorAll('.quick-fill').forEach((button) => {
    button.addEventListener('click', () => {
      els.requestText.value = button.getAttribute('data-fill') || '';
      els.requestText.focus();
    });
  });

  els.requestText.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void run('Sending to X', sendToX);
    }
  });
}

bind();
void run('Creating session', newSession);
