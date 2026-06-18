const directState = {
  stageId: null,
};

function directPretty(value) {
  return JSON.stringify(value, null, 2);
}

function directSetOutput(value) {
  const output = document.getElementById('kernelOutput');
  if (output) {
    output.textContent = typeof value === 'string' ? value : directPretty(value);
  }
}

function directAppendMessage(role, text) {
  const messages = document.getElementById('messages');
  if (!messages) return;
  const article = document.createElement('article');
  const roleClass = role === 'operator'
    ? 'border-xv7-primary/50 bg-xv7-primary/10'
    : 'border-xv7-line/50 bg-slate-950/40';
  article.className = `rounded-xl border ${roleClass} p-3 text-sm text-slate-200`;
  const label = document.createElement('p');
  label.className = 'mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-xv7-glow';
  label.textContent = role;
  const body = document.createElement('pre');
  body.className = 'whitespace-pre-wrap font-sans text-sm leading-relaxed';
  body.textContent = text || '';
  article.append(label, body);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function directSetStage(stageId) {
  directState.stageId = stageId || null;
  const label = document.getElementById('activeStageLabel');
  if (label) {
    label.textContent = `stage: ${directState.stageId || 'none'}`;
  }
}

async function directApi(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function directSendToX() {
  const input = document.getElementById('requestText');
  const rawText = (input?.value || '').trim();
  if (!rawText) {
    directSetOutput('Enter a request first.');
    return;
  }

  directSetOutput('Sending to direct X Kernel endpoint...');
  directAppendMessage('operator', rawText);

  const result = await directApi('/x-kernel/messages', {
    method: 'POST',
    body: JSON.stringify({ raw_text: rawText, operator_mode: false }),
  });

  directAppendMessage('x', result.content || 'No content returned.');
  const stage = result?.metadata?.x_kernel_action_stage || result?.x_kernel_action_stage;
  if (stage?.stage_id) {
    directSetStage(stage.stage_id);
  }
  directSetOutput(result);
}

function directInterceptSend(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
  void directSendToX().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    directSetOutput(`ERROR: ${message}`);
  });
}

function directBind() {
  const sendButton = document.getElementById('sendButton');
  const input = document.getElementById('requestText');
  if (sendButton) {
    sendButton.addEventListener('click', directInterceptSend, true);
  }
  if (input) {
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        directInterceptSend(event);
      }
    }, true);
  }
  directAppendMessage('system', 'Direct X Kernel endpoint enabled: /api/x-kernel/messages');
}

directBind();
