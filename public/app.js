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
  apiBase = '';

  /** @type {boolean} */
  modelMutationBusy = false;

  /** @type {string} */
  modelPanelStatus = 'Loading model profile state...';

  /** @type {{models:any|null,active:any|null,effective:any|null}} */
  modelPayload = { models: null, active: null, effective: null };

  /** @type {{coreApi:string,runtimeHealth:string,activeProfile:string,operatorMode:string,memory:string,lastAction:string,lastChecked:string}} */
  statusSummary = {
    coreApi: 'unknown',
    runtimeHealth: 'unknown',
    activeProfile: 'unknown',
    operatorMode: 'Read-only',
    memory: 'unknown',
    lastAction: 'none',
    lastChecked: 'never',
  };

  /** @type {string} */
  modelProfileSelection = '';

  /** @type {SpeechRecognition | null} */
  speechRecognition = null;

  /** @type {boolean} */
  speechSupported = false;

  /** @type {boolean} */
  isListening = false;

  /** @type {Array<{role:string,text:string,timestamp:string,receiptSummary:string[]}>} */
  visibleConversation = [];

  /** @type {boolean} */
  diagnosticsDrawerOpen = false;

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
      micButton: document.getElementById('micButton'),
      copyChatButton: document.getElementById('copyChatButton'),
      copyToast: document.getElementById('copyToast'),
      modelActiveProfile: document.getElementById('modelActiveProfile'),
      modelProfileSource: document.getElementById('modelProfileSource'),
      modelOllamaReachable: document.getElementById('modelOllamaReachable'),
      modelEffectiveChat: document.getElementById('modelEffectiveChat'),
      modelProfileSelect: document.getElementById('modelProfileSelect'),
      modelApplyButton: document.getElementById('modelApplyButton'),
      modelClearButton: document.getElementById('modelClearButton'),
      modelResolvedChat: document.getElementById('modelResolvedChat'),
      modelResolvedReasoning: document.getElementById('modelResolvedReasoning'),
      modelResolvedCode: document.getElementById('modelResolvedCode'),
      modelResolvedEmbedding: document.getElementById('modelResolvedEmbedding'),
      modelAvailabilityChat: document.getElementById('modelAvailabilityChat'),
      modelAvailabilityReasoning: document.getElementById('modelAvailabilityReasoning'),
      modelAvailabilityCode: document.getElementById('modelAvailabilityCode'),
      modelAvailabilityEmbedding: document.getElementById('modelAvailabilityEmbedding'),
      modelPanelStatus: document.getElementById('modelPanelStatus'),
      chatReceiptProfile: document.getElementById('chatReceiptProfile'),
      chatReceiptSource: document.getElementById('chatReceiptSource'),
      chatReceiptRole: document.getElementById('chatReceiptRole'),
      chatReceiptModelTag: document.getElementById('chatReceiptModelTag'),
      chatReceiptSelectionSource: document.getElementById('chatReceiptSelectionSource'),
      chatReceiptRequestId: document.getElementById('chatReceiptRequestId'),
      operatorActivityList: document.getElementById('operatorActivityList'),
      statusCoreApi: document.getElementById('statusCoreApi'),
      statusRuntimeHealth: document.getElementById('statusRuntimeHealth'),
      statusActiveProfile: document.getElementById('statusActiveProfile'),
      statusOperatorMode: document.getElementById('statusOperatorMode'),
      statusMemory: document.getElementById('statusMemory'),
      statusLastAction: document.getElementById('statusLastAction'),
      statusLastChecked: document.getElementById('statusLastChecked'),
      // compact strip chips (separate elements in new layout)
      statusCoreApiChip: document.getElementById('statusCoreApiChip'),
      statusRuntimeHealthChip: document.getElementById('statusRuntimeHealthChip'),
      statusActiveProfileChip: document.getElementById('statusActiveProfileChip'),
      statusOperatorModeChip: document.getElementById('statusOperatorModeChip'),
      statusLastCheckedChip: document.getElementById('statusLastCheckedChip'),
      // operator summary chip in main view
      operatorSummaryChip: document.getElementById('operatorSummaryChip'),
      // diagnostics drawer
      diagnosticsDrawer: document.getElementById('diagnosticsDrawer'),
      diagnosticsBackdrop: document.getElementById('diagnosticsBackdrop'),
      diagnosticsToggleButton: document.getElementById('diagnosticsToggleButton'),
      diagnosticsCloseButton: document.getElementById('diagnosticsCloseButton'),
    };

    this.bindEvents();
    void this.initialize();
  }

  bindEvents() {
    this.els.sendButton.addEventListener('click', () => {
      void this.sendMessage();
    });

    this.els.promptInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
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

    this.els.modelProfileSelect.addEventListener('change', () => {
      this.modelProfileSelection = this.els.modelProfileSelect.value;
      this.renderModelProfileControl();
    });

    this.els.modelApplyButton.addEventListener('click', () => {
      void this.applyRuntimeProfileOverride();
    });

    this.els.modelClearButton.addEventListener('click', () => {
      void this.clearRuntimeProfileOverride();
    });

    if (this.els.micButton) {
      this.els.micButton.addEventListener('click', () => {
        this.toggleVoiceInput();
      });
    }

    if (this.els.copyChatButton) {
      this.els.copyChatButton.addEventListener('click', () => {
        void this.copyEntireChat();
      });
    }

    if (this.els.diagnosticsToggleButton) {
      this.els.diagnosticsToggleButton.addEventListener('click', () => {
        this.openDiagnosticsDrawer();
      });
    }

    if (this.els.diagnosticsCloseButton) {
      this.els.diagnosticsCloseButton.addEventListener('click', () => {
        this.closeDiagnosticsDrawer();
      });
    }

    if (this.els.diagnosticsBackdrop) {
      this.els.diagnosticsBackdrop.addEventListener('click', () => {
        this.closeDiagnosticsDrawer();
      });
    }
  }

  async initialize() {
    this.setHardwareLoad('Syncing Personas', 28);
    try {
      const payload = await this.fetchJson('/personas', { method: 'GET' });
      this.populatePersonas(payload);
      this.showAlert('Persona registry loaded successfully.', false, 2400);
      this.setHardwareLoad('Ready', 8);
      this.statusSummary.coreApi = 'reachable';
      this.statusSummary.memory = 'available';
      this.refreshStatusTimestamp();
      this.renderStatusStrip();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true);
      this.setHardwareLoad('Degraded', 16);
      this.statusSummary.coreApi = 'unreachable';
      this.statusSummary.runtimeHealth = 'unknown';
      this.refreshStatusTimestamp();
      this.renderStatusStrip();
    }

    await this.refreshModelProfileControl();
    this.setupVoiceInput();
  }

  async refreshModelProfileControl() {
    this.modelPanelStatus = 'Refreshing runtime model profile state...';
    this.renderModelProfileControl();

    try {
      const [modelsPayload, activePayload, effectivePayload] = await Promise.all([
        this.fetchJson('/runtime/models', { method: 'GET' }),
        this.fetchJson('/runtime/models/active', { method: 'GET' }),
        this.fetchJson('/runtime/models/effective', { method: 'GET' }),
      ]);

      this.modelPayload = {
        models: modelsPayload,
        active: activePayload,
        effective: effectivePayload,
      };

      const availableProfiles = Array.isArray(modelsPayload?.available_profiles)
        ? modelsPayload.available_profiles.filter((item) => typeof item === 'string' && item.trim())
        : [];
      const activeProfile = typeof activePayload?.active_profile === 'string' ? activePayload.active_profile : '';
      if (!availableProfiles.includes(this.modelProfileSelection)) {
        this.modelProfileSelection = activeProfile || availableProfiles[0] || '';
      }

      this.modelPanelStatus = 'Runtime profile data loaded.';
      this.statusSummary.runtimeHealth = 'ok';
      this.statusSummary.activeProfile = activeProfile || 'unknown';
      this.statusSummary.coreApi = 'reachable';
      this.statusSummary.memory = 'available';
      this.refreshStatusTimestamp();
    } catch (error) {
      this.modelPayload = { models: null, active: null, effective: null };
      this.modelPanelStatus = this.humanizeError(error);
      this.statusSummary.runtimeHealth = 'degraded';
      this.statusSummary.coreApi = 'reachable';
      this.refreshStatusTimestamp();
    }

    this.renderModelProfileControl();
    this.renderStatusStrip();
  }

  renderModelProfileControl() {
    const modelsPayload = this.modelPayload.models;
    const activePayload = this.modelPayload.active;

    const activeProfile = typeof activePayload?.active_profile === 'string' ? activePayload.active_profile : 'unknown';
    const profileSource = typeof activePayload?.profile_source === 'string' ? activePayload.profile_source : 'unknown';
    const reachable = Boolean(activePayload?.ollama?.reachable);
    const effectiveChatModel =
      typeof this.modelPayload.effective?.effective_models?.chat === 'string'
        ? this.modelPayload.effective.effective_models.chat
        : '-';
    const availableProfiles = Array.isArray(modelsPayload?.available_profiles)
      ? modelsPayload.available_profiles.filter((item) => typeof item === 'string' && item.trim())
      : [];

    this.els.modelActiveProfile.textContent = activeProfile;
    this.els.modelProfileSource.textContent = profileSource;
    this.els.modelOllamaReachable.textContent = reachable ? 'yes' : 'no';
    this.els.modelEffectiveChat.textContent = effectiveChatModel;
    this.els.modelOllamaReachable.classList.toggle('status-ok', reachable);
    this.els.modelOllamaReachable.classList.toggle('status-bad', !reachable);

    this.els.modelProfileSelect.innerHTML = '';
    if (!availableProfiles.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'no profiles available';
      this.els.modelProfileSelect.append(option);
    } else {
      availableProfiles.forEach((profile) => {
        const option = document.createElement('option');
        option.value = profile;
        option.textContent = profile;
        this.els.modelProfileSelect.append(option);
      });
      this.els.modelProfileSelect.value = availableProfiles.includes(this.modelProfileSelection)
        ? this.modelProfileSelection
        : availableProfiles[0];
      this.modelProfileSelection = this.els.modelProfileSelect.value;
    }

    const profiles = modelsPayload?.profiles && typeof modelsPayload.profiles === 'object' ? modelsPayload.profiles : {};
    const selectedResolved = profiles[this.modelProfileSelection] && typeof profiles[this.modelProfileSelection] === 'object'
      ? profiles[this.modelProfileSelection]
      : activePayload?.resolved_models || {};

    this.els.modelResolvedChat.textContent = selectedResolved?.chat || '-';
    this.els.modelResolvedReasoning.textContent = selectedResolved?.reasoning || '-';
    this.els.modelResolvedCode.textContent = selectedResolved?.code || '-';
    this.els.modelResolvedEmbedding.textContent = selectedResolved?.embedding || '-';

    const availability = activePayload?.availability || {};
    this.els.modelAvailabilityChat.textContent = this.asBoolLabel(availability.chat);
    this.els.modelAvailabilityReasoning.textContent = this.asBoolLabel(availability.reasoning);
    this.els.modelAvailabilityCode.textContent = this.asBoolLabel(availability.code);
    this.els.modelAvailabilityEmbedding.textContent = this.asBoolLabel(availability.embedding);

    const canApply =
      !this.modelMutationBusy &&
      !!this.modelProfileSelection &&
      (this.modelProfileSelection !== activeProfile || profileSource !== 'runtime_override');

    const canClear = !this.modelMutationBusy && profileSource === 'runtime_override';

    this.els.modelApplyButton.disabled = !canApply;
    this.els.modelClearButton.disabled = !canClear;
    this.els.modelPanelStatus.textContent = this.modelPanelStatus;
  }

  asBoolLabel(value) {
    return value ? 'available' : 'unavailable';
  }

  async applyRuntimeProfileOverride() {
    if (!this.modelProfileSelection) {
      this.modelPanelStatus = 'Select a profile before applying runtime override.';
      this.renderModelProfileControl();
      return;
    }

    this.modelMutationBusy = true;
    this.modelPanelStatus = 'Applying runtime override...';
    this.renderModelProfileControl();

    try {
      const payload = await this.fetchJson('/api/runtime/models/active', {
        method: 'PUT',
        body: JSON.stringify({
          profile: this.modelProfileSelection,
          require_available: true,
        }),
      });

      this.modelPanelStatus = `Runtime override applied: ${payload.active_profile} (${payload.profile_source}).`;
      await this.refreshModelProfileControl();
    } catch (error) {
      this.modelPanelStatus = this.humanizeError(error);
      this.renderModelProfileControl();
    } finally {
      this.modelMutationBusy = false;
      this.renderModelProfileControl();
    }
  }

  async clearRuntimeProfileOverride() {
    this.modelMutationBusy = true;
    this.modelPanelStatus = 'Clearing runtime override...';
    this.renderModelProfileControl();

    try {
      const payload = await this.fetchJson('/api/runtime/models/active', {
        method: 'DELETE',
      });

      this.modelPanelStatus = `Runtime override cleared. Active profile fallback: ${payload.active_profile} (${payload.profile_source}).`;
      await this.refreshModelProfileControl();
    } catch (error) {
      this.modelPanelStatus = this.humanizeError(error);
      this.renderModelProfileControl();
    } finally {
      this.modelMutationBusy = false;
      this.renderModelProfileControl();
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
        const sessionData = await this.fetchJson('/api/sessions', {
          method: 'POST',
          body: JSON.stringify({
            current_persona: this.activePersona,
            metadata: {
              source: 'xv7-public-spa',
              started_at: new Date().toISOString(),
            },
          }),
        });
        this.currentSessionId = sessionData.session_id;
        if (!this.currentSessionId || typeof this.currentSessionId !== 'string') {
          throw new Error('Session creation response did not include a valid session_id.');
        }
      }

      this.appendMessageCard('user', raw, null, null, this.nowIso());
      this.els.promptInput.value = '';

      const data = await this.fetchJson(`/api/sessions/${this.currentSessionId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ raw_text: raw }),
      });

      try {
        const messages = Array.isArray(data?.messages) ? data.messages : [];
        const assistantMessage = messages[messages.length - 1];
        const assistantContent =
          assistantMessage &&
          typeof assistantMessage === 'object' &&
          typeof assistantMessage.content === 'string'
            ? assistantMessage.content
            : '';
        const assistantMeta =
          assistantMessage &&
          typeof assistantMessage === 'object' &&
          assistantMessage.metadata &&
          typeof assistantMessage.metadata === 'object'
            ? assistantMessage.metadata
            : {};
        const assistantText = this.resolveAssistantVisibleText(assistantMeta, assistantContent);
        const reasoningText = this.extractReasoning(assistantContent);

        this.appendMessageCard(
          'assistant',
          assistantText || 'No assistant content returned.',
          reasoningText,
          assistantMeta,
          this.inferAssistantTimestamp(assistantMeta),
        );

        this.renderModelUseReceipt(data?.metadata?.model_use_receipt);
        this.renderOperatorActivity(data?.metadata?.operator_action_history);
        this.updateStatusFromHistory(data?.metadata?.operator_action_history);

        this.memoryLogCount = messages.length;
        this.updateSessionTelemetry();
        this.renderRetrievalJournal(data);
        this.setHardwareLoad('Ready', 12);
      } catch (parseError) {
        this.els.sendButton.textContent = 'Error';
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
  appendMessageCard(role, content, reasoning, messageMetadata = null, timestamp = '') {
    const article = document.createElement('article');
    article.className = role === 'user' ? 'chat-card chat-card-user' : 'chat-card chat-card-assistant';
    article.dataset.role = role;
    article.dataset.timestamp = timestamp || '';

    const roleLabel = document.createElement('p');
    roleLabel.className = 'chat-role-label';
    roleLabel.textContent = role === 'user' ? 'User Input' : 'Assistant Output';

    const actions = document.createElement('div');
    actions.className = 'message-actions';

    const copyButton = document.createElement('button');
    copyButton.type = 'button';
    copyButton.className = 'message-copy-button';
    copyButton.setAttribute('aria-label', 'Copy message');
    copyButton.textContent = 'Copy';
    copyButton.addEventListener('click', () => {
      void this.copySingleMessage(article);
    });
    actions.append(copyButton);

    const text = document.createElement('p');
    text.className = 'chat-visible-text';
    text.textContent = content;
    text.dataset.visibleText = content;

    article.append(roleLabel, actions, text);

    const copyPayload = {
      role,
      text: content,
      timestamp: timestamp || '',
      receiptSummary: [],
    };

    if (role === 'assistant') {
      copyPayload.receiptSummary = this.appendReceiptChips(article, messageMetadata);
    }

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
    this.visibleConversation.push(copyPayload);
  }

  appendReceiptChips(article, messageMetadata) {
    const meta = messageMetadata && typeof messageMetadata === 'object' ? messageMetadata : {};
    const chipRow = document.createElement('div');
    chipRow.className = 'receipt-chip-row';

    const compactReceipts = [];

    const operatorReceipts = Array.isArray(meta.operator_receipts) ? meta.operator_receipts : [];
    operatorReceipts.forEach((receipt) => {
      if (!receipt || typeof receipt !== 'object') return;
      const status = typeof receipt.status === 'string' ? receipt.status : 'unknown';
      const actionName = typeof receipt.action_name === 'string' ? receipt.action_name : 'operator_action';
      const readOnly = receipt.read_only === true ? 'read_only=true' : 'read_only=false';
      const chip = document.createElement('span');
      chip.className = `receipt-chip status-${status}`;
      chip.textContent = `Operator: ${this.operatorChipLabel(actionName, status)}`;
      chipRow.append(chip);
      compactReceipts.push(`${actionName} ${status} ${readOnly}`);
    });

    const contextReceipt = meta.context_receipt && typeof meta.context_receipt === 'object' ? meta.context_receipt : null;
    const contextEntries = Array.isArray(contextReceipt?.context_receipts)
      ? contextReceipt.context_receipts
      : [];

    if (contextEntries.length > 0) {
      contextEntries.forEach((entry) => {
        if (!entry || typeof entry !== 'object') return;
        const recordId = this.extractReceiptId(entry.record_id || entry.receipt_label || '');
        if (!recordId || recordId === '-') return;
        const label = this.contextLayerChipLabel(entry.layer || entry.receipt_label || '');

        const chip = document.createElement('span');
        chip.className = `receipt-chip receipt-chip-${label.toLowerCase()}`;
        chip.textContent = `${label}: ${recordId}`;
        chipRow.append(chip);
        compactReceipts.push(`${label.toLowerCase()} ${recordId}`);
      });
    } else if (contextReceipt && typeof contextReceipt.compact === 'string' && contextReceipt.compact.trim()) {
      const layered = this.parseLayeredContextFromCompact(contextReceipt.compact);

      if (layered.length > 0) {
        layered.forEach((item) => {
          const chip = document.createElement('span');
          chip.className = `receipt-chip receipt-chip-${item.label.toLowerCase()}`;
          chip.textContent = `${item.label}: ${item.recordId}`;
          chipRow.append(chip);
          compactReceipts.push(`${item.label.toLowerCase()} ${item.recordId}`);
        });
      } else if (!contextReceipt.compact.toLowerCase().includes('operator receipt')) {
        const chip = document.createElement('span');
        chip.className = 'receipt-chip';
        const contextSummary = this.summarizeContextReceipt(contextReceipt.compact);
        chip.textContent = `Context: ${contextSummary}`;
        chipRow.append(chip);
        compactReceipts.push(`context ${contextSummary}`);
      }
    }

    const memoryReceipts = Array.isArray(meta.memory_receipts) ? meta.memory_receipts : [];
    memoryReceipts.slice(0, 2).forEach((item) => {
      if (typeof item !== 'string' || !item.trim()) return;
      const chip = document.createElement('span');
      chip.className = 'receipt-chip';
      const memoryId = this.extractReceiptId(item);
      chip.textContent = `Memory: ${memoryId}`;
      chipRow.append(chip);
      compactReceipts.push(`memory ${memoryId}`);
    });

    const modelUseReceipt = meta.model_use_receipt && typeof meta.model_use_receipt === 'object' ? meta.model_use_receipt : null;
    if (typeof modelUseReceipt?.model_tag === 'string' && modelUseReceipt.model_tag.trim()) {
      const chip = document.createElement('span');
      chip.className = 'receipt-chip';
      chip.textContent = `Model: ${modelUseReceipt.model_tag.trim()}`;
      chipRow.append(chip);
      compactReceipts.push(`model ${modelUseReceipt.model_tag.trim()}`);
    }

    if (chipRow.childElementCount > 0) {
      article.append(chipRow);
    }

    if (operatorReceipts.length > 0) {
      operatorReceipts.forEach((receipt) => {
        if (!receipt || typeof receipt !== 'object') return;
        const details = document.createElement('details');
        details.className = 'receipt-details';

        const summary = document.createElement('summary');
        const label = typeof receipt.receipt_label === 'string' ? receipt.receipt_label : 'operator receipt';
        const status = typeof receipt.status === 'string' ? receipt.status : 'unknown';
        summary.textContent = `${label} (${status})`;

        const body = document.createElement('div');
        body.className = 'receipt-detail-grid';
        this.appendReceiptField(body, 'action_id', receipt.action_id);
        this.appendReceiptField(body, 'action_name', receipt.action_name);
        this.appendReceiptField(body, 'status', receipt.status);
        this.appendReceiptField(body, 'read_only', receipt.read_only);
        this.appendReceiptField(body, 'target', receipt.target);
        this.appendReceiptField(body, 'summary', receipt.summary);
        this.appendReceiptField(body, 'limitation', receipt.limitation);
        this.appendReceiptField(body, 'timestamp', receipt.completed_at || receipt.started_at);

        details.append(summary, body);
        article.append(details);
      });
    }

    return compactReceipts;
  }

  renderOperatorActivity(history) {
    const list = this.els.operatorActivityList;
    const chip = this.els.operatorSummaryChip;

    const items = Array.isArray(history) ? history.slice().reverse() : [];

    // --- compact summary chip in main view ---
    if (chip) {
      if (!items.length) {
        chip.classList.add('hidden');
        chip.textContent = '';
      } else {
        const latest = items[0];
        const status = typeof latest.status === 'string' ? latest.status : 'unknown';
        const actionName = typeof latest.action_name === 'string' ? latest.action_name : 'operator_action';
        const hasLimitation = typeof latest.limitation === 'string' && latest.limitation.trim().length > 0;
        const label = hasLimitation ? `${actionName} (limitation)` : `${actionName} ${status}`;
        chip.textContent = `Last operator action: ${label}`;
        chip.className = `operator-summary-chip border-b border-xv7-line bg-xv7-panelSoft px-4 py-1.5 text-[11px] chip-status-${hasLimitation ? 'limitation' : status}`;
      }
    }

    if (!list) return;
    list.innerHTML = '';

    if (!items.length) {
      const li = document.createElement('li');
      li.className = 'rounded border border-dashed border-xv7-line px-2 py-1.5 text-slate-500';
      li.textContent = 'No operator actions yet.';
      list.append(li);
      return;
    }

    items.forEach((entry) => {
      if (!entry || typeof entry !== 'object') return;
      const li = document.createElement('li');
      const status = typeof entry.status === 'string' ? entry.status : 'unknown';
      const hasLimitation = typeof entry.limitation === 'string' && entry.limitation.trim().length > 0;
      li.className = `operator-activity-item status-${hasLimitation ? 'limitation' : status}`;

      const summary = document.createElement('div');
      summary.className = 'operator-activity-summary';

      const name = document.createElement('span');
      name.className = 'operator-activity-name';
      name.textContent = entry.action_name || 'unknown';

      const badge = document.createElement('span');
      badge.className = `operator-status-badge status-${hasLimitation ? 'limitation' : status}`;
      badge.textContent = hasLimitation ? 'limitation' : status;

      summary.append(name, badge);

      const meta = document.createElement('div');
      meta.className = 'operator-activity-meta font-mono';
      const timestamp = typeof entry.completed_at === 'string' ? entry.completed_at : 'n/a';
      meta.textContent = `${timestamp} | target=${entry.target || 'unknown'}`;

      const detail = document.createElement('div');
      detail.className = 'operator-activity-meta';
      detail.textContent = String(entry.summary || entry.receipt_label || 'no summary');

      const details = document.createElement('details');
      details.className = 'operator-activity-details';
      const detailsSummary = document.createElement('summary');
      detailsSummary.textContent = 'Expand details';
      const detailGrid = document.createElement('div');
      detailGrid.className = 'receipt-detail-grid';
      this.appendReceiptField(detailGrid, 'action_id', entry.action_id);
      this.appendReceiptField(detailGrid, 'status', status);
      this.appendReceiptField(detailGrid, 'read_only', entry.read_only);
      this.appendReceiptField(detailGrid, 'target', entry.target);
      this.appendReceiptField(detailGrid, 'summary', entry.summary);
      this.appendReceiptField(detailGrid, 'limitation', entry.limitation);
      this.appendReceiptField(detailGrid, 'timestamp', entry.completed_at || entry.started_at);
      details.append(detailsSummary, detailGrid);

      li.append(summary, meta, detail, details);
      list.append(li);
    });
  }

  updateStatusFromHistory(history) {
    const items = Array.isArray(history) ? history : [];
    if (!items.length) {
      this.renderStatusStrip();
      return;
    }

    const latest = items[items.length - 1];
    if (latest && typeof latest === 'object') {
      const status = typeof latest.status === 'string' ? latest.status : 'unknown';
      const actionName = typeof latest.action_name === 'string' ? latest.action_name : 'operator_action';
      this.statusSummary.lastAction = `${actionName} ${status}`;
      this.statusSummary.operatorMode = 'Read-only';
      this.refreshStatusTimestamp();
      this.renderStatusStrip();
    }
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
    this.statusSummary.memory = this.currentSessionId ? 'available' : 'idle';
    this.renderStatusStrip();
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
    this.els.sendButton.textContent = locked ? 'Processing…' : 'Send';
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

    this.els.alertBox.classList.remove('alert-info');
    if (!isError && message) {
      this.els.alertBox.classList.add('alert-info');
    }

    if (autoHideMs > 0) {
      window.setTimeout(() => {
        this.els.alertBox.classList.add('hidden');
      }, autoHideMs);
    }
  }

  setupVoiceInput() {
    if (!this.els.micButton) return;

    const SpeechRecognitionCtor =
      window.SpeechRecognition || window.webkitSpeechRecognition || null;

    this.speechSupported = Boolean(SpeechRecognitionCtor);
    if (!this.speechSupported) {
      this.els.micButton.disabled = true;
      this.els.micButton.setAttribute('aria-label', 'Start voice input');
      this.els.micButton.title = 'Voice input is not supported in this browser.';
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      this.isListening = true;
      this.els.micButton.classList.add('listening');
      this.els.micButton.textContent = 'Listening...';
      this.els.micButton.setAttribute('aria-label', 'Stop voice input');
      this.els.micButton.title = 'Click to stop voice input.';
    };

    recognition.onend = () => {
      this.isListening = false;
      this.els.micButton.classList.remove('listening');
      this.els.micButton.textContent = 'Mic';
      this.els.micButton.setAttribute('aria-label', 'Start voice input');
      this.els.micButton.title = 'Start voice input.';
    };

    recognition.onresult = (event) => {
      const result = event.results?.[0]?.[0]?.transcript;
      if (!result || typeof result !== 'string') return;
      this.els.promptInput.value = result.trim();
      this.els.promptInput.focus();
      this.showCopyToast('Voice transcript added to prompt.');
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        this.showAlert('Microphone permission was denied.', true, 2200);
        return;
      }
      if (event.error === 'no-speech') {
        this.showAlert('No speech was detected. Try again.', true, 1800);
        return;
      }
      this.showAlert('Voice input failed to start.', true, 1800);
    };

    this.speechRecognition = recognition;
    this.els.micButton.disabled = false;
    this.els.micButton.title = 'Start voice input.';
  }

  toggleVoiceInput() {
    if (!this.speechSupported || !this.speechRecognition) {
      this.showAlert('Voice input is not supported in this browser.', true, 2200);
      return;
    }

    if (this.isListening) {
      this.speechRecognition.stop();
      return;
    }

    this.speechRecognition.start();
  }

  async copyEntireChat() {
    const lines = [];
    this.visibleConversation.forEach((entry) => {
      const roleLabel = entry.role === 'assistant' ? 'Xoduz' : 'User';
      if (entry.timestamp) {
        lines.push(`[${entry.timestamp}]`);
      }
      lines.push(`${roleLabel}:`);
      lines.push(entry.text || '');
      if (Array.isArray(entry.receiptSummary) && entry.receiptSummary.length) {
        entry.receiptSummary.forEach((receiptLine) => {
          lines.push('');
          lines.push(`Operator receipt:`);
          lines.push(receiptLine);
        });
      }
      lines.push('');
    });

    await this.copyToClipboard(lines.join('\n').trim());
    this.showCopyToast('Chat copied.');
  }

  async copySingleMessage(article) {
    const role = article?.dataset?.role === 'assistant' ? 'Xoduz' : 'User';
    const text = article.querySelector('.chat-visible-text')?.textContent || '';
    const timestamp = article?.dataset?.timestamp || '';

    const lines = [];
    if (timestamp) {
      lines.push(`[${timestamp}]`);
    }
    lines.push(`${role}:`);
    lines.push(text);

    if (role === 'Xoduz') {
      const chips = [...article.querySelectorAll('.receipt-chip')]
        .map((chip) => (chip.textContent || '').trim())
        .filter(Boolean);
      chips.forEach((chipText) => {
        lines.push('');
        lines.push(`Receipt:`);
        lines.push(chipText);
      });
    }

    await this.copyToClipboard(lines.join('\n').trim());
    this.showCopyToast('Copied.');
  }

  async copyToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return;
    }

    const el = document.createElement('textarea');
    el.value = text;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.append(el);
    el.select();
    document.execCommand('copy');
    el.remove();
  }

  showCopyToast(message) {
    const toast = this.els.copyToast;
    if (!toast) {
      this.showAlert(message, false, 1200);
      return;
    }

    toast.textContent = message;
    toast.classList.remove('hidden');
    window.clearTimeout(this.copyToastTimer);
    this.copyToastTimer = window.setTimeout(() => {
      toast.classList.add('hidden');
    }, 1200);
  }

  nowIso() {
    return new Date().toISOString();
  }

  inferAssistantTimestamp(metadata) {
    const receipts = Array.isArray(metadata?.operator_receipts) ? metadata.operator_receipts : [];
    const latest = receipts[receipts.length - 1];
    if (latest && typeof latest.completed_at === 'string') {
      return latest.completed_at;
    }
    return this.nowIso();
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

  renderModelUseReceipt(receipt) {
    const safeReceipt = receipt && typeof receipt === 'object' ? receipt : {};

    this.els.chatReceiptProfile.textContent = this.receiptField(safeReceipt.model_profile);
    this.els.chatReceiptSource.textContent = this.receiptField(safeReceipt.profile_source);
    this.els.chatReceiptRole.textContent = this.receiptField(safeReceipt.runtime_role);
    this.els.chatReceiptModelTag.textContent = this.receiptField(safeReceipt.model_tag);
    this.els.chatReceiptSelectionSource.textContent = this.receiptField(
      safeReceipt.model_selection_source,
    );
    this.els.chatReceiptRequestId.textContent = this.receiptField(safeReceipt.request_id);
  }

  renderStatusStrip() {
    // --- drawer panel values (existing IDs) ---
    const drawerMap = [
      ['statusCoreApi', this.statusSummary.coreApi],
      ['statusRuntimeHealth', this.statusSummary.runtimeHealth],
      ['statusActiveProfile', this.statusSummary.activeProfile],
      ['statusOperatorMode', this.statusSummary.operatorMode],
      ['statusMemory', this.statusSummary.memory],
      ['statusLastAction', this.statusSummary.lastAction],
      ['statusLastChecked', this.statusSummary.lastChecked],
    ];

    drawerMap.forEach(([id, value]) => {
      const el = this.els[id];
      if (!el) return;
      el.textContent = value;
    });

    this.applyStatusTone(this.els.statusCoreApi, this.statusSummary.coreApi);
    this.applyStatusTone(this.els.statusRuntimeHealth, this.statusSummary.runtimeHealth);
    this.applyStatusTone(this.els.statusMemory, this.statusSummary.memory);
    this.applyStatusTone(this.els.statusLastAction, this.statusSummary.lastAction);

    // --- compact strip chips (new layout, separate elements) ---
    if (this.els.statusCoreApiChip) {
      this.els.statusCoreApiChip.textContent = this.statusSummary.coreApi;
      this.applyStatusTone(this.els.statusCoreApiChip, this.statusSummary.coreApi);
    }
    if (this.els.statusRuntimeHealthChip) {
      this.els.statusRuntimeHealthChip.textContent = this.statusSummary.runtimeHealth;
      this.applyStatusTone(this.els.statusRuntimeHealthChip, this.statusSummary.runtimeHealth);
    }
    if (this.els.statusActiveProfileChip) {
      this.els.statusActiveProfileChip.textContent = this.statusSummary.activeProfile;
    }
    if (this.els.statusOperatorModeChip) {
      this.els.statusOperatorModeChip.textContent = this.statusSummary.operatorMode;
    }
    if (this.els.statusLastCheckedChip) {
      this.els.statusLastCheckedChip.textContent = this.statusSummary.lastChecked;
    }
  }

  refreshStatusTimestamp() {
    const date = new Date();
    this.statusSummary.lastChecked = `last checked ${date.toLocaleTimeString()}`;
  }

  openDiagnosticsDrawer() {
    this.diagnosticsDrawerOpen = true;
    if (this.els.diagnosticsDrawer) {
      this.els.diagnosticsDrawer.classList.add('open');
    }
    if (this.els.diagnosticsBackdrop) {
      this.els.diagnosticsBackdrop.classList.remove('hidden');
    }
    if (this.els.diagnosticsToggleButton) {
      this.els.diagnosticsToggleButton.setAttribute('aria-expanded', 'true');
    }
  }

  closeDiagnosticsDrawer() {
    this.diagnosticsDrawerOpen = false;
    if (this.els.diagnosticsDrawer) {
      this.els.diagnosticsDrawer.classList.remove('open');
    }
    if (this.els.diagnosticsBackdrop) {
      this.els.diagnosticsBackdrop.classList.add('hidden');
    }
    if (this.els.diagnosticsToggleButton) {
      this.els.diagnosticsToggleButton.setAttribute('aria-expanded', 'false');
    }
  }

  applyStatusTone(el, rawValue) {
    if (!el) return;
    const value = String(rawValue || '').toLowerCase();
    const positive = ['ok', 'reachable', 'available', 'read-only', 'none', 'unknown'];
    const negative = ['unreachable', 'failed', 'degraded', 'denied', 'error'];

    const isNegative = negative.some((token) => value.includes(token));
    const isPositive = positive.some((token) => value.includes(token));

    el.classList.toggle('status-bad', isNegative);
    el.classList.toggle('status-ok', !isNegative && isPositive);
  }

  appendReceiptField(container, label, value) {
    const row = document.createElement('div');
    row.className = 'receipt-field';

    const key = document.createElement('span');
    key.className = 'receipt-field-key';
    key.textContent = `${label}:`;

    const val = document.createElement('span');
    val.className = 'receipt-field-value';
    val.textContent = this.receiptField(value);

    row.append(key, val);
    container.append(row);
  }

  operatorChipLabel(actionName, status) {
    const normalizedAction = String(actionName || 'operator_action');
    const normalizedStatus = String(status || 'unknown');
    if (normalizedAction === 'read_only_guard' && normalizedStatus === 'denied') {
      return 'mutation denied';
    }
    return `${normalizedAction} ${normalizedStatus}`;
  }

  summarizeContextReceipt(value) {
    const text = String(value || '').trim();
    if (!text) return '-';

    const id = this.extractReceiptId(text);
    if (id !== text) {
      if (text.toLowerCase().includes('verified status')) {
        return `Verified Status ${id}`;
      }
      return id;
    }

    return text.length > 72 ? `${text.slice(0, 69)}...` : text;
  }

  contextLayerChipLabel(layerOrLabel) {
    const normalized = String(layerOrLabel || '').toLowerCase();
    if (normalized.includes('system_prompt') || normalized.includes('system prompt')) return 'System';
    if (normalized.includes('active_focus') || normalized.includes('active focus')) return 'Focus';
    if (normalized.includes('verified_status') || normalized.includes('verified status')) return 'Verified';
    if (normalized.includes('knowledge')) return 'Knowledge';
    if (normalized.includes('memory')) return 'Memory';
    return 'Context';
  }

  parseLayeredContextFromCompact(value) {
    const text = String(value || '');
    const out = [];
    const pattern = /(System Prompt|Active Focus|Knowledge|Memory|Verified Status)\s+(XV7-[A-Z-]+-\d+)/g;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      out.push({
        label: this.contextLayerChipLabel(match[1]),
        recordId: match[2],
      });
    }
    return out;
  }

  extractReceiptId(value) {
    const text = String(value || '').trim();
    if (!text) return '-';
    const match = text.match(/(XV7-[A-Z-]+-\d+)/);
    return match ? match[1] : text;
  }

  resolveAssistantVisibleText(metadata, content) {
    const meta = metadata && typeof metadata === 'object' ? metadata : {};
    const fromMeta = typeof meta.visible_text === 'string' ? meta.visible_text.trim() : '';
    if (fromMeta) return fromMeta;

    const stripped = this.stripReasoningTokens(String(content || '')).trim();
    if (!stripped) return 'No assistant content returned.';

    if (this.looksLikeStructuredPayload(stripped)) {
      return 'Structured response received. Expand receipts for details.';
    }

    return stripped;
  }

  looksLikeStructuredPayload(text) {
    if (!text) return false;
    const first = text[0];
    if (first !== '{' && first !== '[') return false;
    try {
      JSON.parse(text);
      return true;
    } catch {
      return false;
    }
  }

  receiptField(value) {
    if (typeof value !== 'string') return '-';
    const cleaned = value.trim();
    return cleaned || '-';
  }
}

window.addEventListener('DOMContentLoaded', () => {
  // Global entrypoint for future module extension (streaming, avatars, sockets).
  if (!window.__XV7_DISABLE_AUTO_INIT) {
    new Xv7UI();
  }
});

export { Xv7UI };
