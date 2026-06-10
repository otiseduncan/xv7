/**
 * xv7 zero-dependency SPA controller.
 *
 * Architecture goals:
 * - Keep state local and explicit for predictable UI updates.
 * - Favor async/await and cancellation-safe request handling.
 * - Leave extension points for streaming/WebSocket and avatar channels.
 */
class Xv7UI {
  /** @type {string | null} */
  currentSessionId = null;

  /** @type {string} */
  activePersona = 'default';

  /** @type {{id:string,name:string,model?:string,options?:Record<string, number>,system_prompt?:string}[]} */
  personas = [];

  /** @type {number} */
  memoryLogCount = 0;

  /** @type {Record<string, HTMLElement>} */
  els;

  /** @type {string} */
  apiBase = 'http://localhost:8000';

  constructor() {
    this.els = {
      personaSelect: document.getElementById('personaSelect'),
      personaHint: document.getElementById('personaHint'),
      sessionIdValue: document.getElementById('sessionIdValue'),
      memoryCountValue: document.getElementById('memoryCountValue'),
      hardwareLoadValue: document.getElementById('hardwareLoadValue'),
      hardwareLoadBar: document.getElementById('hardwareLoadBar'),
      alertBox: document.getElementById('alertBox'),
      retrievalJournal: document.getElementById('retrievalJournal'),
      chatTimeline: document.getElementById('chatTimeline'),
      promptInput: document.getElementById('promptInput'),
      sendButton: document.getElementById('sendButton'),
    };

    this.bindEvents();
    void this.initialize();
  }

  bindEvents() {
    this.els.sendButton.addEventListener('click', () => {
      void this.sendMessage();
    });

    this.els.promptInput.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        void this.sendMessage();
      }
    });

    this.els.personaSelect.addEventListener('change', () => {
      this.activePersona = this.els.personaSelect.value;
      // Reset to ensure persona-specific context starts from a clean thread.
      this.currentSessionId = null;
      this.updateSessionTelemetry();
      this.showAlert(`Switched persona to "${this.activePersona}". New session will initialize on next send.`, false);
    });
  }

  async initialize() {
    this.setHardwareLoad('Syncing Personas', 28);
    try {
      const payload = await this.fetchJson('/personas', { method: 'GET' });
      this.populatePersonas(payload);
      this.showAlert('Persona registry loaded successfully.', false, 2400);
      this.setHardwareLoad('Ready', 8);
    } catch (error) {
      this.showAlert(this.humanizeError(error), true);
      this.setHardwareLoad('Degraded', 16);
    }
  }

  /**
   * @param {unknown} payload
   */
  populatePersonas(payload) {
    const personasMap =
      payload && typeof payload === 'object' && payload.personas && typeof payload.personas === 'object'
        ? payload.personas
        : {};

    /** @type {{id:string,name:string,model?:string,options?:Record<string, number>,system_prompt?:string}[]} */
    const parsed = Object.entries(personasMap).map(([id, meta]) => {
      const safeMeta = meta && typeof meta === 'object' ? meta : {};
      return {
        id,
        name: String(safeMeta.name || id),
        model: safeMeta.model ? String(safeMeta.model) : undefined,
        options: safeMeta.options && typeof safeMeta.options === 'object' ? safeMeta.options : undefined,
        system_prompt: safeMeta.system_prompt ? String(safeMeta.system_prompt) : undefined,
      };
    });

    this.personas = parsed.length ? parsed : [{ id: 'default', name: 'default' }];

    this.els.personaSelect.innerHTML = '';
    this.personas.forEach((persona) => {
      const option = document.createElement('option');
      option.value = persona.id;
      option.textContent = persona.name;
      this.els.personaSelect.append(option);
    });

    if (!this.personas.some((persona) => persona.id === this.activePersona)) {
      this.activePersona = this.personas[0].id;
    }
    this.els.personaSelect.value = this.activePersona;

    const current = this.personas.find((persona) => persona.id === this.activePersona);
    this.els.personaHint.textContent = current?.model
      ? `Model: ${current.model}`
      : 'Model fallback currently inherited from core defaults.';
  }

  async sendMessage() {
    const raw = this.els.promptInput.value.trim();
    if (!raw) return;

    this.showAlert('', false);
    this.lockInput(true);
    this.setHardwareLoad('Inference', 74);

    try {
      if (!this.currentSessionId) {
        const sessionResponse = await fetch(`${this.apiBase}/sessions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            current_persona: this.activePersona,
            metadata: {
              source: 'xv7-public-spa',
              started_at: new Date().toISOString(),
            },
          }),
        });

        if (!sessionResponse.ok) {
          const errorText = await sessionResponse.text();
          throw new Error(errorText || `Session creation failed with status ${sessionResponse.status}`);
        }

        const sessionData = await sessionResponse.json();
        this.currentSessionId = sessionData.session_id;
        if (!this.currentSessionId || typeof this.currentSessionId !== 'string') {
          throw new Error('Session creation response did not include a valid session_id.');
        }
      }

      this.appendMessageCard('user', raw, null);
      this.els.promptInput.value = '';

      const messageResponse = await fetch(`${this.apiBase}/sessions/${this.currentSessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ raw_text: raw }),
      });

      if (!messageResponse.ok) {
        const errorText = await messageResponse.text();
        throw new Error(errorText || `Message request failed with status ${messageResponse.status}`);
      }

      try {
        const data = await messageResponse.json();
        const messages = Array.isArray(data?.messages) ? data.messages : [];
        const assistantMessage = messages[messages.length - 1];
        const assistantContent =
          assistantMessage &&
          typeof assistantMessage === 'object' &&
          typeof assistantMessage.content === 'string'
            ? assistantMessage.content
            : '';
        const assistantText = this.stripReasoningTokens(assistantContent).trim();
        const reasoningText = this.extractReasoning(assistantContent);

        this.appendMessageCard('assistant', assistantText || 'No assistant content returned.', reasoningText);

        this.memoryLogCount = messages.length;
        this.updateSessionTelemetry();
        this.renderRetrievalJournal(data);
        this.setHardwareLoad('Ready', 12);
      } catch (parseError) {
        this.els.sendButton.textContent = '[ ERROR ]';
        throw new Error(`Failed to parse assistant response: ${this.humanizeError(parseError)}`);
      }
    } catch (error) {
      this.setHardwareLoad('Recovery', 24);
      this.showAlert(this.humanizeError(error), true);
    } finally {
      this.lockInput(false);
    }
  }

  /**
   * @param {string} role
   * @param {string} content
   * @param {string | null} reasoning
   */
  appendMessageCard(role, content, reasoning) {
    const article = document.createElement('article');
    article.className =
      role === 'user'
        ? 'rounded-xl border border-sky-300/40 bg-sky-400/10 p-4'
        : 'rounded-xl border border-teal-300/30 bg-teal-300/10 p-4';

    const roleLabel = document.createElement('p');
    roleLabel.className = 'font-mono text-xs uppercase tracking-[0.16em] text-slate-300';
    roleLabel.textContent = role === 'user' ? 'User Input' : 'Assistant Output';

    const text = document.createElement('p');
    text.className = 'mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-100';
    text.textContent = this.stripReasoningTokens(content);

    article.append(roleLabel, text);

    if (reasoning && reasoning.trim()) {
      const details = document.createElement('details');
      details.className = 'mt-3 overflow-hidden rounded-lg border border-slate-700 bg-slate-950/80';

      const summary = document.createElement('summary');
      summary.className = 'cursor-pointer px-3 py-2 text-xs font-semibold tracking-wide text-slate-200';
      summary.textContent = '🧠 Cognitive Reasoning History';

      const reasoningBody = document.createElement('pre');
      reasoningBody.className = 'max-h-72 overflow-auto border-t border-slate-700 px-3 py-3 font-mono text-xs leading-5 text-slate-300';
      reasoningBody.textContent = reasoning.trim();

      details.append(summary, reasoningBody);
      article.append(details);
    }

    this.els.chatTimeline.append(article);
    this.els.chatTimeline.scrollTop = this.els.chatTimeline.scrollHeight;
  }

  /**
   * Displays top retrieval snippets if backend supplies them; otherwise uses
   * recent assistant/user timeline as a local fallback preview.
   *
   * @param {any} response
   */
  renderRetrievalJournal(response) {
    const journal = this.els.retrievalJournal;
    journal.innerHTML = '';

    let entries = [];
    if (Array.isArray(response?.retrieval_memories)) {
      entries = response.retrieval_memories.slice(0, 3);
    } else if (Array.isArray(response?.messages)) {
      entries = response.messages.slice(-3).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));
    }

    if (!entries.length) {
      const li = document.createElement('li');
      li.className = 'rounded-lg border border-dashed border-xv7-line bg-slate-900/40 px-3 py-2 text-slate-400';
      li.textContent = 'No retrieval context available for this turn.';
      journal.append(li);
      return;
    }

    entries.forEach((entry) => {
      const li = document.createElement('li');
      li.className = 'rounded-lg border border-xv7-line bg-slate-900/40 px-3 py-2 text-slate-200';
      const role = String(entry.role || 'memory').toUpperCase();
      const content = this.stripReasoningTokens(String(entry.content || '')).slice(0, 280);
      li.textContent = `[${role}] ${content || 'No content'}`;
      journal.append(li);
    });
  }

  /**
   * @param {string} text
   */
  extractReasoning(text) {
    const matches = [...text.matchAll(/<\|think\|>([\s\S]*?)<\/\|think\|>/g)];
    if (!matches.length) return null;
    return matches.map((m) => m[1]).join('\n\n');
  }

  /**
   * @param {string} text
   */
  stripReasoningTokens(text) {
    return text.replace(/<\|think\|>[\s\S]*?<\/\|think\|>/g, '').trim();
  }

  updateSessionTelemetry() {
    this.els.sessionIdValue.textContent = this.currentSessionId || 'not initialized';
    this.els.memoryCountValue.textContent = String(this.memoryLogCount);
  }

  /**
   * @param {string} label
   * @param {number} percent
   */
  setHardwareLoad(label, percent) {
    this.els.hardwareLoadValue.textContent = `${label} (${percent}%)`;
    this.els.hardwareLoadBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
  }

  /**
   * @param {boolean} locked
   */
  lockInput(locked) {
    this.els.promptInput.disabled = locked;
    this.els.sendButton.disabled = locked;
    this.els.sendButton.textContent = locked ? '[ PROCESSING ]' : '[ SEND ]';
  }

  /**
   * @param {unknown} error
   */
  humanizeError(error) {
    const fallback =
      'xv7-core is currently resetting or loading heavy model weights. Wait a moment and retry your request.';

    if (error instanceof Error) return error.message || fallback;
    if (typeof error === 'string') return error;
    return fallback;
  }

  /**
   * @param {string} message
   * @param {boolean} isError
   * @param {number} autoHideMs
   */
  showAlert(message, isError, autoHideMs = 0) {
    this.els.alertBox.classList.toggle('hidden', !message);
    this.els.alertBox.textContent = message;

    this.els.alertBox.classList.remove('border-teal-300/60', 'bg-teal-500/10', 'text-teal-100');
    if (!isError && message) {
      this.els.alertBox.classList.add('border-teal-300/60', 'bg-teal-500/10', 'text-teal-100');
    }

    if (autoHideMs > 0) {
      window.setTimeout(() => {
        this.els.alertBox.classList.add('hidden');
      }, autoHideMs);
    }
  }

  /**
   * @param {string} path
   * @param {RequestInit} init
   */
  async fetchJson(path, init) {
    const headers = new Headers(init?.headers || {});
    if (!headers.has('Content-Type') && init?.body) {
      headers.set('Content-Type', 'application/json');
    }

    // Intentionally long timeout to avoid failing while large model weights load.
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15 * 60 * 1000);

    try {
      const response = await fetch(`${this.apiBase}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Request failed with status ${response.status}`);
      }

      return await response.json();
    } finally {
      window.clearTimeout(timeout);
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  // Global entrypoint for future module extension (streaming, avatars, sockets).
  new Xv7UI();
});
