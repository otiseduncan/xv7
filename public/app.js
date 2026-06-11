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
  voiceInputSupported = false;

  /** @type {boolean} */
  isListening = false;

  /** @type {string} */
  voiceInputError = '';

  /** @type {boolean} */
  transcriptPending = false;

  /** @type {boolean} */
  speechOutputSupported = false;

  /** @type {boolean} */
  speaking = false;

  /** @type {string | null} */
  speakingMessageId = null;

  /** @type {SpeechSynthesisUtterance | null} */
  activeUtterance = null;

  /** @type {SpeechSynthesisVoice[]} */
  availableVoices = [];

  /** @type {{voiceName:string,volume:number,rate:number,pitch:number,muted:boolean}} */
  voiceSettings = {
    voiceName: '',
    volume: 1,
    rate: 1,
    pitch: 1.1,
    muted: false,
  };

  /** @type {string} */
  voiceAvailabilityNote = '';

  /** @type {number} */
  messageCounter = 0;

  /** @type {boolean} */
  operatorModeActive = false;

  /** @type {Array<any>} */
  slashCommands = [];

  /** @type {boolean} */
  slashMenuOpen = false;

  /** @type {string} */
  slashFilter = '';

  /** @type {any | null} */
  pendingOperatorAction = null;

  /** @type {Array<{role:string,text:string,timestamp:string,receiptSummary:string[]}>} */
  visibleConversation = [];

  /** @type {boolean} */
  diagnosticsDrawerOpen = false;

  /** @type {'idle'|'listening'|'captured'|'thinking'|'speaking'|'error'} */
  avatarState = 'idle';

  /** @type {string} */
  avatarLastEvent = 'init';

  /** @type {boolean} */
  avatarClipLoaded = false;

  /** @type {boolean} */
  avatarMediaEnabled = false;

  /** @type {number | null} */
  avatarResetTimer = null;

  avatarClips = {
    idle: '/avatar/xoduz-idle.mp4',
    listening: '/avatar/xoduz-idle.mp4',
    captured: '/avatar/xoduz-idle.mp4',
    thinking: '/avatar/xoduz-thinking.mp4',
    speaking: '/avatar/xoduz-speaking.mp4',
    error: '/avatar/xoduz-idle.mp4',
  };

  voiceState = {
    inputSupported: false,
    listening: false,
    permissionDenied: false,
    transcriptPending: false,
    outputSupported: false,
    speaking: false,
    speakingMessageId: null,
    lastVoiceError: '',
  };

  constructor() {
    this.avatarMediaEnabled = this.resolveAvatarMediaEnabled();
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
      slashMenu: document.getElementById('slashMenu'),
      sendButton: document.getElementById('sendButton'),
      operatorModeToggle: document.getElementById('operatorModeToggle'),
      operatorModeBanner: document.getElementById('operatorModeBanner'),
      operatorConfirmArea: document.getElementById('operatorConfirmArea'),
      micButton: document.getElementById('micButton'),
      copyChatButton: document.getElementById('copyChatButton'),
      copyToast: document.getElementById('copyToast'),
      voiceStatus: document.getElementById('voiceStatus'),
      voiceSettingsStatus: document.getElementById('voiceSettingsStatus'),
      voiceSelect: document.getElementById('voiceSelect'),
      voiceVolume: document.getElementById('voiceVolume'),
      sidebarVoiceVolume: document.getElementById('sidebarVoiceVolume'),
      sidebarVoiceVolumeValue: document.getElementById('sidebarVoiceVolumeValue'),
      voiceRate: document.getElementById('voiceRate'),
      voicePitch: document.getElementById('voicePitch'),
      voiceMute: document.getElementById('voiceMute'),
      sidebarVoiceMuteButton: document.getElementById('sidebarVoiceMuteButton'),
      sidebarVoiceMuteIconOn: document.getElementById('sidebarVoiceMuteIconOn'),
      sidebarVoiceMuteIconOff: document.getElementById('sidebarVoiceMuteIconOff'),
      sidebarVoiceMuteLabel: document.getElementById('sidebarVoiceMuteLabel'),
      sidebarVoiceMuteState: document.getElementById('sidebarVoiceMuteState'),
      voiceTestButton: document.getElementById('voiceTestButton'),
      voiceStopButton: document.getElementById('voiceStopButton'),
      avatarCard: document.getElementById('avatarCard'),
      avatarToggleButton: document.getElementById('avatarToggleButton'),
      avatarCardBody: document.getElementById('avatarCardBody'),
      avatarShell: document.getElementById('avatarShell'),
      avatarVideo: document.getElementById('avatarVideo'),
      avatarFallback: document.getElementById('avatarFallback'),
      avatarStateText: document.getElementById('avatarStateText'),
      avatarVoiceLabel: document.getElementById('avatarVoiceLabel'),
      avatarDiagState: document.getElementById('avatarDiagState'),
      avatarDiagClip: document.getElementById('avatarDiagClip'),
      avatarDiagLoaded: document.getElementById('avatarDiagLoaded'),
      avatarDiagVisible: document.getElementById('avatarDiagVisible'),
      avatarDiagEvent: document.getElementById('avatarDiagEvent'),
      voiceDiagInput: document.getElementById('voiceDiagInput'),
      voiceDiagMicState: document.getElementById('voiceDiagMicState'),
      voiceDiagOutput: document.getElementById('voiceDiagOutput'),
      voiceDiagSpeaking: document.getElementById('voiceDiagSpeaking'),
      voiceDiagVoiceCount: document.getElementById('voiceDiagVoiceCount'),
      voiceDiagSelected: document.getElementById('voiceDiagSelected'),
      voiceDiagVolume: document.getElementById('voiceDiagVolume'),
      voiceDiagRate: document.getElementById('voiceDiagRate'),
      voiceDiagPitch: document.getElementById('voiceDiagPitch'),
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

  resolveAvatarMediaEnabled() {
    const bodyValue = String(document.body?.dataset?.avatarMedia || '').toLowerCase();
    if (bodyValue === 'off' || bodyValue === 'disabled') return false;

    const storedValue = String(window.localStorage?.getItem('xv7-avatar-media') || '').toLowerCase();
    if (storedValue === 'off' || storedValue === 'disabled') return false;
    if (storedValue === 'on' || storedValue === 'enabled') return true;

    const runtimeValue = window.XV7_ENABLE_AVATAR_MEDIA;
    if (runtimeValue === false) return false;
    if (runtimeValue === true) return true;

    return true;
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

    this.els.promptInput.addEventListener('input', () => {
      this.handlePromptInputChanged();
    });

    if (this.els.operatorModeToggle) {
      this.els.operatorModeToggle.addEventListener('click', () => {
        void this.toggleOperatorMode();
      });
    }

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

    if (this.els.voiceSelect) {
      this.els.voiceSelect.addEventListener('change', () => {
        this.voiceSettings.voiceName = this.els.voiceSelect.value;
        this.saveVoicePreferences();
        this.renderVoiceDiagnostics();
      });
    }

    if (this.els.voiceVolume) {
      this.els.voiceVolume.addEventListener('input', () => {
        this.setVoiceVolume(this.els.voiceVolume.value);
      });
    }

    if (this.els.sidebarVoiceVolume) {
      this.els.sidebarVoiceVolume.addEventListener('input', () => {
        this.setVoiceVolume(this.els.sidebarVoiceVolume.value);
      });
    }

    if (this.els.voiceRate) {
      this.els.voiceRate.addEventListener('input', () => {
        this.voiceSettings.rate = this.clampVoiceNumber(this.els.voiceRate.value, 0.5, 2, 1);
        this.saveVoicePreferences();
        this.renderVoiceDiagnostics();
      });
    }

    if (this.els.voicePitch) {
      this.els.voicePitch.addEventListener('input', () => {
        this.voiceSettings.pitch = this.clampVoiceNumber(this.els.voicePitch.value, 0.5, 2, 1.1);
        this.saveVoicePreferences();
        this.renderVoiceDiagnostics();
      });
    }

    if (this.els.voiceMute) {
      this.els.voiceMute.addEventListener('change', () => {
        this.setVoiceMuted(Boolean(this.els.voiceMute.checked));
      });
    }

    if (this.els.sidebarVoiceMuteButton) {
      this.els.sidebarVoiceMuteButton.addEventListener('click', () => {
        this.setVoiceMuted(!this.voiceSettings.muted);
      });
    }

    if (this.els.voiceTestButton) {
      this.els.voiceTestButton.addEventListener('click', () => {
        void this.playVoiceSample();
      });
    }

    if (this.els.voiceStopButton) {
      this.els.voiceStopButton.addEventListener('click', () => {
        this.stopVoicePlayback();
      });
    }

    if (this.els.avatarToggleButton) {
      this.els.avatarToggleButton.addEventListener('click', () => {
        const card = this.els.avatarCard;
        if (!card) return;
        const collapsed = card.classList.toggle('collapsed');
        this.els.avatarToggleButton.setAttribute('aria-expanded', String(!collapsed));
        this.els.avatarToggleButton.textContent = collapsed ? 'Avatar ▸' : 'Avatar ▾';
        this.renderAvatarDiagnostics();
      });
    }

    if (this.els.avatarVideo) {
      this.els.avatarVideo.addEventListener('loadeddata', () => {
        this.avatarClipLoaded = true;
        this.renderAvatarDiagnostics();
      });
      this.els.avatarVideo.addEventListener('error', () => {
        this.avatarClipLoaded = false;
        this.renderAvatarDiagnostics();
      });
    }

    window.addEventListener('xv7:voice-listening-start', () => {
      this.setAvatarState('listening', 'voice-listening-start');
    });
    window.addEventListener('xv7:voice-listening-stop', () => {
      this.setAvatarState(this.transcriptPending ? 'captured' : 'idle', 'voice-listening-stop');
      if (this.transcriptPending) this.scheduleAvatarReset('idle', 1200);
    });
    window.addEventListener('xv7:voice-transcript-captured', () => {
      this.setAvatarState('captured', 'voice-transcript-captured');
      this.scheduleAvatarReset('idle', 1300);
    });
    window.addEventListener('xv7:voice-speaking-start', () => {
      this.setAvatarState('speaking', 'voice-speaking-start');
    });
    window.addEventListener('xv7:voice-speaking-stop', () => {
      this.setAvatarState('idle', 'voice-speaking-stop');
    });
    window.addEventListener('xv7:voice-error', () => {
      this.setAvatarState('error', 'voice-error');
      this.scheduleAvatarReset('idle', 1800);
    });
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
    await this.refreshSlashCommands();
    this.renderOperatorModeUi();
    this.loadVoicePreferences();
    this.setupVoiceInput();
    this.setupVoiceOutput();
    this.refreshVoiceVoices();
    this.renderVoiceDiagnostics();
    this.initializeAvatar();
  }

  async toggleOperatorMode() {
    this.operatorModeActive = !this.operatorModeActive;
    this.statusSummary.operatorMode = this.operatorModeActive ? 'Operator Active' : 'Read-only';
    this.renderStatusStrip();
    this.renderOperatorModeUi();
    await this.refreshSlashCommands();
    this.handlePromptInputChanged();
    if (!this.operatorModeActive) {
      this.pendingOperatorAction = null;
      this.renderPendingOperatorAction();
    }
  }

  renderOperatorModeUi() {
    if (this.els.operatorModeToggle) {
      this.els.operatorModeToggle.setAttribute('aria-pressed', this.operatorModeActive ? 'true' : 'false');
      this.els.operatorModeToggle.textContent = this.operatorModeActive ? 'Operator Mode: ON' : 'Operator Mode: OFF';
      this.els.operatorModeToggle.classList.toggle('operator-mode-on', this.operatorModeActive);
    }
    if (this.els.operatorModeBanner) {
      this.els.operatorModeBanner.classList.toggle('hidden', !this.operatorModeActive);
    }
  }

  async refreshSlashCommands() {
    try {
      const payload = await this.fetchJson(`/api/operator/commands?operator_mode=${this.operatorModeActive ? 'true' : 'false'}`, {
        method: 'GET',
      });
      this.slashCommands = Array.isArray(payload?.commands) ? payload.commands : [];
    } catch {
      this.slashCommands = [];
    }
    this.renderSlashMenu();
  }

  handlePromptInputChanged() {
    const text = String(this.els.promptInput.value || '');
    const trimmed = text.trimStart();
    if (!trimmed.startsWith('/')) {
      this.slashMenuOpen = false;
      this.slashFilter = '';
      this.renderSlashMenu();
      return;
    }

    this.slashMenuOpen = true;
    this.slashFilter = trimmed.slice(1).toLowerCase();
    this.renderSlashMenu();
  }

  groupedSlashCommands() {
    const groups = {
      read_only: [],
      mutation: [],
      high_risk: [],
      vscode: [],
    };
    this.slashCommands.forEach((item) => {
      if (!item || typeof item !== 'object') return;
      const slash = String(item.slash || '');
      const category = String(item.category || '');
      const visible = Boolean(item.visible);
      if (!visible) return;
      if (this.slashFilter && !slash.toLowerCase().includes(this.slashFilter)) return;

      if (category.includes('high_risk')) {
        groups.high_risk.push(item);
      } else if (category.includes('vscode')) {
        groups.vscode.push(item);
      } else if (String(item.mode) === 'read_only') {
        groups.read_only.push(item);
      } else {
        groups.mutation.push(item);
      }
    });
    return groups;
  }

  renderSlashMenu() {
    const menu = this.els.slashMenu;
    if (!menu) return;
    menu.innerHTML = '';
    menu.classList.toggle('hidden', !this.slashMenuOpen);
    if (!this.slashMenuOpen) return;

    const groups = this.groupedSlashCommands();
    const labels = [
      ['read_only', 'Read-only Scan Commands'],
      ['mutation', 'Operator Mutation Commands'],
      ['high_risk', 'High-risk Commands'],
      ['vscode', 'VS Code Commands'],
    ];

    labels.forEach(([key, label]) => {
      const items = groups[key] || [];
      if (!items.length) return;
      const section = document.createElement('div');
      section.className = 'slash-group';

      const title = document.createElement('p');
      title.className = 'slash-group-title';
      title.textContent = label;
      section.append(title);

      items.forEach((item) => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'slash-item';
        row.disabled = !Boolean(item.enabled);
        const risk = String(item.risk_level || 'low');
        row.textContent = `${item.slash} (${risk})`;
        row.addEventListener('click', () => {
          this.els.promptInput.value = `${item.slash} `;
          this.els.promptInput.focus();
          this.slashMenuOpen = false;
          this.renderSlashMenu();
        });
        section.append(row);
      });

      menu.append(section);
    });
  }

  renderPendingOperatorAction() {
    const mount = this.els.operatorConfirmArea;
    if (!mount) return;
    mount.innerHTML = '';
    if (!this.pendingOperatorAction) {
      mount.classList.add('hidden');
      return;
    }
    mount.classList.remove('hidden');

    const pending = this.pendingOperatorAction;
    const wrapper = document.createElement('div');
    wrapper.className = 'operator-confirm-card';

    const title = document.createElement('p');
    title.className = 'operator-confirm-title';
    title.textContent = "I'm ready to perform this operator action, but I need confirmation first.";

    const details = document.createElement('div');
    details.className = 'operator-confirm-grid';
    this.appendReceiptField(details, 'Action', String(pending.command_name || '-'));
    this.appendReceiptField(details, 'Target', String(pending.target || '-'));
    this.appendReceiptField(details, 'Mode', 'Operator Mode');
    this.appendReceiptField(details, 'Risk level', String(pending.risk_level || 'unknown'));
    this.appendReceiptField(details, 'Can this be undone', pending.reversible ? 'Possibly' : 'No, not from XV7');
    this.appendReceiptField(details, 'Command preview', String(pending.command_preview || '-'));
    this.appendReceiptField(details, 'Status', 'Pending confirmation');

    const typedWrap = document.createElement('div');
    let typedInput = null;
    if (pending.requires_typed_confirmation) {
      typedWrap.className = 'operator-typed-confirm-wrap';
      const typedLabel = document.createElement('label');
      typedLabel.className = 'operator-typed-confirm-label';
      typedLabel.textContent = `Type: ${String(pending.confirmation_phrase || '')}`;
      typedInput = document.createElement('input');
      typedInput.type = 'text';
      typedInput.className = 'operator-typed-confirm-input';
      typedInput.placeholder = 'Type exact confirmation phrase';
      typedWrap.append(typedLabel, typedInput);
    }

    const actions = document.createElement('div');
    actions.className = 'operator-confirm-actions';
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'xv7-control-button';
    cancelButton.textContent = 'Cancel';
    cancelButton.addEventListener('click', () => {
      void this.cancelPendingOperatorAction();
    });

    const confirmButton = document.createElement('button');
    confirmButton.type = 'button';
    confirmButton.className = 'xv7-control-button operator-confirm-exec';
    confirmButton.textContent = 'Confirm Action';
    confirmButton.addEventListener('click', () => {
      const typed = typedInput ? typedInput.value : '';
      void this.confirmPendingOperatorAction(typed);
    });
    actions.append(cancelButton, confirmButton);

    wrapper.append(title, details);
    if (typedWrap.childElementCount) wrapper.append(typedWrap);
    wrapper.append(actions);
    mount.append(wrapper);
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

    this.setAvatarState('thinking', 'message-sent');

    this.showAlert('', false);
    this.lockInput(true);
    this.setHardwareLoad('Inference', 74);

    try {
      await this.ensureSession();

      this.appendMessageCard('user', raw, null, null, this.nowIso());
      this.els.promptInput.value = '';
      this.slashMenuOpen = false;
      this.renderSlashMenu();
      this.transcriptPending = false;
      this.voiceInputError = '';
      this.setVoiceStatus('');
      this.voiceState.transcriptPending = false;
      this.voiceState.lastVoiceError = '';
      this.renderVoiceDiagnostics();

      if (raw.startsWith('/')) {
        await this.sendSlashCommand(raw);
        this.memoryLogCount += 1;
        this.updateSessionTelemetry();
        this.setHardwareLoad('Ready', 12);
        this.setAvatarState('idle', 'operator-stage-response');
        return;
      }

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

        const assistantArticle = this.appendMessageCard(
          'assistant',
          assistantText || 'No assistant content returned.',
          reasoningText,
          assistantMeta,
          this.inferAssistantTimestamp(assistantMeta),
        );

        this.setAvatarState('idle', 'assistant-response-received');

        const spokenText = String(assistantText || 'No assistant content returned.').trim();
        if (spokenText) {
          this.startSpeechPlayback(spokenText, {
            messageId: assistantArticle?.dataset?.messageId || null,
            startStatus: 'Reading response aloud...',
            stopStatus: 'Read-aloud stopped.',
            failStatus: 'Browser blocked voice playback. Try clicking Read again.',
          });
        }

        this.renderModelUseReceipt(data?.metadata?.model_use_receipt);
        this.renderOperatorActivity(data?.metadata?.operator_action_history);
        this.updateStatusFromHistory(data?.metadata?.operator_action_history);

        const operatorHistory = Array.isArray(data?.metadata?.operator_action_history)
          ? data.metadata.operator_action_history
          : [];
        const hasOperatorFailure = operatorHistory.some((item) => {
          const status = String(item?.status || '').toLowerCase();
          return status === 'failed' || status === 'denied';
        });
        if (hasOperatorFailure) {
          this.setAvatarState('error', 'operator-action-failed');
          this.scheduleAvatarReset('idle', 1700);
        }

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
      this.setAvatarState('error', 'message-error');
      this.scheduleAvatarReset('idle', 1800);
    } finally {
      this.lockInput(false);
    }
  }

  async ensureSession() {
    if (this.currentSessionId) return;
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

  async sendSlashCommand(commandText) {
    let payload;
    try {
      payload = await this.fetchJson('/api/operator/stage', {
        method: 'POST',
        body: JSON.stringify({
          session_id: this.currentSessionId,
          command_text: commandText,
          operator_mode: this.operatorModeActive,
        }),
      });
    } catch (error) {
      this.showAlert(this.humanizeError(error), true);
      return;
    }

    const receipt = payload?.receipt && typeof payload.receipt === 'object' ? payload.receipt : null;
    const assistantMeta = {
      visible_text: payload?.answer || '',
      context_receipt: {},
      operator_receipts: receipt ? [receipt] : [],
      memory_receipts: [],
      model_use_receipt: {},
      policy_provenance: { policy_source: 'operator_mode_slash' },
      warnings: [],
      action_history_refs: receipt?.action_id ? [receipt.action_id] : [],
    };
    this.appendMessageCard('assistant', payload?.answer || 'Operator action processed.', null, assistantMeta, this.nowIso());

    this.pendingOperatorAction = payload?.pending_action || null;
    this.renderPendingOperatorAction();

    if (receipt) {
      this.renderOperatorActivity([receipt]);
      this.updateStatusFromHistory([receipt]);
    }
  }

  async confirmPendingOperatorAction(typedConfirmation = '') {
    if (!this.pendingOperatorAction || !this.currentSessionId) return;
    let payload;
    try {
      payload = await this.fetchJson('/api/operator/confirm', {
        method: 'POST',
        body: JSON.stringify({
          session_id: this.currentSessionId,
          action_id: this.pendingOperatorAction.action_id,
          typed_confirmation: typedConfirmation || null,
        }),
      });
    } catch (error) {
      this.showAlert(this.humanizeError(error), true);
      return;
    }

    const receipt = payload?.receipt && typeof payload.receipt === 'object' ? payload.receipt : null;
    const assistantMeta = {
      visible_text: payload?.answer || '',
      context_receipt: {},
      operator_receipts: receipt ? [receipt] : [],
      memory_receipts: [],
      model_use_receipt: {},
      policy_provenance: { policy_source: 'operator_mode_confirm' },
      warnings: [],
      action_history_refs: receipt?.action_id ? [receipt.action_id] : [],
    };
    this.appendMessageCard('assistant', payload?.answer || 'Operator confirmation processed.', null, assistantMeta, this.nowIso());

    this.pendingOperatorAction = payload?.pending_action || null;
    this.renderPendingOperatorAction();

    if (receipt) {
      this.renderOperatorActivity([receipt]);
      this.updateStatusFromHistory([receipt]);
    }
  }

  async cancelPendingOperatorAction() {
    if (!this.pendingOperatorAction || !this.currentSessionId) return;
    let payload;
    try {
      payload = await this.fetchJson('/api/operator/cancel', {
        method: 'POST',
        body: JSON.stringify({
          session_id: this.currentSessionId,
          action_id: this.pendingOperatorAction.action_id,
        }),
      });
    } catch (error) {
      this.showAlert(this.humanizeError(error), true);
      return;
    }

    const receipt = payload?.receipt && typeof payload.receipt === 'object' ? payload.receipt : null;
    const assistantMeta = {
      visible_text: payload?.answer || '',
      context_receipt: {},
      operator_receipts: receipt ? [receipt] : [],
      memory_receipts: [],
      model_use_receipt: {},
      policy_provenance: { policy_source: 'operator_mode_cancel' },
      warnings: [],
      action_history_refs: receipt?.action_id ? [receipt.action_id] : [],
    };
    this.appendMessageCard('assistant', payload?.answer || 'Pending operator action cancelled.', null, assistantMeta, this.nowIso());

    this.pendingOperatorAction = null;
    this.renderPendingOperatorAction();

    if (receipt) {
      this.renderOperatorActivity([receipt]);
      this.updateStatusFromHistory([receipt]);
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
    article.dataset.messageId = `msg-${++this.messageCounter}`;

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

    if (role === 'assistant') {
      const readAloudButton = document.createElement('button');
      readAloudButton.type = 'button';
      readAloudButton.className = 'message-audio-button';
      readAloudButton.dataset.messageId = article.dataset.messageId;
      readAloudButton.textContent = 'Read';
      readAloudButton.addEventListener('click', () => {
        void this.toggleReadAloud(article);
      });
      actions.append(readAloudButton);
      this.renderReadAloudButton(readAloudButton, article.dataset.messageId);
    }

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

    return article;
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
      compactReceipts.push(chip.textContent || `${actionName} ${status} ${readOnly}`);
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
        compactReceipts.push(chip.textContent);
      });
    } else if (contextReceipt && typeof contextReceipt.compact === 'string' && contextReceipt.compact.trim()) {
      const layered = this.parseLayeredContextFromCompact(contextReceipt.compact);

      if (layered.length > 0) {
        layered.forEach((item) => {
          const chip = document.createElement('span');
          chip.className = `receipt-chip receipt-chip-${item.label.toLowerCase()}`;
          chip.textContent = `${item.label}: ${item.recordId}`;
          chipRow.append(chip);
          compactReceipts.push(chip.textContent);
        });
      } else if (!contextReceipt.compact.toLowerCase().includes('operator receipt')) {
        const chip = document.createElement('span');
        chip.className = 'receipt-chip';
        const contextSummary = this.summarizeContextReceipt(contextReceipt.compact);
        chip.textContent = `Context: ${contextSummary}`;
        chipRow.append(chip);
        compactReceipts.push(chip.textContent);
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
      compactReceipts.push(chip.textContent);
    });

    const modelUseReceipt = meta.model_use_receipt && typeof meta.model_use_receipt === 'object' ? meta.model_use_receipt : null;
    if (typeof modelUseReceipt?.model_tag === 'string' && modelUseReceipt.model_tag.trim()) {
      const chip = document.createElement('span');
      chip.className = 'receipt-chip';
      chip.textContent = `Model: ${modelUseReceipt.model_tag.trim()}`;
      chipRow.append(chip);
      compactReceipts.push(chip.textContent);
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

  normalizeSpeechText(text) {
    const raw = this.stripReasoningTokens(String(text || ''));
    if (!raw) return '';

    const blockedPrefixes = [
      'operator receipt:',
      'context receipt:',
      'memory receipt:',
      'model receipt:',
      'receipt:',
      'receipts:',
      'system:',
      'memory:',
      'knowledge:',
      'focus:',
      'verified:',
      'model:',
      'sources:',
      'diagnostics:',
      'metadata:',
    ];

    const withoutFences = raw
      .replace(/```[a-z0-9_-]*\s*/gi, '\n')
      .replace(/```/g, '\n');

    const spokenLines = withoutFences
      .split('\n')
      .map((line) => line.trim())
      .map((line) => line.replace(/^#{1,6}\s+/, ''))
      .map((line) => line.replace(/`([^`]*)`/g, '$1'))
      .map((line) => line.replace(/\*\*|__|\*|_/g, ''))
      .map((line) => {
        const bullet = line.match(/^[-*•]\s+(.+)$/);
        if (!bullet) return line;
        const content = bullet[1].trim();
        if (!content) return '';
        return /[.!?;:]$/.test(content) ? content : `${content}.`;
      })
      .filter((line) => {
        if (!line) return false;
        const lowered = line.toLowerCase();
        if (blockedPrefixes.some((prefix) => lowered.startsWith(prefix))) return false;
        if (/\bxv7-(system|memory|knowledge|focus|verified)-\d+\b/i.test(line)) return false;
        if (/\bqwen\d*:[a-z0-9_.-]+\b/i.test(line)) return false;
        return true;
      });

    const normalized = spokenLines
      .join(' ')
      .replace(/^\s*Xoduz\s+is\s+pronounced\s+Exodus\.?\s*$/i, 'Exodus.')
      .replace(/\bX-O-D-U-Z\b/g, 'X O D U Z')
      .replace(/\bXoduz\b/gi, 'Exodus')
      .replace(/\bXV\s*-?\s*7\b/gi, 'X V Seven')
      .replace(/\s+/g, ' ')
      .trim();

    return normalized;
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

    this.voiceInputSupported = Boolean(SpeechRecognitionCtor);
    this.voiceState.inputSupported = this.voiceInputSupported;
    if (!this.voiceInputSupported) {
      this.els.micButton.disabled = true;
      this.els.micButton.setAttribute('aria-label', 'Start voice input');
      this.els.micButton.title = 'Voice input is not supported in this browser.';
      this.setVoiceStatus('Voice input is not supported in this browser.');
      this.voiceState.permissionDenied = false;
      this.renderVoiceDiagnostics();
      return;
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      this.isListening = true;
      this.voiceInputError = '';
      this.transcriptPending = false;
      this.voiceState.listening = true;
      this.voiceState.permissionDenied = false;
      this.voiceState.transcriptPending = false;
      this.voiceState.lastVoiceError = '';
      this.els.micButton.classList.add('listening');
      this.els.micButton.textContent = 'Listening...';
      this.els.micButton.setAttribute('aria-label', 'Stop voice input');
      this.els.micButton.title = 'Click to stop voice input.';
      this.setVoiceStatus('Listening...');
      this.dispatchVoiceEvent('xv7:voice-listening-start');
      this.renderVoiceDiagnostics();
    };

    recognition.onend = () => {
      this.isListening = false;
      this.voiceState.listening = false;
      this.els.micButton.classList.remove('listening');
      this.els.micButton.textContent = 'Mic';
      this.els.micButton.setAttribute('aria-label', 'Start voice input');
      this.els.micButton.title = 'Start voice input.';
      if (this.voiceInputError) {
        this.setVoiceStatus(this.voiceInputError);
      } else if (this.transcriptPending) {
        this.setVoiceStatus('Voice captured. Review and send.');
      } else {
        this.setVoiceStatus('Voice input ready.');
      }
      this.dispatchVoiceEvent('xv7:voice-listening-stop');
      this.renderVoiceDiagnostics();
    };

    recognition.onresult = (event) => {
      const result = event.results?.[0]?.[0]?.transcript;
      if (!result || typeof result !== 'string') return;
      this.transcriptPending = true;
      this.voiceState.transcriptPending = true;
      this.els.promptInput.value = this.mergeTranscript(this.els.promptInput.value, result.trim());
      this.els.promptInput.focus();
      this.showCopyToast('Voice transcript added to prompt.');
      this.dispatchVoiceEvent('xv7:voice-transcript-captured', { transcript: result.trim() });
      this.renderVoiceDiagnostics();
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        this.voiceInputError = 'Microphone permission was denied.';
        this.voiceState.permissionDenied = true;
        this.voiceState.lastVoiceError = 'Microphone permission was denied.';
        this.showAlert('Microphone permission was denied.', true, 2200);
        this.setVoiceStatus('Microphone permission was denied. Allow microphone permission in the browser to use voice input.');
        this.dispatchVoiceEvent('xv7:voice-error', { error: event.error });
        this.renderVoiceDiagnostics();
        return;
      }
      if (event.error === 'no-speech') {
        this.voiceInputError = 'No speech was detected. Try again.';
        this.voiceState.lastVoiceError = 'No speech was detected. Try again.';
        this.showAlert('No speech was detected. Try again.', true, 1800);
        this.setVoiceStatus('Recognition error.');
        this.dispatchVoiceEvent('xv7:voice-error', { error: event.error });
        this.renderVoiceDiagnostics();
        return;
      }
      this.voiceInputError = 'Voice input failed to start.';
      this.voiceState.lastVoiceError = 'Voice input failed to start.';
      this.showAlert('Voice input failed to start.', true, 1800);
      this.setVoiceStatus('Recognition error.');
      this.dispatchVoiceEvent('xv7:voice-error', { error: event.error });
      this.renderVoiceDiagnostics();
    };

    this.speechRecognition = recognition;
    this.els.micButton.disabled = false;
    this.els.micButton.title = 'Start voice input.';
    this.setVoiceStatus('Voice input ready.');
    this.renderVoiceDiagnostics();
  }

  toggleVoiceInput() {
    if (!this.voiceInputSupported || !this.speechRecognition) {
      this.showAlert('Voice input is not supported in this browser.', true, 2200);
      return;
    }

    if (this.isListening) {
      this.speechRecognition.stop();
      return;
    }

    this.voiceInputError = '';
    this.voiceState.lastVoiceError = '';
    this.speechRecognition.start();
  }

  setupVoiceOutput() {
    this.speechOutputSupported = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
    this.voiceState.outputSupported = this.speechOutputSupported;

    if (!this.speechOutputSupported) {
      this.availableVoices = [];
      this.voiceAvailabilityNote = 'No browser voices are available.';
      this.renderVoiceDiagnostics();
      return;
    }

    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = () => {
        this.refreshVoiceVoices();
      };
    }

    this.renderVoiceDiagnostics();
  }

  loadVoicePreferences() {
    try {
      const voiceName = window.localStorage.getItem('xv7.voice.voiceName');
      const volume = window.localStorage.getItem('xv7.voice.volume');
      const rate = window.localStorage.getItem('xv7.voice.rate');
      const pitch = window.localStorage.getItem('xv7.voice.pitch');
      const muted = window.localStorage.getItem('xv7.voice.muted');

      this.voiceSettings.voiceName = typeof voiceName === 'string' ? voiceName : '';
      this.voiceSettings.volume = this.clampVoiceNumber(volume, 0, 1, 1);
      this.voiceSettings.rate = this.clampVoiceNumber(rate, 0.5, 2, 1);
      this.voiceSettings.pitch = this.clampVoiceNumber(pitch, 0.5, 2, 1.1);
      this.voiceSettings.muted = muted === 'true';
    } catch {
      this.voiceSettings.voiceName = '';
      this.voiceSettings.volume = 1;
      this.voiceSettings.rate = 1;
      this.voiceSettings.pitch = 1.1;
      this.voiceSettings.muted = false;
    }
  }

  saveVoicePreferences() {
    try {
      window.localStorage.setItem('xv7.voice.voiceName', this.voiceSettings.voiceName || '');
      window.localStorage.setItem('xv7.voice.volume', String(this.voiceSettings.volume));
      window.localStorage.setItem('xv7.voice.rate', String(this.voiceSettings.rate));
      window.localStorage.setItem('xv7.voice.pitch', String(this.voiceSettings.pitch));
      window.localStorage.setItem('xv7.voice.muted', String(this.voiceSettings.muted));
    } catch {
      // Best-effort only.
    }
  }

  clampVoiceNumber(value, min, max, fallback) {
    const parsed = Number.parseFloat(String(value));
    if (!Number.isFinite(parsed)) return fallback;
    return Math.min(max, Math.max(min, parsed));
  }

  refreshVoiceVoices() {
    if (!this.speechOutputSupported || !window.speechSynthesis) {
      this.availableVoices = [];
      this.renderVoiceDiagnostics();
      return;
    }

    const voices = typeof window.speechSynthesis.getVoices === 'function' ? window.speechSynthesis.getVoices() : [];
    this.availableVoices = Array.isArray(voices) ? voices.filter((voice) => voice && typeof voice.name === 'string') : [];

    this.renderVoiceSelectOptions();
    this.applyPreferredVoiceIfNeeded();
    this.renderVoiceDiagnostics();
  }

  renderVoiceSelectOptions() {
    if (!this.els.voiceSelect) return;

    const currentValue = this.voiceSettings.voiceName || '';
    const voices = [...this.availableVoices].sort((left, right) => {
      const leftLabel = `${left.lang || ''} ${left.name || ''}`.toLowerCase();
      const rightLabel = `${right.lang || ''} ${right.name || ''}`.toLowerCase();
      return leftLabel.localeCompare(rightLabel);
    });

    this.els.voiceSelect.innerHTML = '';

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Browser default';
    this.els.voiceSelect.append(defaultOption);

    voices.forEach((voice) => {
      const option = document.createElement('option');
      option.value = voice.name || '';
      option.textContent = `${voice.name || 'Unnamed voice'} (${voice.lang || 'unknown'})`;
      this.els.voiceSelect.append(option);
    });

    this.els.voiceSelect.value = voices.some((voice) => voice.name === currentValue) ? currentValue : '';
  }

  applyPreferredVoiceIfNeeded() {
    if (!this.availableVoices.length) {
      this.voiceAvailabilityNote = 'No browser voices are available.';
      this.voiceSettings.voiceName = '';
      this.syncVoiceSettingsToControls();
      return;
    }

    const currentVoice = this.availableVoices.find((voice) => voice.name === this.voiceSettings.voiceName);
    if (currentVoice) {
      this.voiceAvailabilityNote = this.isFemaleLikeVoice(currentVoice)
        ? `Using ${currentVoice.name}.`
        : 'Using browser default voice. Select a different voice if needed.';
      this.syncVoiceSettingsToControls();
      return;
    }

    const preferredVoice = this.choosePreferredVoice(this.availableVoices);
    this.voiceSettings.voiceName = preferredVoice?.name || '';
    this.voiceAvailabilityNote = preferredVoice && this.isFemaleLikeVoice(preferredVoice)
      ? `Using ${preferredVoice.name}.`
      : 'Using browser default voice. Select a different voice if needed.';
    this.saveVoicePreferences();
    this.syncVoiceSettingsToControls();
  }

  choosePreferredVoice(voices) {
    if (!Array.isArray(voices) || !voices.length) return null;

    const femaleHints = ['female', 'woman', 'jenny', 'aria', 'sonia', 'zira', 'susan', 'samantha', 'victoria', 'google us english', 'microsoft zira', 'microsoft jenny', 'microsoft aria'];
    const femaleVoice = voices.find((voice) => {
      const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
      return femaleHints.some((hint) => haystack.includes(hint));
    });
    if (femaleVoice) return femaleVoice;

    const englishVoice = voices.find((voice) => String(voice.lang || '').toLowerCase().startsWith('en'));
    if (englishVoice) return englishVoice;

    return voices.find((voice) => voice.default) || voices[0] || null;
  }

  isFemaleLikeVoice(voice) {
    if (!voice) return false;
    const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
    return ['female', 'woman', 'jenny', 'aria', 'sonia', 'zira', 'susan', 'samantha', 'victoria', 'google us english', 'microsoft zira', 'microsoft jenny', 'microsoft aria']
      .some((hint) => haystack.includes(hint));
  }

  syncVoiceSettingsToControls() {
    if (this.els.voiceSelect) this.els.voiceSelect.value = this.voiceSettings.voiceName || '';
    if (this.els.voiceVolume) this.els.voiceVolume.value = String(this.voiceSettings.volume);
    if (this.els.sidebarVoiceVolume) this.els.sidebarVoiceVolume.value = String(this.voiceSettings.volume);
    if (this.els.sidebarVoiceVolumeValue) this.els.sidebarVoiceVolumeValue.textContent = `${Math.round(this.voiceSettings.volume * 100)}%`;
    if (this.els.voiceRate) this.els.voiceRate.value = String(this.voiceSettings.rate);
    if (this.els.voicePitch) this.els.voicePitch.value = String(this.voiceSettings.pitch);
    if (this.els.voiceMute) this.els.voiceMute.checked = Boolean(this.voiceSettings.muted);
    if (this.els.sidebarVoiceMuteButton) {
      const isMuted = Boolean(this.voiceSettings.muted);
      this.els.sidebarVoiceMuteButton.setAttribute('aria-pressed', String(isMuted));
      this.els.sidebarVoiceMuteButton.setAttribute('aria-label', isMuted ? 'Unmute voice output' : 'Mute voice output');
    }
    if (this.els.sidebarVoiceMuteIconOn) {
      this.els.sidebarVoiceMuteIconOn.classList.toggle('hidden', Boolean(this.voiceSettings.muted));
    }
    if (this.els.sidebarVoiceMuteIconOff) {
      this.els.sidebarVoiceMuteIconOff.classList.toggle('hidden', !Boolean(this.voiceSettings.muted));
    }
    if (this.els.sidebarVoiceMuteLabel) {
      this.els.sidebarVoiceMuteLabel.textContent = this.voiceSettings.muted ? 'Unmute output' : 'Mute output';
    }
    if (this.els.sidebarVoiceMuteState) {
      this.els.sidebarVoiceMuteState.textContent = this.voiceSettings.muted ? 'Muted' : 'On';
    }
    if (this.els.avatarVoiceLabel) {
      const selected = this.availableVoices.find((voice) => voice.name === this.voiceSettings.voiceName) || this.choosePreferredVoice(this.availableVoices);
      this.els.avatarVoiceLabel.textContent = `Voice: ${selected?.name || 'Browser default'}`;
    }
  }

  initializeAvatar() {
    if (!this.els.avatarVideo) return;
    this.applyAvatarClipForState(this.avatarState);
    this.renderAvatarStateUI();
    this.renderAvatarDiagnostics();
  }

  scheduleAvatarReset(nextState = 'idle', delayMs = 1400) {
    if (this.avatarResetTimer) {
      window.clearTimeout(this.avatarResetTimer);
    }
    this.avatarResetTimer = window.setTimeout(() => {
      this.setAvatarState(nextState, 'state-timeout');
      this.avatarResetTimer = null;
    }, delayMs);
  }

  setAvatarState(nextState, sourceEvent = '') {
    const allowed = ['idle', 'listening', 'captured', 'thinking', 'speaking', 'error'];
    const normalized = allowed.includes(nextState) ? nextState : 'idle';
    this.avatarState = normalized;
    this.avatarLastEvent = sourceEvent || normalized;

    if (normalized === 'speaking' || normalized === 'listening') {
      if (this.avatarResetTimer) {
        window.clearTimeout(this.avatarResetTimer);
        this.avatarResetTimer = null;
      }
    }

    this.applyAvatarClipForState(normalized);
    this.renderAvatarStateUI();
    this.renderAvatarDiagnostics();
  }

  applyAvatarClipForState(stateName) {
    const clip = this.avatarClips[stateName] || this.avatarClips.idle;
    const video = this.els.avatarVideo;
    if (!video || !clip) {
      this.avatarClipLoaded = false;
      return;
    }

    if (!this.avatarMediaEnabled) {
      this.avatarClipLoaded = false;
      this.avatarLastEvent = this.avatarLastEvent || 'avatar-media-disabled';
      if (video.getAttribute('src')) {
        video.removeAttribute('src');
      }
      return;
    }

    const currentSrc = video.getAttribute('src') || '';
    if (currentSrc !== clip) {
      this.avatarClipLoaded = false;
      video.setAttribute('src', clip);
      video.load();
    }

    const playResult = video.play();
    if (playResult && typeof playResult.catch === 'function') {
      playResult.catch(() => {
        this.avatarClipLoaded = false;
        this.renderAvatarDiagnostics();
      });
    }
  }

  avatarStateLabel(stateName) {
    const labels = {
      idle: 'Idle',
      listening: 'Listening',
      captured: 'Captured',
      thinking: 'Thinking',
      speaking: 'Speaking',
      error: 'Voice error',
    };
    return labels[stateName] || 'Idle';
  }

  renderAvatarStateUI() {
    if (this.els.avatarShell) {
      this.els.avatarShell.classList.remove('state-idle', 'state-listening', 'state-captured', 'state-thinking', 'state-speaking', 'state-error');
      this.els.avatarShell.classList.add(`state-${this.avatarState}`);
      this.els.avatarShell.setAttribute('aria-label', `Xoduz avatar state ${this.avatarStateLabel(this.avatarState)}`);
    }
    if (this.els.avatarStateText) {
      this.els.avatarStateText.textContent = this.avatarStateLabel(this.avatarState);
    }
  }

  renderAvatarDiagnostics() {
    const clipPath = this.avatarClips[this.avatarState] || this.avatarClips.idle || '';
    const clipName = this.avatarMediaEnabled
      ? (clipPath.split('/').pop() || 'fallback')
      : ((clipPath.split('/').pop() || 'fallback') + ' (disabled)');
    const visible = this.els.avatarCard ? !this.els.avatarCard.classList.contains('collapsed') : false;

    if (this.els.avatarDiagState) this.els.avatarDiagState.textContent = this.avatarState;
    if (this.els.avatarDiagClip) this.els.avatarDiagClip.textContent = clipName;
    if (this.els.avatarDiagLoaded) this.els.avatarDiagLoaded.textContent = this.avatarClipLoaded ? 'yes' : 'no';
    if (this.els.avatarDiagVisible) this.els.avatarDiagVisible.textContent = visible ? 'yes' : 'no';
    if (this.els.avatarDiagEvent) this.els.avatarDiagEvent.textContent = this.avatarLastEvent || 'init';

    if (this.els.avatarFallback) {
      this.els.avatarFallback.classList.toggle('hidden', this.avatarClipLoaded);
    }
  }

  setVoiceVolume(value) {
    this.voiceSettings.volume = this.clampVoiceNumber(value, 0, 1, 1);
    this.saveVoicePreferences();
    this.renderVoiceDiagnostics();
  }

  setVoiceMuted(muted) {
    this.voiceSettings.muted = Boolean(muted);
    this.saveVoicePreferences();
    this.renderVoiceDiagnostics();
  }

  buildSpeechUtterance(text) {
    if (!window.SpeechSynthesisUtterance) return null;

    const spokenText = this.normalizeSpeechText(text);
    if (!spokenText) return null;

    const utterance = new window.SpeechSynthesisUtterance(spokenText);
    const selectedVoice = this.availableVoices.find((voice) => voice.name === this.voiceSettings.voiceName) || this.choosePreferredVoice(this.availableVoices);
    if (selectedVoice) {
      utterance.voice = selectedVoice;
      if (selectedVoice.lang) {
        utterance.lang = selectedVoice.lang;
      }
    }
    utterance.volume = this.voiceSettings.muted ? 0 : this.voiceSettings.volume;
    utterance.rate = this.voiceSettings.rate;
    utterance.pitch = this.voiceSettings.pitch;
    return utterance;
  }

  startSpeechPlayback(text, options = {}) {
    if (!this.speechOutputSupported || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      return false;
    }

    const utterance = this.buildSpeechUtterance(text);
    if (!utterance) return false;

    const messageId = options.messageId || null;
    const startStatus = options.startStatus || 'Reading response aloud...';
    const stopStatus = options.stopStatus || 'Read-aloud stopped.';
    const failStatus = options.failStatus || 'Browser blocked voice playback. Try clicking Test Voice again.';

    window.speechSynthesis.cancel();
    if (this.speaking && this.speakingMessageId) {
      this.dispatchVoiceEvent('xv7:voice-speaking-stop', { messageId: this.speakingMessageId });
    }

    utterance.onend = () => {
      this.speaking = false;
      this.speakingMessageId = null;
      this.activeUtterance = null;
      this.voiceState.speaking = false;
      this.voiceState.speakingMessageId = null;
      this.setVoiceStatus(stopStatus);
      this.dispatchVoiceEvent('xv7:voice-speaking-stop', { messageId });
      this.renderVoiceDiagnostics();
      this.updateReadAloudButtons();
    };
    utterance.onerror = () => {
      this.speaking = false;
      this.speakingMessageId = null;
      this.activeUtterance = null;
      this.voiceState.speaking = false;
      this.voiceState.speakingMessageId = null;
      this.voiceState.lastVoiceError = failStatus;
      this.setVoiceStatus(failStatus);
      this.dispatchVoiceEvent('xv7:voice-error', { error: 'speech_output_error', messageId });
      this.dispatchVoiceEvent('xv7:voice-speaking-stop', { messageId });
      this.renderVoiceDiagnostics();
      this.updateReadAloudButtons();
      this.showAlert(failStatus, true, 1800);
    };

    this.speaking = true;
    this.speakingMessageId = messageId;
    this.activeUtterance = utterance;
    this.voiceState.speaking = true;
    this.voiceState.speakingMessageId = messageId;
    this.setVoiceStatus(startStatus);
    this.dispatchVoiceEvent('xv7:voice-speaking-start', { messageId, text });
    this.renderVoiceDiagnostics();
    this.updateReadAloudButtons();

    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      this.speaking = false;
      this.speakingMessageId = null;
      this.activeUtterance = null;
      this.voiceState.speaking = false;
      this.voiceState.speakingMessageId = null;
      this.voiceState.lastVoiceError = failStatus;
      this.setVoiceStatus(failStatus);
      this.renderVoiceDiagnostics();
      this.updateReadAloudButtons();
      this.showAlert(failStatus, true, 1800);
      return false;
    }

    return true;
  }

  stopVoicePlayback() {
    if (!this.speechOutputSupported || !window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    this.speaking = false;
    this.speakingMessageId = null;
    this.activeUtterance = null;
    this.voiceState.speaking = false;
    this.voiceState.speakingMessageId = null;
    this.setVoiceStatus('Voice playback stopped.');
    this.dispatchVoiceEvent('xv7:voice-speaking-stop', {});
    this.renderVoiceDiagnostics();
    this.updateReadAloudButtons();
  }

  async playVoiceSample() {
    const success = this.startSpeechPlayback('Hello Otis. I am Xoduz. This is my selected voice.', {
      startStatus: 'Testing voice output...',
      stopStatus: 'Test voice finished.',
      failStatus: 'Browser blocked voice playback. Try clicking Test Voice again.',
      messageId: 'test-voice',
    });

    if (!success && this.voiceSettings.muted) {
      this.setVoiceStatus('Voice output is muted.');
    }
  }

  mergeTranscript(existingValue, transcript) {
    const current = String(existingValue || '').trim();
    const next = String(transcript || '').trim();
    if (!current) return next;
    if (!next) return current;
    const joiner = /[\n\s]$/.test(existingValue || '') ? '' : ' ';
    return `${existingValue}${joiner}${next}`.trim();
  }

  setVoiceStatus(message) {
    if (!this.els.voiceStatus) return;
    this.els.voiceStatus.textContent = message || '';
  }

  renderVoiceDiagnostics() {
    if (this.els.voiceDiagInput) {
      this.els.voiceDiagInput.textContent = this.voiceState.inputSupported ? 'supported' : 'unsupported';
    }
    if (this.els.voiceDiagMicState) {
      let micState = 'idle';
      if (!this.voiceState.inputSupported) {
        micState = 'unsupported';
      } else if (this.voiceState.permissionDenied) {
        micState = 'denied';
      } else if (this.voiceState.listening) {
        micState = 'listening';
      }
      this.els.voiceDiagMicState.textContent = micState;
    }
    if (this.els.voiceDiagOutput) {
      this.els.voiceDiagOutput.textContent = this.voiceState.outputSupported ? 'yes' : 'no';
    }
    if (this.els.voiceDiagVoiceCount) {
      this.els.voiceDiagVoiceCount.textContent = String(this.availableVoices.length);
    }
    if (this.els.voiceDiagSelected) {
      const selected = this.availableVoices.find((voice) => voice.name === this.voiceSettings.voiceName) || this.choosePreferredVoice(this.availableVoices);
      this.els.voiceDiagSelected.textContent = selected?.name || 'Browser default';
    }
    if (this.els.voiceDiagVolume) {
      this.els.voiceDiagVolume.textContent = this.voiceSettings.volume.toFixed(1);
    }
    if (this.els.voiceDiagRate) {
      this.els.voiceDiagRate.textContent = this.voiceSettings.rate.toFixed(1);
    }
    if (this.els.voiceDiagPitch) {
      this.els.voiceDiagPitch.textContent = this.voiceSettings.pitch.toFixed(1);
    }
    if (this.els.voiceDiagSpeaking) {
      this.els.voiceDiagSpeaking.textContent = this.voiceState.speaking ? 'yes' : 'no';
    }
    if (this.els.voiceSettingsStatus) {
      this.els.voiceSettingsStatus.textContent = this.availableVoices.length
        ? this.voiceAvailabilityNote
        : 'No browser voices are available.';
    }
    this.syncVoiceSettingsToControls();
    this.renderAvatarDiagnostics();
  }

  dispatchVoiceEvent(name, detail = {}) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  renderReadAloudButton(button, messageId) {
    if (!button) return;
    if (!this.speechOutputSupported) {
      button.disabled = true;
      button.textContent = 'Read';
      button.setAttribute('aria-label', 'Read assistant response aloud');
      button.title = 'Read aloud is not supported in this browser.';
      return;
    }

    const isActive = this.speaking && this.speakingMessageId === messageId;
    button.disabled = false;
    button.classList.toggle('speaking', isActive);
    button.textContent = isActive ? 'Stop' : 'Read';
    button.setAttribute('aria-label', isActive ? 'Stop reading aloud' : 'Read assistant response aloud');
    button.title = isActive ? 'Stop reading aloud.' : 'Read assistant response aloud.';
  }

  updateReadAloudButtons() {
    const buttons = this.els.chatTimeline?.querySelectorAll('.message-audio-button') || [];
    buttons.forEach((button) => {
      this.renderReadAloudButton(button, button.dataset.messageId || '');
    });
  }

  async toggleReadAloud(article) {
    const messageId = article?.dataset?.messageId || '';
    const visibleText = article?.querySelector('.chat-visible-text')?.textContent?.trim() || '';
    if (!visibleText) return;

    if (!this.speechOutputSupported || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      this.showAlert('Read aloud is not supported in this browser.', true, 1800);
      return;
    }

    if (this.speaking && this.speakingMessageId === messageId) {
      this.stopVoicePlayback();
      return;
    }

    this.startSpeechPlayback(visibleText, {
      messageId,
      startStatus: 'Reading response aloud...',
      stopStatus: 'Read-aloud stopped.',
      failStatus: 'Browser blocked voice playback. Try clicking Test Voice again.',
    });
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
        lines.push('');
        lines.push('Receipts:');
        entry.receiptSummary.forEach((receiptLine) => {
          lines.push(`- ${receiptLine}`);
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
      if (chips.length) {
        lines.push('');
        lines.push('Receipts:');
        chips.forEach((chipText) => {
          lines.push(`- ${chipText}`);
        });
      }
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
    if (normalizedStatus === 'pending') {
      return `${normalizedAction} pending_confirmation`;
    }
    if (normalizedStatus === 'cancelled') {
      return `${normalizedAction} cancelled`;
    }
    if (normalizedStatus === 'not_implemented') {
      return `${normalizedAction} not_implemented`;
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
    window.__XV7_UI_INSTANCE = new Xv7UI();
  }
});

export { Xv7UI };
