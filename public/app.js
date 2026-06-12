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

  /** @type {Map<string, {copied:boolean, timer:number | null}>} */
  artifactCopyState = new Map();

  /** @type {boolean} */
  diagnosticsDrawerOpen = false;

  /** @type {'now'|'review'|'history'|'library'} */
  brainRecordsView = 'now';

  /** @type {{layer:string,status:string,relevance:string,source:string,search:string,showArchived:boolean,showRawJson:boolean}} */
  brainRecordsFilters = {
    layer: 'all',
    status: 'active',
    relevance: 'all',
    source: 'all',
    search: '',
    showArchived: false,
    showRawJson: false,
  };

  /** @type {Array<any>} */
  brainRecords = [];

  /** @type {Array<any>} */
  brainReviewRecords = [];

  /** @type {Array<any>} */
  brainHistoryRecords = [];

  /** @type {{current:number,review:number,history:number,library:number,reviewBackend:number,historyBackend:number}} */
  brainRecordCounts = {
    current: 0,
    review: 0,
    history: 0,
    library: 0,
    reviewBackend: 0,
    historyBackend: 0,
  };

  /** @type {Record<string, string>} */
  approvedCleanupRecommendations = {};

  /** @type {any | null} */
  latestAssistantMeta = null;

  /** @type {{recordIds:string[],activeFocusId:string,activeFocusSummary:string,prompt:string}|null} */
  activeContextSnapshot = null;

  /** @type {number} */
  brainRecordsLastRefreshAt = 0;

  /** @type {boolean} */
  brainRecordBusy = false;

  /** @type {number} */
  brainRecordsStaleMs = 15000;

  /** @type {string | null} */
  brainRecordEditorId = null;

  /** @type {any | null} */
  brainRecordEditorRecord = null;

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
      brainRecordsStatus: document.getElementById('brainRecordsStatus'),
      brainRecordsRefreshButton: document.getElementById('brainRecordsRefreshButton'),
      brainRecordsList: document.getElementById('brainRecordsList'),
      brainRecordsViews: document.getElementById('brainRecordsViews'),
      brainNowCounts: document.getElementById('brainNowCounts'),
      brainReviewToolbar: document.getElementById('brainReviewToolbar'),
      brainRecordsApplyCleanupButton: document.getElementById('brainRecordsApplyCleanupButton'),
      brainNowFocus: document.getElementById('brainNowFocus'),
      brainNowSelectedRecords: document.getElementById('brainNowSelectedRecords'),
      brainNowAnswerMeta: document.getElementById('brainNowAnswerMeta'),
      brainLibraryControls: document.getElementById('brainLibraryControls'),
      brainLibraryLayerFilter: document.getElementById('brainLibraryLayerFilter'),
      brainLibraryStatusFilter: document.getElementById('brainLibraryStatusFilter'),
      brainLibraryRelevanceFilter: document.getElementById('brainLibraryRelevanceFilter'),
      brainLibrarySourceFilter: document.getElementById('brainLibrarySourceFilter'),
      brainLibrarySearch: document.getElementById('brainLibrarySearch'),
      brainLibraryShowArchived: document.getElementById('brainLibraryShowArchived'),
      brainLibraryShowRawJson: document.getElementById('brainLibraryShowRawJson'),
      brainRecordEditor: document.getElementById('brainRecordEditor'),
      brainRecordEditorId: document.getElementById('brainRecordEditorId'),
      brainRecordEditorLayer: document.getElementById('brainRecordEditorLayer'),
      brainRecordEditorTitle: document.getElementById('brainRecordEditorTitle'),
      brainRecordEditorBody: document.getElementById('brainRecordEditorBody'),
      brainRecordEditorTags: document.getElementById('brainRecordEditorTags'),
      brainRecordEditorStatus: document.getElementById('brainRecordEditorStatus'),
      brainRecordEditorSaveButton: document.getElementById('brainRecordEditorSaveButton'),
      brainRecordEditorCancelButton: document.getElementById('brainRecordEditorCancelButton'),
      brainRecordEditorRaw: document.getElementById('brainRecordEditorRaw'),
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
        void this.refreshBrainRecords();
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

    if (this.els.brainRecordsViews) {
      this.els.brainRecordsViews.addEventListener('click', (event) => {
        const target = event.target instanceof HTMLElement ? event.target.closest('button[data-view]') : null;
        if (!(target instanceof HTMLButtonElement)) return;
        const view = String(target.dataset.view || '').trim();
        if (!view) return;
        this.brainRecordsView = /** @type {'now'|'review'|'history'|'library'} */ (view);
        this.renderBrainRecordsViews();
        this.renderBrainRecordsList();
        if (this.isBrainRecordsStale()) {
          void this.refreshBrainRecords();
        }
      });
    }

    if (this.els.brainRecordsApplyCleanupButton) {
      this.els.brainRecordsApplyCleanupButton.addEventListener('click', () => {
        void this.applyApprovedCleanup();
      });
    }

    [
      this.els.brainLibraryLayerFilter,
      this.els.brainLibraryStatusFilter,
      this.els.brainLibraryRelevanceFilter,
      this.els.brainLibrarySourceFilter,
      this.els.brainLibraryShowArchived,
      this.els.brainLibraryShowRawJson,
    ].forEach((control) => {
      if (!control) return;
      control.addEventListener('change', () => {
        this.syncBrainLibraryFiltersFromUi();
        this.renderBrainRecordsList();
      });
    });

    if (this.els.brainLibrarySearch) {
      this.els.brainLibrarySearch.addEventListener('input', () => {
        this.syncBrainLibraryFiltersFromUi();
        this.renderBrainRecordsList();
      });
    }

    if (this.els.brainRecordEditorSaveButton) {
      this.els.brainRecordEditorSaveButton.addEventListener('click', () => {
        void this.saveBrainRecordEdits();
      });
    }

    if (this.els.brainRecordEditorCancelButton) {
      this.els.brainRecordEditorCancelButton.addEventListener('click', () => {
        this.closeBrainRecordEditor();
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
    await this.refreshBrainRecords();
    this.renderOperatorModeUi();
    this.renderBrainRecordsViews();
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
        const responseMetadata = data && typeof data === 'object' && data.metadata && typeof data.metadata === 'object'
          ? data.metadata
          : {};
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
        const fallbackAssistantMeta =
          responseMetadata.last_assistant_payload && typeof responseMetadata.last_assistant_payload === 'object'
            ? responseMetadata.last_assistant_payload
            : {};
        const mergedAssistantMeta = {
          ...fallbackAssistantMeta,
          ...assistantMeta,
        };
        const assistantArtifacts = this.collectCodeArtifacts(assistantMessage);
        if (assistantArtifacts.length) {
          mergedAssistantMeta.code_artifacts = assistantArtifacts;
        }
        this.debugArtifactReceipt(assistantMessage, mergedAssistantMeta);
        const assistantText = this.resolveAssistantVisibleText(mergedAssistantMeta, assistantContent);
        const reasoningText = this.extractReasoning(assistantContent);

        const assistantArticle = this.appendMessageCard(
          'assistant',
          assistantText || 'No assistant content returned.',
          reasoningText,
          mergedAssistantMeta,
          this.inferAssistantTimestamp(mergedAssistantMeta),
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

  async sendQuickPrompt(text) {
    const value = String(text || '').trim();
    if (!value) return;
    this.els.promptInput.value = value;
    await this.sendMessage();
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

    const hasCodeArtifacts = role === 'assistant' && this.collectCodeArtifacts(messageMetadata).length > 0;
    const patchProposal = role === 'assistant' ? this.collectArtifactPatchProposal(messageMetadata) : null;

    if (role === 'assistant') {
      copyPayload.receiptSummary = this.appendReceiptChips(article, messageMetadata);
      this.appendCodeArtifacts(article, messageMetadata);
      this.appendArtifactPatchProposal(article, patchProposal);
      this.appendWhyThisAnswerDrawer(article, messageMetadata);
      if (messageMetadata && typeof messageMetadata === 'object') {
        this.latestAssistantMeta = messageMetadata;
        this.updateBrainRecordsCalmSummary();
      }
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
    if (hasCodeArtifacts || patchProposal) {
      if (typeof article.scrollIntoView === 'function') {
        article.scrollIntoView({ block: 'start', inline: 'nearest' });
      }
    } else {
      this.els.chatTimeline.scrollTop = this.els.chatTimeline.scrollHeight;
    }
    this.visibleConversation.push(copyPayload);

    return article;
  }

  appendCodeArtifacts(article, messageMetadata) {
    const artifacts = this.collectCodeArtifacts(messageMetadata);

    if (!artifacts.length) return;

    const artifactTray = document.createElement('div');
    artifactTray.className = 'code-artifact-tray';

    artifacts.forEach((artifact, index) => {
      if (!artifact || typeof artifact !== 'object') return;
      const filename = typeof artifact.filename === 'string' ? artifact.filename.trim() : '';
      const content = typeof artifact.content === 'string' ? artifact.content : '';
      if (!filename || !content) return;
      artifactTray.append(
        this.createCodeArtifactCard({
          ...artifact,
          filename,
          content,
          artifactIndex: index,
        }),
      );
    });

    if (artifactTray.childElementCount > 0) {
      article.append(artifactTray);
    }
  }

  createCodeArtifactCard(artifact) {
    const filename = String(artifact.filename || '').trim();
    const content = String(artifact.content || '');
    const language = this.normalizeArtifactLanguage(artifact.language || this.inferLanguageFromFilename(filename));
    const previewable = this.isArtifactPreviewable(artifact, filename, language);
    const applied = artifact.applied === true;
    const artifactId = `artifact-${++this.messageCounter}`;

    const card = document.createElement('section');
    card.className = 'code-artifact-card';
    card.dataset.artifactId = artifactId;
    card.dataset.filename = filename;
    card.dataset.language = language;

    const header = document.createElement('div');
    header.className = 'code-artifact-header';

    const chevron = document.createElement('button');
    chevron.type = 'button';
    chevron.className = 'code-artifact-chevron';
    chevron.setAttribute('aria-expanded', 'true');
    chevron.setAttribute('aria-label', 'Collapse code artifact');
    chevron.textContent = '▾';

    const identity = document.createElement('div');
    identity.className = 'code-artifact-identity';

    const fileNameEl = document.createElement('div');
    fileNameEl.className = 'code-artifact-filename';
    fileNameEl.textContent = filename;

    const badgeRow = document.createElement('div');
    badgeRow.className = 'code-artifact-badges';

    const languageBadge = document.createElement('span');
    languageBadge.className = 'code-artifact-badge code-artifact-badge-language';
    languageBadge.textContent = this.languageLabel(language);

    const statusBadge = document.createElement('span');
    statusBadge.className = 'code-artifact-badge code-artifact-badge-status';
    statusBadge.textContent = applied ? 'Applied' : 'Draft only';

    badgeRow.append(languageBadge, statusBadge);
    identity.append(fileNameEl, badgeRow);

    const toolbar = document.createElement('div');
    toolbar.className = 'code-artifact-toolbar';

    const copyButton = document.createElement('button');
    copyButton.type = 'button';
    copyButton.className = 'code-artifact-button';
    copyButton.textContent = 'Copy';
    copyButton.addEventListener('click', async () => {
      await this.copyCodeArtifact(card, artifact, copyButton);
    });

    const downloadButton = document.createElement('button');
    downloadButton.type = 'button';
    downloadButton.className = 'code-artifact-button';
    downloadButton.textContent = 'Download';
    downloadButton.addEventListener('click', () => {
      this.downloadCodeArtifact(artifact);
    });

    const previewButton = document.createElement('button');
    previewButton.type = 'button';
    previewButton.className = 'code-artifact-button';
    previewButton.textContent = 'Preview';
    previewButton.disabled = !previewable;
    previewButton.title = previewable ? 'Preview artifact locally.' : 'Preview is available for HTML artifacts.';
    previewButton.addEventListener('click', () => {
      this.toggleArtifactPreview(card, artifact, previewButton);
    });

    toolbar.append(copyButton, downloadButton, previewButton);

    header.append(chevron, identity, toolbar);

    const tabs = document.createElement('div');
    tabs.className = 'code-artifact-tabs';

    const codeTab = document.createElement('button');
    codeTab.type = 'button';
    codeTab.className = 'code-artifact-tab is-active';
    codeTab.setAttribute('aria-selected', 'true');
    codeTab.textContent = 'Code';

    const previewTab = document.createElement('button');
    previewTab.type = 'button';
    previewTab.className = 'code-artifact-tab';
    previewTab.setAttribute('aria-selected', 'false');
    previewTab.textContent = 'Preview';
    previewTab.disabled = !previewable;
    previewTab.title = previewable ? 'Preview artifact locally.' : 'Preview is available for HTML artifacts.';

    tabs.append(codeTab, previewTab);

    const body = document.createElement('div');
    body.className = 'code-artifact-body';

    const codePane = document.createElement('div');
    codePane.className = 'code-artifact-pane code-artifact-code-panel code-artifact-pane-code';
    codePane.style.minHeight = '480px';

    const codeViewport = document.createElement('div');
    codeViewport.className = 'code-artifact-codeview';
    codeViewport.append(this.renderArtifactCodeRows(content, language));
    codePane.append(codeViewport);

    const previewPane = document.createElement('div');
    previewPane.className = 'code-artifact-pane code-artifact-preview-panel code-artifact-pane-preview';
    previewPane.style.minHeight = '480px';
    previewPane.hidden = true;

    if (previewable) {
      if (language === 'html') {
        const iframe = document.createElement('iframe');
        iframe.className = 'code-artifact-preview-frame';
        iframe.setAttribute('sandbox', 'allow-scripts');
        iframe.setAttribute('title', `${filename} preview`);
        iframe.srcdoc = content;
        previewPane.append(iframe);
      } else {
        const previewText = document.createElement('pre');
        previewText.className = 'code-artifact-preview-text';
        previewText.textContent = content;
        previewPane.append(previewText);
      }
    } else {
      const previewNote = document.createElement('p');
      previewNote.className = 'code-artifact-preview-note';
      previewNote.textContent = 'Preview is available for HTML artifacts.';
      previewPane.append(previewNote);
    }

    const footer = document.createElement('div');
    footer.className = 'code-artifact-footer';
    footer.innerHTML = `
      <p class="code-artifact-footer-copy">This code has not been applied to the repo.</p>
      <p class="code-artifact-footer-next">
        Next step: Copy to VS Code or generate patch.
        <button type="button" class="code-artifact-footer-link" title="Patch generation is not enabled yet.">generate patch</button>
      </p>
    `;
    const generatePatchButton = footer.querySelector('.code-artifact-footer-link');
    if (generatePatchButton) {
      generatePatchButton.addEventListener('click', () => {
        void this.sendQuickPrompt('generate patch');
      });
    }

    const collapseBody = () => {
      const collapsed = card.classList.toggle('is-collapsed');
      chevron.textContent = collapsed ? '▸' : '▾';
      chevron.setAttribute('aria-expanded', String(!collapsed));
      chevron.setAttribute('aria-label', collapsed ? 'Expand code artifact' : 'Collapse code artifact');
      body.hidden = collapsed;
      tabs.hidden = collapsed;
      footer.hidden = collapsed;
    };

    chevron.addEventListener('click', collapseBody);
    codeTab.addEventListener('click', () => this.switchArtifactTab(card, 'code'));
    previewTab.addEventListener('click', () => this.switchArtifactTab(card, 'preview'));

    body.append(codePane, previewPane);
    card.append(header, tabs, body, footer);

    if (artifact.applied === true) {
      statusBadge.textContent = 'Applied';
    }

    return card;
  }

  renderArtifactCodeRows(content, language) {
    const fragment = document.createDocumentFragment();
    const source = String(content || '');
    const lines = source.endsWith('\n') ? source.slice(0, -1).split('\n') : source.split('\n');
    const highlightState = this.createArtifactHighlightState(language);

    lines.forEach((line, index) => {
      const row = document.createElement('div');
      row.className = `code-artifact-line ${index % 2 === 0 ? 'is-odd' : 'is-even'}`;

      const lineNumber = document.createElement('span');
      lineNumber.className = 'code-artifact-line-number';
      lineNumber.textContent = String(index + 1);

      const lineCode = document.createElement('span');
      lineCode.className = 'code-artifact-line-code';
      this.appendArtifactHighlightedLine(lineCode, line, language, highlightState);

      row.append(lineNumber, lineCode);
      fragment.append(row);
    });

    return fragment;
  }

  createArtifactHighlightState(language) {
    const normalized = this.normalizeArtifactLanguage(language);
    return {
      language: normalized,
      inHtmlComment: false,
      inCssComment: false,
      inStyleBlock: false,
      inScriptBlock: false,
    };
  }

  appendArtifactHighlightedLine(container, line, language, state) {
    const normalized = this.normalizeArtifactLanguage(language || state?.language || 'text');
    if (normalized === 'html') {
      this.appendHtmlArtifactLine(container, line, state);
      return;
    }
    if (normalized === 'css') {
      this.appendCssArtifactLine(container, line, state);
      return;
    }
    if (normalized === 'python') {
      this.appendPythonArtifactLine(container, line);
      return;
    }
    this.appendPlainArtifactLine(container, line);
  }

  appendPlainArtifactLine(container, line) {
    const text = document.createElement('span');
    text.className = 'code-token-plain';
    text.textContent = line;
    container.append(text);
  }

  appendHtmlArtifactLine(container, line, state) {
    if (state.inStyleBlock) {
      const closingIndex = line.toLowerCase().indexOf('</style');
      if (closingIndex === -1) {
        this.appendCssArtifactLine(container, line, state);
        return;
      }
      this.appendCssArtifactLine(container, line.slice(0, closingIndex), state);
      state.inStyleBlock = false;
      this.appendHtmlArtifactLine(container, line.slice(closingIndex), state);
      return;
    }

    const commentOpen = '<!--';
    const commentClose = '-->';
    let index = 0;

    while (index < line.length) {
      if (state.inHtmlComment) {
        const commentEnd = line.indexOf(commentClose, index);
        if (commentEnd === -1) {
          this.appendArtifactToken(container, 'code-token-html-comment', line.slice(index));
          return;
        }
        this.appendArtifactToken(container, 'code-token-html-comment', line.slice(index, commentEnd + commentClose.length));
        state.inHtmlComment = false;
        index = commentEnd + commentClose.length;
        continue;
      }

      const commentStart = line.indexOf(commentOpen, index);
      const tagStart = line.indexOf('<', index);

      if (commentStart !== -1 && (tagStart === -1 || commentStart <= tagStart)) {
        if (commentStart > index) {
          this.appendArtifactToken(container, 'code-token-html-text', line.slice(index, commentStart));
        }
        const commentEnd = line.indexOf(commentClose, commentStart + commentOpen.length);
        if (commentEnd === -1) {
          this.appendArtifactToken(container, 'code-token-html-comment', line.slice(commentStart));
          state.inHtmlComment = true;
          return;
        }
        this.appendArtifactToken(container, 'code-token-html-comment', line.slice(commentStart, commentEnd + commentClose.length));
        index = commentEnd + commentClose.length;
        continue;
      }

      if (tagStart === -1) {
        this.appendArtifactToken(container, 'code-token-html-text', line.slice(index));
        return;
      }

      if (tagStart > index) {
        this.appendArtifactToken(container, 'code-token-html-text', line.slice(index, tagStart));
      }

      const tagEnd = line.indexOf('>', tagStart + 1);
      const rawTag = tagEnd === -1 ? line.slice(tagStart) : line.slice(tagStart, tagEnd + 1);
      this.appendHtmlTagTokens(container, rawTag, state);
      index = tagEnd === -1 ? line.length : tagEnd + 1;
    }
  }

  appendHtmlTagTokens(container, rawTag, state) {
    if (!rawTag) return;

    const isClosingTag = rawTag.startsWith('</');
    const isSelfClosing = /\/>\s*$/.test(rawTag);
    const tagMatch = rawTag.match(/^<\/?\s*([A-Za-z][\w:-]*)/);
    let index = 0;

    if (isClosingTag) {
      this.appendArtifactToken(container, 'code-token-html-bracket', '</');
      index = 2;
    } else {
      this.appendArtifactToken(container, 'code-token-html-bracket', '<');
      index = 1;
    }

    if (tagMatch) {
      const tagName = tagMatch[1];
      this.appendArtifactToken(container, 'code-token-html-tag', tagName);
      index = rawTag.indexOf(tagName, index) + tagName.length;
      if (tagName.toLowerCase() === 'style') {
        state.inStyleBlock = !isClosingTag;
      }
      if (tagName.toLowerCase() === 'script') {
        state.inScriptBlock = !isClosingTag;
      }
    }

    while (index < rawTag.length) {
      const ch = rawTag[index];
      if (ch === '>' ) {
        this.appendArtifactToken(container, 'code-token-html-bracket', '>');
        return;
      }
      if (ch === '/' && rawTag[index + 1] === '>') {
        this.appendArtifactToken(container, 'code-token-html-bracket', '/>');
        return;
      }
      if (/\s/.test(ch)) {
        this.appendArtifactToken(container, 'code-token-html-text', ch);
        index += 1;
        continue;
      }
      if (ch === '=' ) {
        this.appendArtifactToken(container, 'code-token-html-bracket', '=');
        index += 1;
        continue;
      }
      if (ch === '"' || ch === '\'') {
        const quote = ch;
        let end = index + 1;
        while (end < rawTag.length && rawTag[end] !== quote) end += 1;
        const text = rawTag.slice(index, end < rawTag.length ? end + 1 : rawTag.length);
        this.appendArtifactToken(container, 'code-token-html-string', text);
        index = end < rawTag.length ? end + 1 : rawTag.length;
        continue;
      }

      const attrMatch = rawTag.slice(index).match(/^[A-Za-z_:][\w:.-]*/);
      if (attrMatch) {
        this.appendArtifactToken(container, 'code-token-html-attr', attrMatch[0]);
        index += attrMatch[0].length;
        continue;
      }

      this.appendArtifactToken(container, 'code-token-html-text', ch);
      index += 1;
    }

    if (isSelfClosing) {
      state.inStyleBlock = false;
      state.inScriptBlock = false;
    }
  }

  appendCssArtifactLine(container, line, state) {
    const commentOpen = '/*';
    const commentClose = '*/';
    let index = 0;

    while (index < line.length) {
      if (state.inCssComment) {
        const commentEnd = line.indexOf(commentClose, index);
        if (commentEnd === -1) {
          this.appendArtifactToken(container, 'code-token-css-comment', line.slice(index));
          return;
        }
        this.appendArtifactToken(container, 'code-token-css-comment', line.slice(index, commentEnd + commentClose.length));
        state.inCssComment = false;
        index = commentEnd + commentClose.length;
        continue;
      }

      const commentStart = line.indexOf(commentOpen, index);
      if (commentStart !== -1 && commentStart >= index) {
        if (commentStart > index) {
          this.appendCssValueTokens(container, line.slice(index, commentStart));
        }
        const commentEnd = line.indexOf(commentClose, commentStart + commentOpen.length);
        if (commentEnd === -1) {
          this.appendArtifactToken(container, 'code-token-css-comment', line.slice(commentStart));
          state.inCssComment = true;
          return;
        }
        this.appendArtifactToken(container, 'code-token-css-comment', line.slice(commentStart, commentEnd + commentClose.length));
        index = commentEnd + commentClose.length;
        continue;
      }

      this.appendCssTokenizedLine(container, line.slice(index));
      return;
    }
  }

  appendCssTokenizedLine(container, text) {
    if (!text) return;
    const pattern = /(\/\*[\s\S]*?\*\/)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw|deg|ms|s)?\b)|(#[0-9a-fA-F]{3,8}\b)|(\b[A-Za-z_-][\w-]*\b)(?=\s*:)|([{}();:,])/g;
    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(text)) !== null) {
      if (match.index > lastIndex) {
        this.appendArtifactToken(container, 'code-token-css-text', text.slice(lastIndex, match.index));
      }
      const token = match[0];
      if (match[1]) {
        this.appendArtifactToken(container, 'code-token-css-comment', token);
      } else if (match[2]) {
        this.appendArtifactToken(container, 'code-token-css-string', token);
      } else if (match[3] || match[4]) {
        this.appendArtifactToken(container, 'code-token-css-number', token);
      } else if (match[5]) {
        this.appendArtifactToken(container, 'code-token-css-property', token);
      } else {
        this.appendArtifactToken(container, 'code-token-css-bracket', token);
      }
      lastIndex = match.index + token.length;
    }

    if (lastIndex < text.length) {
      this.appendArtifactToken(container, 'code-token-css-text', text.slice(lastIndex));
    }
  }

  appendPythonArtifactLine(container, line) {
    const keywordPattern = /\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b/g;
    const tokenPattern = /(#[^\n]*|'''[\s\S]*?'''|"""[\s\S]*?"""|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|\b\d+(?:\.\d+)?\b|\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b)/g;
    let lastIndex = 0;
    let match;

    while ((match = tokenPattern.exec(line)) !== null) {
      if (match.index > lastIndex) {
        this.appendArtifactToken(container, 'code-token-plain', line.slice(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith('#')) {
        this.appendArtifactToken(container, 'code-token-python-comment', token);
      } else if (token.startsWith('"') || token.startsWith("'") || token.startsWith('"""') || token.startsWith("'''")) {
        this.appendArtifactToken(container, 'code-token-python-string', token);
      } else if (/^\d/.test(token)) {
        this.appendArtifactToken(container, 'code-token-python-number', token);
      } else if (keywordPattern.test(token)) {
        keywordPattern.lastIndex = 0;
        this.appendArtifactToken(container, 'code-token-python-keyword', token);
      } else {
        this.appendArtifactToken(container, 'code-token-plain', token);
      }
      lastIndex = match.index + token.length;
    }

    if (lastIndex < line.length) {
      this.appendArtifactToken(container, 'code-token-plain', line.slice(lastIndex));
    }
  }

  appendArtifactToken(container, className, text) {
    if (!text) return;
    const span = document.createElement('span');
    span.className = className;
    span.textContent = text;
    container.append(span);
  }

  switchArtifactTab(card, tabName) {
    if (!card) return;
    const codeTab = card.querySelector('.code-artifact-tab:nth-of-type(1)');
    const previewTab = card.querySelector('.code-artifact-tab:nth-of-type(2)');
    const codePane = card.querySelector('.code-artifact-code-panel');
    const previewPane = card.querySelector('.code-artifact-preview-panel');
    if (!codeTab || !previewTab || !codePane || !previewPane) return;

    const showPreview = tabName === 'preview' && !previewTab.disabled;
    codeTab.classList.toggle('is-active', !showPreview);
    previewTab.classList.toggle('is-active', showPreview);
    codeTab.setAttribute('aria-selected', String(!showPreview));
    previewTab.setAttribute('aria-selected', String(showPreview));
    codePane.hidden = showPreview;
    previewPane.hidden = !showPreview;
  }

  normalizeArtifactLanguage(language) {
    const normalized = String(language || '').trim().toLowerCase();
    if (!normalized) return 'text';
    if (normalized === 'py') return 'python';
    if (normalized === 'md') return 'markdown';
    return normalized;
  }

  inferLanguageFromFilename(filename) {
    const lower = String(filename || '').toLowerCase();
    if (lower.endsWith('.py')) return 'python';
    if (lower.endsWith('.js')) return 'javascript';
    if (lower.endsWith('.ts')) return 'typescript';
    if (lower.endsWith('.css')) return 'css';
    if (lower.endsWith('.html') || lower.endsWith('.htm')) return 'html';
    if (lower.endsWith('.md')) return 'markdown';
    return 'text';
  }

  languageLabel(language) {
    const normalized = this.normalizeArtifactLanguage(language);
    if (normalized === 'javascript') return 'JavaScript';
    if (normalized === 'python') return 'Python';
    if (normalized === 'typescript') return 'TypeScript';
    if (normalized === 'markdown') return 'Markdown';
    if (normalized === 'html') return 'HTML';
    if (normalized === 'css') return 'CSS';
    return normalized.toUpperCase();
  }

  isArtifactPreviewable(artifact, filename, language) {
    if (artifact && artifact.previewable === true) return true;
    const normalized = this.normalizeArtifactLanguage(language || this.inferLanguageFromFilename(filename));
    return normalized === 'html';
  }

  async copyCodeArtifact(card, artifact, button) {
    const content = String(artifact?.content || '');
    if (!content) return;
    await this.copyToClipboard(content);
    if (!button) return;

    const original = button.textContent || 'Copy';
    button.textContent = 'Copied';
    button.classList.add('is-copied');
    window.clearTimeout(this.artifactCopyState.get(card)?.timer || 0);
    const timer = window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove('is-copied');
    }, 1200);
    this.artifactCopyState.set(card, { copied: true, timer });
  }

  downloadCodeArtifact(artifact) {
    const filename = this.sanitizeArtifactDownloadName(artifact?.filename || 'artifact.txt');
    const content = String(artifact?.content || '');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  sanitizeArtifactDownloadName(filename) {
    const name = String(filename || 'artifact.txt').trim().split(/[\\/]/).pop() || 'artifact.txt';
    return name;
  }

  toggleArtifactPreview(card, artifact, button) {
    if (!card) return;
    const previewPane = card.querySelector('.code-artifact-pane-preview');
    const codePane = card.querySelector('.code-artifact-pane-code');
    if (!previewPane || !codePane || button?.disabled) return;
    this.switchArtifactTab(card, 'preview');
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

  appendWhyThisAnswerDrawer(article, messageMetadata) {
    const meta = messageMetadata && typeof messageMetadata === 'object' ? messageMetadata : {};
    const policy = meta.policy_provenance && typeof meta.policy_provenance === 'object' ? meta.policy_provenance : {};
    const contextReceipt = meta.context_receipt && typeof meta.context_receipt === 'object' ? meta.context_receipt : {};
    const contextEntries = Array.isArray(contextReceipt.context_receipts) ? contextReceipt.context_receipts : [];

    const sourceRecordIds = Array.isArray(meta.source_record_ids)
      ? meta.source_record_ids.filter((item) => typeof item === 'string' && item.trim())
      : Array.isArray(contextReceipt.record_ids)
        ? contextReceipt.record_ids.filter((item) => typeof item === 'string' && item.trim())
        : [];

    const selectedLayers = contextEntries
      .map((entry) => this.contextLayerChipLabel(entry?.layer || entry?.receipt_label || ''))
      .filter((label) => label && label !== 'Context');

    const modelUseReceipt = meta.model_use_receipt && typeof meta.model_use_receipt === 'object'
      ? meta.model_use_receipt
      : {};

    const artifactGeneration = policy.artifact_generation || '-';
    const artifactIsFallback = artifactGeneration === 'deterministic_prompt_template_fallback';
    const resolvedModelUsed = policy.model_used
      || modelUseReceipt.model_tag
      || meta.model_used
      || 'policy_only';
    const resolvedFallbackReason = policy.fallback_reason
      || meta.fallback_reason
      || policy.brain_answer_source
      || '-';
    const revisionMode = policy.revision_mode || meta.revision_mode || '-';
    const revisionNumber = policy.revision_number || meta.revision_number || '-';
    const sourceArtifact = policy.source_artifact || policy.source_artifact_key || meta.source_artifact || '-';
    const patchProposal = this.collectArtifactPatchProposal(meta);
    const patchValidation = patchProposal?.validation?.status || policy.validation || '-';
    const patchTargetPath = patchProposal?.target_path || policy.target_path || '-';
    const primaryArtifact = Array.isArray(meta.code_artifacts) && meta.code_artifacts.length
      ? meta.code_artifacts[0]
      : (meta.code_artifact && typeof meta.code_artifact === 'object' ? meta.code_artifact : null);
    const promptFidelity = policy.prompt_fidelity && typeof policy.prompt_fidelity === 'object'
      ? policy.prompt_fidelity
      : (primaryArtifact?.prompt_fidelity && typeof primaryArtifact.prompt_fidelity === 'object'
          ? primaryArtifact.prompt_fidelity
          : {});
    const promptFidelityStatus = promptFidelity.status || '-';
    const promptFidelityBusinessName = promptFidelity.requested_business_name || '-';
    const promptFidelityBusinessType = promptFidelity.requested_business_type || '-';
    const promptFidelityColors = Array.isArray(promptFidelity.requested_colors) && promptFidelity.requested_colors.length
      ? promptFidelity.requested_colors.join(', ')
      : '-';
    const promptFidelityRepairAttempted = this.boolText(promptFidelity.repair_attempted);

    const fields = [
      ['intent_class', policy.intent_class || meta.intent_class],
      ['speech_act', meta.speech_act || '-'],
      ['response_mode', policy.response_mode || meta.response_mode || '-'],
      ['artifact_generation', artifactGeneration],
      ['prompt_fidelity_status', promptFidelityStatus],
      ['prompt_fidelity_business', promptFidelityBusinessName],
      ['prompt_fidelity_type', promptFidelityBusinessType],
      ['prompt_fidelity_colors', promptFidelityColors],
      ['prompt_fidelity_repair_attempted', promptFidelityRepairAttempted],
      ['revision_mode', revisionMode],
      ['revision_number', revisionNumber],
      ['source_artifact', sourceArtifact],
      ['artifact_patch', policy.artifact_patch || '-'],
      ['patch_target_path', patchTargetPath],
      ['patch_operation', patchProposal?.operation || policy.operation || '-'],
      ['patch_validation', patchValidation],
      ['patch_applied', this.boolText(patchProposal?.applied ?? policy.applied)],
      ['model_used', resolvedModelUsed],
      ['artifact_validation', policy.artifact_validation || '-'],
      ['fallback_used', this.boolText(meta.fallback_used ?? artifactIsFallback)],
      ['fallback_reason', resolvedFallbackReason],
      ['learned_record_id', meta.learned_record_id || '-'],
      ['learning_layer', meta.learning_layer || '-'],
      ['learning_status', meta.learning_status || '-'],
      ['requires_confirmation', this.boolText(meta.requires_confirmation)],
      ['protected_boundary', this.boolText(meta.protected_boundary)],
      ['selected_layers', selectedLayers.length ? selectedLayers.join(', ') : '-'],
      ['source_record_ids', sourceRecordIds.length ? sourceRecordIds.join(', ') : '-'],
      ['active_focus_id', policy.active_focus_id || meta.active_focus_id || '-'],
      ['focus_applied', this.boolText(policy.focus_applied ?? meta.focus_applied)],
      ['context_includes_focus', this.boolText(meta.context_includes_focus ?? selectedLayers.includes('Focus'))],
    ];

    const details = document.createElement('details');
    details.className = 'why-answer-drawer';

    const summary = document.createElement('summary');
    summary.textContent = 'Why this answer?';

    const body = document.createElement('div');
    body.className = 'receipt-detail-grid';
    fields.forEach(([label, value]) => {
      this.appendReceiptField(body, String(label), value);
    });

    details.append(summary, body);
    article.append(details);
  }

  boolText(value) {
    if (value === true) return 'true';
    if (value === false) return 'false';
    return '-';
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

  renderBrainRecordsViews() {
    const tabMount = this.els.brainRecordsViews;
    if (!tabMount) return;
    const counts = this.brainRecordCounts;
    const viewLabels = {
      now: `NOW (${counts.current})`,
      review: `REVIEW (${counts.review})`,
      history: `HISTORY (${counts.history})`,
      library: `LIBRARY (${counts.library})`,
    };
    const buttons = tabMount.querySelectorAll('button[data-view]');
    buttons.forEach((button) => {
      const viewKey = String(button.dataset.view || '').trim();
      if (viewKey && Object.prototype.hasOwnProperty.call(viewLabels, viewKey)) {
        button.textContent = viewLabels[viewKey];
      }
      const isActive = button.dataset.view === this.brainRecordsView;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    if (this.els.brainLibraryControls) {
      this.els.brainLibraryControls.classList.toggle('hidden', this.brainRecordsView !== 'library');
    }

    if (this.els.brainReviewToolbar) {
      const approvedCount = Object.keys(this.approvedCleanupRecommendations).length;
      const showToolbar = this.brainRecordsView === 'review' && approvedCount > 0;
      this.els.brainReviewToolbar.classList.toggle('hidden', !showToolbar);
    }

    if (this.els.brainRecordsApplyCleanupButton) {
      const approvedCount = Object.keys(this.approvedCleanupRecommendations).length;
      this.els.brainRecordsApplyCleanupButton.textContent = `Apply approved cleanup (${approvedCount})`;
    }

    this.syncBrainLibraryFiltersFromUi();
  }

  syncBrainLibraryFiltersFromUi() {
    this.brainRecordsFilters.layer = String(this.els.brainLibraryLayerFilter?.value || 'all');
    this.brainRecordsFilters.status = String(this.els.brainLibraryStatusFilter?.value || 'active');
    this.brainRecordsFilters.relevance = String(this.els.brainLibraryRelevanceFilter?.value || 'all');
    this.brainRecordsFilters.source = String(this.els.brainLibrarySourceFilter?.value || 'all');
    this.brainRecordsFilters.search = String(this.els.brainLibrarySearch?.value || '').trim().toLowerCase();
    this.brainRecordsFilters.showArchived = Boolean(this.els.brainLibraryShowArchived?.checked);
    this.brainRecordsFilters.showRawJson = Boolean(this.els.brainLibraryShowRawJson?.checked);
  }

  pendingLearnedCount() {
    return this.brainRecordCounts.review;
  }

  isPendingLearnedRecord(record) {
    const tags = new Set((Array.isArray(record?.tags) ? record.tags : []).map((tag) => String(tag).toLowerCase()));
    const status = String(record?.status_label || record?.status || '').toLowerCase();
    return status === 'pending' && (tags.has('learned-rule') || tags.has('otis-learning'));
  }

  normalizeRecordSource(record) {
    return String(record?.source || '').toLowerCase() === 'runtime_override' ? 'runtime' : 'seed';
  }

  recordStatusLabel(record) {
    const status = String(record?.status_label || record?.status || '').toLowerCase();
    const tags = new Set((Array.isArray(record?.tags) ? record.tags : []).map((tag) => String(tag).toLowerCase()));
    if (status === 'active') return 'ACTIVE';
    if (status === 'pending' || status === 'pending_review') return 'PENDING';
    if (status === 'disabled' || (status === 'archived' && tags.has('deactivated'))) return 'DISABLED';
    if (status === 'archived') return 'ARCHIVED';
    return String(status || 'ARCHIVED').toUpperCase();
  }

  recordRelevanceLabel(record) {
    const relevance = String(record?.effective_relevance_state || record?.relevance_state || 'current').toLowerCase();
    if (relevance === 'needs_review') return 'NEEDS REVIEW';
    return relevance.replace('_', ' ').toUpperCase();
  }

  sourceStatusLabel(record) {
    return this.normalizeRecordSource(record) === 'runtime' ? 'RUNTIME OVERRIDE' : 'SEED';
  }

  sourceRuntime(record) {
    return this.normalizeRecordSource(record) === 'runtime';
  }

  primaryHygieneRecommendation(record) {
    const recs = Array.isArray(record?.hygiene_recommendations) ? record.hygiene_recommendations : [];
    if (!recs.length) return null;
    const split = recs.find((item) => String(item?.type || '') === 'split_record');
    if (split) return split;
    return recs[0];
  }

  isReviewCandidate(record) {
    const status = String(record?.status_label || record?.status || '').toLowerCase();
    const storedRelevance = String(record?.relevance_state || '').toLowerCase();
    const effectiveRelevance = String(record?.effective_relevance_state || storedRelevance || '').toLowerCase();
    const recs = Array.isArray(record?.hygiene_recommendations) ? record.hygiene_recommendations : [];
    const flags = new Set((Array.isArray(record?.hygiene_flags) ? record.hygiene_flags : []).map((item) => String(item).toLowerCase()));

    return (
      status === 'pending'
      || status === 'pending_review'
      || storedRelevance === 'needs_review'
      || effectiveRelevance === 'needs_review'
      || recs.length > 0
      || flags.has('old_phase_reference')
      || flags.has('completed_milestone')
      || flags.has('mixed_historical_and_current')
      || flags.has('mixed_historical_and_operational')
    );
  }

  isHistoryCandidate(record) {
    const storedRelevance = String(record?.relevance_state || '').toLowerCase();
    const effectiveRelevance = String(record?.effective_relevance_state || storedRelevance || '').toLowerCase();
    return (
      storedRelevance === 'historical'
      || storedRelevance === 'superseded'
      || storedRelevance === 'expired'
      || effectiveRelevance === 'historical'
      || effectiveRelevance === 'superseded'
      || effectiveRelevance === 'expired'
    );
  }

  filteredLibraryRecords() {
    const f = this.brainRecordsFilters;
    return this.brainRecords.filter((record) => {
      const layer = String(record?.layer || '');
      const source = this.normalizeRecordSource(record);
      const statusLabel = this.recordStatusLabel(record).toLowerCase();
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
      const rawStatus = String(record?.status || '').toLowerCase();
      const searchBlob = [
        record?.record_id,
        record?.title,
        record?.summary,
        record?.body,
        record?.relevance_state,
        record?.effective_relevance_state,
        Array.isArray(record?.tags) ? record.tags.join(' ') : '',
      ]
        .map((value) => String(value || '').toLowerCase())
        .join(' ');

      if (f.layer !== 'all' && layer !== f.layer) return false;
      if (f.source !== 'all' && source !== f.source) return false;

      if (!f.showArchived && (statusLabel === 'archived' || statusLabel === 'disabled')) return false;

      if (f.status !== 'all') {
        if (f.status === 'active' && statusLabel !== 'active') return false;
        if (f.status === 'pending' && statusLabel !== 'pending') return false;
        if (f.status === 'disabled' && statusLabel !== 'disabled') return false;
        if (f.status === 'archived' && statusLabel !== 'archived') return false;
      }

      if (f.relevance !== 'all' && relevance !== f.relevance) return false;

      if (rawStatus === 'archived' && f.status === 'active') return false;

      if (f.search && !searchBlob.includes(f.search)) return false;
      return true;
    });
  }

  nowViewRecords() {
    const active = this.brainRecords.filter((record) => {
      const status = this.recordStatusLabel(record) === 'ACTIVE';
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
      return status && relevance === 'current';
    });
    const byLayer = {
      system_prompt: [],
      active_focus: [],
      memory: [],
      knowledge: [],
      verified_status: [],
    };

    active.forEach((record) => {
      const layer = String(record?.layer || '');
      if (layer in byLayer) byLayer[layer].push(record);
    });

    const nowRecords = [
      ...byLayer.system_prompt,
      ...byLayer.active_focus,
      ...byLayer.memory,
      ...byLayer.knowledge,
      ...byLayer.verified_status,
    ];

    const pushIfMissing = (record) => {
      const recordId = String(record?.record_id || '').trim();
      if (!recordId) return;
      const exists = nowRecords.some((item) => String(item?.record_id || '') === recordId);
      if (!exists) nowRecords.push(record);
    };

    const selectedIds = Array.isArray(this.latestAssistantMeta?.source_record_ids)
      ? this.latestAssistantMeta.source_record_ids.filter((item) => typeof item === 'string' && item.trim())
      : [];
    selectedIds.forEach((recordId) => {
      const found = this.brainRecords.find((record) => String(record?.record_id || '') === String(recordId));
      if (found) pushIfMissing(found);
    });

    const activeContextIds = Array.isArray(this.activeContextSnapshot?.recordIds)
      ? this.activeContextSnapshot.recordIds.filter((item) => typeof item === 'string' && item.trim())
      : [];
    activeContextIds.forEach((recordId) => {
      const found = this.brainRecords.find((record) => String(record?.record_id || '') === String(recordId));
      if (found) pushIfMissing(found);
    });

    const focusId = String(
      this.latestAssistantMeta?.active_focus_id
      || this.latestAssistantMeta?.policy_provenance?.active_focus_id
      || this.activeContextSnapshot?.activeFocusId
      || '',
    ).trim();
    if (focusId) {
      const focusRecord = this.brainRecords.find((record) => String(record?.record_id || '') === focusId);
      if (focusRecord) {
        const isActive = this.recordStatusLabel(focusRecord) === 'ACTIVE';
        const relevance = String(focusRecord?.effective_relevance_state || focusRecord?.relevance_state || '').toLowerCase();
        const alreadyIncluded = nowRecords.some((record) => String(record?.record_id || '') === focusId);
        if (isActive && relevance === 'current' && !alreadyIncluded) {
          nowRecords.unshift(focusRecord);
        }
      } else {
        const focusSummary = String(
          this.activeContextSnapshot?.activeFocusSummary
          || this.latestAssistantMeta?.active_focus_summary
          || this.latestAssistantMeta?.policy_provenance?.current_focus?.summary
          || this.latestAssistantMeta?.active_focus_text
          || '',
        ).trim();
        const virtualFocus = {
          record_id: focusId,
          layer: 'active_focus',
          title: focusSummary || 'Active Focus',
          summary: focusSummary || 'Active focus from current context.',
          body: focusSummary || 'Active focus from current context.',
          status: 'active',
          status_label: 'active',
          relevance_state: 'current',
          effective_relevance_state: 'current',
          source: 'active_context',
          updated_at: '-',
          tags: ['active-context', 'virtual'],
          writable: false,
          raw_record: {
            record_id: focusId,
            layer: 'active_focus',
            summary: focusSummary || 'Active focus from current context.',
            source: 'active_context',
            virtual: true,
          },
          __virtual_now_focus: true,
        };
        nowRecords.unshift(virtualFocus);
      }
    }

    return nowRecords;
  }

  isBrainRecordsStale() {
    if (!this.brainRecordsLastRefreshAt) return true;
    return (Date.now() - this.brainRecordsLastRefreshAt) > this.brainRecordsStaleMs;
  }

  historyViewRecords() {
    return this.brainRecords.filter((record) => this.isHistoryCandidate(record));
  }

  computeBrainRecordCounts(reviewBackendCount = 0, historyBackendCount = 0) {
    const review = Number.isFinite(reviewBackendCount) ? reviewBackendCount : this.brainReviewRecords.length;
    const history = Number.isFinite(historyBackendCount) ? historyBackendCount : this.brainHistoryRecords.length;
    const current = this.nowViewRecords().length;
    this.brainRecordCounts = {
      current,
      review,
      history,
      library: this.brainRecords.length,
      reviewBackend: reviewBackendCount,
      historyBackend: historyBackendCount,
    };
  }

  buildReviewDiagnostics(frontendReviewCount) {
    const reasons = [];
    const backendReviewCount = Number(this.brainRecordCounts.reviewBackend || 0);
    if (backendReviewCount === 0) {
      reasons.push('no records returned by backend review_only');
    }
    if (backendReviewCount > 0 && this.brainReviewRecords.length === 0) {
      reasons.push('frontend binding dropped backend review_only records');
    }
    if (backendReviewCount > 0 && frontendReviewCount === 0) {
      reasons.push('frontend filter excluded computed candidate');
    }

    const hasHygieneSignals = this.brainRecords.some((record) => {
      const flags = Array.isArray(record?.hygiene_flags) ? record.hygiene_flags : [];
      const recs = Array.isArray(record?.hygiene_recommendations) ? record.hygiene_recommendations : [];
      const storedRelevance = String(record?.relevance_state || '').toLowerCase();
      const effectiveRelevance = String(record?.effective_relevance_state || storedRelevance || '').toLowerCase();
      return flags.length > 0 || recs.length > 0 || storedRelevance === 'needs_review' || effectiveRelevance === 'needs_review';
    });
    if (!hasHygieneSignals) {
      reasons.push('hygiene classifier found no flags');
    }
    return reasons;
  }

  updateBrainRecordsCalmSummary() {
    const activeFocus = this.brainRecords.find(
      (record) => String(record?.layer || '') === 'active_focus' && this.recordStatusLabel(record) === 'ACTIVE',
    );
    if (this.els.brainNowFocus) {
      if (activeFocus) {
        this.els.brainNowFocus.textContent = `${activeFocus.record_id} • ${activeFocus.title || activeFocus.summary || '-'}`;
      } else {
        const activeFocusId = String(this.activeContextSnapshot?.activeFocusId || '').trim();
        const activeFocusSummary = String(this.activeContextSnapshot?.activeFocusSummary || '').trim();
        this.els.brainNowFocus.textContent = activeFocusId
          ? `${activeFocusId} • ${activeFocusSummary || 'Active focus from current context.'}`
          : 'No active focus record.';
      }
    }

    const sourceRecordIds = Array.isArray(this.latestAssistantMeta?.source_record_ids)
      ? this.latestAssistantMeta.source_record_ids.filter((item) => typeof item === 'string' && item.trim())
      : [];
    if (this.els.brainNowSelectedRecords) {
      this.els.brainNowSelectedRecords.textContent = sourceRecordIds.length ? sourceRecordIds.join(', ') : '-';
    }

    const responseMode = String(this.latestAssistantMeta?.response_mode || this.latestAssistantMeta?.policy_provenance?.response_mode || '-');
    const focusApplied = this.boolText(this.latestAssistantMeta?.focus_applied ?? this.latestAssistantMeta?.policy_provenance?.focus_applied);
    const fallbackUsed = this.boolText(this.latestAssistantMeta?.fallback_used);
    const modelUsed = String(this.latestAssistantMeta?.model_use_receipt?.model_tag || this.latestAssistantMeta?.model_used || 'policy_only');

    if (this.els.brainNowAnswerMeta) {
      this.els.brainNowAnswerMeta.textContent = `response_mode=${responseMode} | focus_applied=${focusApplied} | fallback_used=${fallbackUsed} | model_used=${modelUsed}`;
    }

    if (this.els.brainNowCounts) {
      const counts = this.brainRecordCounts;
      this.els.brainNowCounts.textContent = `current=${counts.current} | review=${counts.review} | history=${counts.history} | library=${counts.library}`;
    }
  }

  async refreshBrainRecords() {
    if (!this.els.brainRecordsList) return;
    this.brainRecordBusy = true;
    if (this.els.brainRecordsStatus) {
      this.els.brainRecordsStatus.textContent = 'Loading records...';
    }

    try {
      this.syncBrainLibraryFiltersFromUi();
      const [payload, reviewPayload, historyPayload] = await Promise.all([
        this.fetchJson('/runtime/brain/records?include_archived=true', { method: 'GET' }),
        this.fetchJson('/runtime/brain/records?include_archived=true&review_only=true', { method: 'GET' }),
        this.fetchJson('/runtime/brain/records?include_archived=true&history_only=true', { method: 'GET' }),
      ]);
      let activeContextPayload = null;
      try {
        activeContextPayload = await this.fetchJson('/runtime/context/active', { method: 'GET' });
      } catch {
        activeContextPayload = null;
      }
      this.brainRecords = Array.isArray(payload?.records) ? payload.records : [];
      const reviewRecords = Array.isArray(reviewPayload?.records) ? reviewPayload.records : [];
      const historyRecords = Array.isArray(historyPayload?.records) ? historyPayload.records : [];
      const activeContextReceipts = Array.isArray(activeContextPayload?.receipt?.context_receipts)
        ? activeContextPayload.receipt.context_receipts
        : [];
      const activeContextRecordIds = Array.isArray(activeContextPayload?.receipt?.record_ids)
        ? activeContextPayload.receipt.record_ids
        : [];
      const activeFocusReceipt = activeContextReceipts.find((item) => String(item?.layer || '') === 'active_focus');
      this.activeContextSnapshot = {
        recordIds: activeContextRecordIds
          .filter((item) => typeof item === 'string' && item.trim())
          .map((item) => String(item)),
        activeFocusId: String(activeFocusReceipt?.record_id || '').trim(),
        activeFocusSummary: String(activeFocusReceipt?.summary || activeContextPayload?.compact_receipt || '').trim(),
        prompt: String(activeContextPayload?.prompt || '').trim(),
      };
      this.brainReviewRecords = reviewRecords;
      this.brainHistoryRecords = historyRecords;
      this.computeBrainRecordCounts(reviewRecords.length, historyRecords.length);
      this.brainRecordsLastRefreshAt = Date.now();
      this.updateBrainRecordsCalmSummary();
      this.renderBrainRecordsViews();
      this.renderBrainRecordsList();
      if (this.els.brainRecordsStatus) {
        const counts = this.brainRecordCounts;
        this.els.brainRecordsStatus.textContent = `current=${counts.current} review=${counts.review} history=${counts.history} library=${counts.library}`;
      }
    } catch (error) {
      this.brainRecords = [];
      this.brainReviewRecords = [];
      this.brainHistoryRecords = [];
      this.activeContextSnapshot = null;
      this.computeBrainRecordCounts(0, 0);
      this.renderBrainRecordsViews();
      this.renderBrainRecordsList();
      if (this.els.brainRecordsStatus) {
        this.els.brainRecordsStatus.textContent = `Records unavailable: ${this.humanizeError(error)}`;
      }
    } finally {
      this.brainRecordBusy = false;
    }
  }

  renderBrainRecordsList() {
    const mount = this.els.brainRecordsList;
    if (!mount) return;
    mount.innerHTML = '';

    this.updateBrainRecordsCalmSummary();

    let recordsToRender = [];
    if (this.brainRecordsView === 'review') {
      recordsToRender = this.brainReviewRecords;
    } else if (this.brainRecordsView === 'history') {
      recordsToRender = this.brainHistoryRecords;
    } else if (this.brainRecordsView === 'library') {
      recordsToRender = this.filteredLibraryRecords();
    } else {
      recordsToRender = this.nowViewRecords();
    }

    if (!recordsToRender.length) {
      const li = document.createElement('li');
      li.className = 'rounded border border-dashed border-xv7-line px-2 py-1.5 text-slate-500';
      li.textContent = this.brainRecordsView === 'review'
        ? 'No review candidates.'
        : this.brainRecordsView === 'history'
          ? 'No historical records.'
        : this.brainRecordsView === 'library'
          ? 'No records match current library filters.'
          : 'No active stack records.';

      if (this.brainRecordsView === 'review') {
        const reasons = this.buildReviewDiagnostics(0);
        if (reasons.length) {
          const details = document.createElement('div');
          details.className = 'mt-2 text-[11px] text-slate-400';
          details.textContent = `Diagnostic: ${reasons.join('; ')}`;
          li.append(details);
        }
      } else if (this.brainRecordsView === 'history') {
        const backendHistoryCount = Number(this.brainRecordCounts.historyBackend || 0);
        if (backendHistoryCount > 0) {
          const details = document.createElement('div');
          details.className = 'mt-2 text-[11px] text-slate-400';
          details.textContent = 'Diagnostic: backend history_only returned records but frontend rendered none.';
          li.append(details);
        }
      } else if (this.brainRecordsView === 'now') {
        const focusId = String(
          this.latestAssistantMeta?.active_focus_id
          || this.latestAssistantMeta?.policy_provenance?.active_focus_id
          || this.activeContextSnapshot?.activeFocusId
          || '',
        ).trim();
        if (focusId) {
          const details = document.createElement('div');
          details.className = 'mt-2 text-[11px] text-red-300';
          details.textContent = 'Diagnostic: Active focus exists but was not bound into NOW records.';
          li.append(details);
        }
      }
      mount.append(li);
      return;
    }

    recordsToRender.forEach((record) => {
      const li = document.createElement('li');
      li.className = 'brain-record-card';

      const title = document.createElement('div');
      title.className = 'brain-record-title';
      title.textContent = `${record.record_id} • ${record.title || '-'}`;

      const meta = document.createElement('div');
      meta.className = 'brain-record-meta';
      meta.textContent = `${this.recordStatusLabel(record)} | ${this.recordRelevanceLabel(record)} | ${this.sourceStatusLabel(record)} | layer=${record.layer || '-'} | updated=${record.updated_at || '-'}`;

      const summary = document.createElement('div');
      summary.className = 'brain-record-summary';
      summary.textContent = String(record.summary || record.body || '').slice(0, 180) || '-';

      let reasonNode = null;
      const hygieneReason = String(record?.hygiene_reason || '').trim();
      if (hygieneReason) {
        const reason = document.createElement('div');
        reason.className = 'brain-record-summary';
        reason.textContent = `Reason: ${hygieneReason}`;
        reasonNode = reason;
      }

      const actions = document.createElement('div');
      actions.className = 'brain-record-actions';

      const isVirtualNowFocus = Boolean(record?.__virtual_now_focus);
      const viewButton = this.makeBrainRecordAction('View', () => this.openBrainRecordEditor(record, true));
      const editButton = this.makeBrainRecordAction('Edit / Tune', () => this.openBrainRecordEditor(record, false));
      const recommendation = this.primaryHygieneRecommendation(record);
      const recommendationType = recommendation ? String(recommendation.type || '') : '';
      const approveButton = this.makeBrainRecordAction('Approve', () => {
        void this.approveBrainRecord(record.record_id);
      });
      const rejectButton = this.makeBrainRecordAction('Reject', () => {
        void this.rejectBrainRecord(record.record_id);
      });
      const restoreButton = this.makeBrainRecordAction('Restore / Mark Current', () => {
        void this.markBrainRecordCurrent(record.record_id);
      });

      const moreActions = [
        {
          label: this.sourceRuntime(record) ? 'Edit' : 'Copy/Edit Runtime Override',
          onClick: () => this.openBrainRecordEditor(record, false),
          enabled: true,
        },
        {
          label: this.sourceRuntime(record) ? 'Set Active' : 'Set Active via Runtime Override',
          onClick: () => {
            void this.setBrainRecordActive(record.record_id);
          },
          enabled: !this.isRecordCurrent(record),
        },
        {
          label: 'Mark Current',
          onClick: () => {
            void this.markBrainRecordCurrent(record.record_id);
          },
          enabled: !this.isRecordCurrent(record),
        },
        {
          label: 'Mark Historical',
          onClick: () => {
            void this.markBrainRecordHistorical(record.record_id);
          },
          enabled: !this.isRecordHistorical(record),
        },
        {
          label: 'Mark Superseded',
          onClick: () => {
            void this.markBrainRecordSuperseded(record.record_id);
          },
          enabled: String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase() !== 'superseded',
        },
        {
          label: this.sourceRuntime(record) ? 'Disable' : 'Disable via Runtime Override',
          onClick: () => {
            void this.deactivateBrainRecord(record.record_id);
          },
          enabled: !this.isRecordDisabled(record),
        },
        {
          label: this.approvedCleanupRecommendations[String(record.record_id || '')] ? 'Approved for cleanup' : 'Approve Recommendation',
          onClick: () => {
            if (!recommendationType) return;
            this.toggleApprovedCleanup(record, recommendationType);
          },
          enabled: Boolean(recommendationType),
        },
        {
          label: 'Apply Hygiene Recommendation',
          onClick: () => {
            if (!recommendationType) return;
            void this.applyBrainRecordRecommendation(record.record_id, recommendationType);
          },
          enabled: Boolean(recommendationType),
        },
        {
          label: 'Split to Current Rule',
          onClick: () => {
            void this.splitBrainRecord(record);
          },
          enabled: this.shouldShowSplitAction(record),
        },
        {
          label: 'Raw JSON',
          onClick: () => this.openBrainRecordEditor(record, true),
          enabled: true,
        },
        {
          label: 'Advanced Details',
          onClick: () => this.openBrainRecordEditor(record, true),
          enabled: true,
        },
      ];
      const moreMenu = this.makeBrainRecordMoreMenu(record, moreActions);

      if (this.brainRecordsView === 'review') {
        actions.append(viewButton);
        if (this.isRecordReviewActionable(record)) {
          actions.append(approveButton, rejectButton);
        }
        actions.append(moreMenu);
      } else if (this.brainRecordsView === 'history') {
        actions.append(viewButton);
        if (!this.isRecordCurrent(record)) {
          actions.append(restoreButton);
        }
        actions.append(moreMenu);
      } else if (this.brainRecordsView === 'library') {
        actions.append(viewButton, editButton, moreMenu);
      } else {
        actions.append(viewButton);
        if (!isVirtualNowFocus) {
          actions.append(editButton);
        }
      }

      if (this.brainRecordsView === 'library' && this.brainRecordsFilters.showRawJson) {
        const raw = document.createElement('pre');
        raw.className = 'brain-record-raw';
        raw.textContent = JSON.stringify(record.raw_record || {}, null, 2);
        if (reasonNode) {
          li.append(title, meta, summary, reasonNode, actions, raw);
        } else {
          li.append(title, meta, summary, actions, raw);
        }
        mount.append(li);
        return;
      }

      if (reasonNode) {
        li.append(title, meta, summary, reasonNode, actions);
      } else {
        li.append(title, meta, summary, actions);
      }
      mount.append(li);
    });
  }

  makeBrainRecordAction(label, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'xv7-control-button brain-record-action';
    button.textContent = label;
    button.disabled = this.brainRecordBusy;
    button.addEventListener('click', onClick);
    return button;
  }

  isRecordCurrent(record) {
    const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
    return relevance === 'current';
  }

  isRecordHistorical(record) {
    const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
    return relevance === 'historical' || relevance === 'superseded' || relevance === 'expired';
  }

  isRecordDisabled(record) {
    const status = String(record?.status_label || record?.status || '').toLowerCase();
    return status === 'disabled' || status === 'archived';
  }

  isRecordReviewActionable(record) {
    const status = String(record?.status_label || record?.status || '').toLowerCase();
    const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
    return status === 'pending' || status === 'pending_review' || relevance === 'needs_review';
  }

  shouldShowSplitAction(record) {
    const recommendation = this.primaryHygieneRecommendation(record);
    if (String(recommendation?.type || '') === 'split_record') return true;
    const flags = new Set((Array.isArray(record?.hygiene_flags) ? record.hygiene_flags : []).map((item) => String(item).toLowerCase()));
    return flags.has('mixed_historical_and_current') || flags.has('mixed_historical_and_operational');
  }

  makeBrainRecordMoreMenu(record, actions) {
    const wrapper = document.createElement('div');
    wrapper.className = 'brain-record-more';

    const menu = document.createElement('div');
    menu.className = 'brain-record-more-menu hidden';
    menu.dataset.recordId = String(record?.record_id || '');

    const toggle = this.makeBrainRecordAction('More', () => {
      const currentlyHidden = menu.classList.contains('hidden');
      if (currentlyHidden && !menu.childElementCount) {
        actions.forEach((actionDef) => {
          if (!actionDef || actionDef.enabled === false) return;
          const action = this.makeBrainRecordAction(actionDef.label, actionDef.onClick);
          action.classList.add('brain-record-more-action');
          menu.append(action);
        });
      }
      menu.classList.toggle('hidden');
    });

    wrapper.append(toggle, menu);
    return wrapper;
  }

  openBrainRecordEditor(record, readOnly) {
    if (!record || typeof record !== 'object') return;
    this.brainRecordEditorRecord = record;
    this.brainRecordEditorId = String(record.record_id || '');

    if (this.els.brainRecordEditor) this.els.brainRecordEditor.classList.remove('hidden');
    if (this.els.brainRecordEditorId) this.els.brainRecordEditorId.textContent = this.brainRecordEditorId || '-';
    if (this.els.brainRecordEditorLayer) this.els.brainRecordEditorLayer.value = String(record.layer || '');
    if (this.els.brainRecordEditorTitle) this.els.brainRecordEditorTitle.value = String(record.title || '');
    if (this.els.brainRecordEditorBody) this.els.brainRecordEditorBody.value = String(record.body || '');
    if (this.els.brainRecordEditorTags) this.els.brainRecordEditorTags.value = Array.isArray(record.tags) ? record.tags.join(', ') : '';
    if (this.els.brainRecordEditorStatus) this.els.brainRecordEditorStatus.value = String(record.status || 'active');
    if (this.els.brainRecordEditorRaw) {
      this.els.brainRecordEditorRaw.value = JSON.stringify(record.raw_record || {}, null, 2);
    }

    [
      this.els.brainRecordEditorLayer,
      this.els.brainRecordEditorTitle,
      this.els.brainRecordEditorBody,
      this.els.brainRecordEditorTags,
      this.els.brainRecordEditorStatus,
    ].forEach((el) => {
      if (!el) return;
      el.disabled = Boolean(readOnly);
    });

    if (this.els.brainRecordEditorSaveButton) {
      this.els.brainRecordEditorSaveButton.disabled = Boolean(readOnly);
    }
  }

  closeBrainRecordEditor() {
    this.brainRecordEditorRecord = null;
    this.brainRecordEditorId = null;
    if (this.els.brainRecordEditor) this.els.brainRecordEditor.classList.add('hidden');
  }

  async saveBrainRecordEdits() {
    if (!this.brainRecordEditorId) return;

    const payload = {
      layer: this.els.brainRecordEditorLayer?.value || 'memory',
      title: this.els.brainRecordEditorTitle?.value || '',
      body: this.els.brainRecordEditorBody?.value || '',
      tags: String(this.els.brainRecordEditorTags?.value || '')
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      status: this.els.brainRecordEditorStatus?.value || 'active',
    };

    try {
      this.brainRecordBusy = true;
      if (this.els.brainRecordsStatus) this.els.brainRecordsStatus.textContent = 'Saving runtime override...';
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(this.brainRecordEditorId)}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      this.closeBrainRecordEditor();
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async deactivateBrainRecord(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/deactivate`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async setBrainRecordActive(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/set-active`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async approveBrainRecord(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/approve`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async rejectBrainRecord(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/reject`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async markBrainRecordCurrent(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/mark-current`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async markBrainRecordHistorical(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/mark-historical`, { method: 'POST' });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async markBrainRecordSuperseded(recordId) {
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/mark-superseded`, {
        method: 'POST',
        body: JSON.stringify({ relevance_state: 'superseded' }),
      });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  async applyBrainRecordRecommendation(recordId, recommendationType) {
    if (!recordId || !recommendationType) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/apply-recommendation`, {
        method: 'POST',
        body: JSON.stringify({ recommendation_type: recommendationType, approve: true }),
      });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  toggleApprovedCleanup(record, recommendationType) {
    const recordId = String(record?.record_id || '');
    if (!recordId || !recommendationType) return;
    if (this.approvedCleanupRecommendations[recordId]) {
      delete this.approvedCleanupRecommendations[recordId];
    } else {
      this.approvedCleanupRecommendations[recordId] = recommendationType;
    }
    this.updateBrainRecordsCalmSummary();
    this.renderBrainRecordsViews();
    this.renderBrainRecordsList();
  }

  async applyApprovedCleanup() {
    const entries = Object.entries(this.approvedCleanupRecommendations);
    if (!entries.length) {
      this.showAlert('No approved cleanup recommendations selected.', false, 1800);
      return;
    }

    this.brainRecordBusy = true;
    try {
      for (const [recordId, recommendationType] of entries) {
        await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/apply-recommendation`, {
          method: 'POST',
          body: JSON.stringify({
            recommendation_type: recommendationType,
            approve: true,
          }),
        });
      }
      this.approvedCleanupRecommendations = {};
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
      this.updateBrainRecordsCalmSummary();
      this.renderBrainRecordsViews();
    }
  }

  async splitBrainRecord(record) {
    const recordId = String(record?.record_id || '');
    if (!recordId) return;
    try {
      this.brainRecordBusy = true;
      await this.fetchJson(`/runtime/brain/records/${encodeURIComponent(recordId)}/split`, {
        method: 'POST',
        body: JSON.stringify({
          operational_title: `Operational: ${String(record?.title || '').trim() || recordId}`,
          operational_body: String(record?.body || '').trim(),
          tags: Array.isArray(record?.tags) ? record.tags : [],
          layer: record?.layer || 'knowledge',
        }),
      });
      await this.refreshBrainRecords();
    } catch (error) {
      this.showAlert(this.humanizeError(error), true, 2200);
    } finally {
      this.brainRecordBusy = false;
    }
  }

  /**
   * @param {string} text
   */
  extractReasoning(text) {
    const matches = [...text.matchAll(/<\|think\|>([\s\S]*?)<\/\|think\|>/g)];
    if (!matches.length) return null;
    return matches.map((m) => m[1]).join('\n\n');
  }

  collectArtifactPatchProposal(message) {
    const source = message && typeof message === 'object' ? message : {};
    const metadata = source.metadata && typeof source.metadata === 'object' ? source.metadata : source;
    const proposal = metadata.artifact_patch_proposal;
    return this.normalizeArtifactPatchProposal(proposal);
  }

  normalizeArtifactPatchProposal(proposal) {
    if (!proposal || typeof proposal !== 'object') return null;
    if (proposal.type !== 'artifact_patch_proposal') return null;
    const targetPath = typeof proposal.target_path === 'string' ? proposal.target_path.trim() : '';
    const previewPath = typeof proposal.preview_path === 'string' ? proposal.preview_path.trim() : '';
    const diff = typeof proposal.diff === 'string' ? proposal.diff : '';
    if (!targetPath) return null;
    const validation = proposal.validation && typeof proposal.validation === 'object' ? proposal.validation : {};
    const postApplyVerification = proposal.post_apply_verification && typeof proposal.post_apply_verification === 'object'
      ? proposal.post_apply_verification
      : {};
    const targetedValidation = proposal.targeted_validation && typeof proposal.targeted_validation === 'object'
      ? proposal.targeted_validation
      : {};
    const checks = Array.isArray(validation.checks) ? validation.checks : [];
    const verifyChecks = Array.isArray(postApplyVerification.checks) ? postApplyVerification.checks : [];
    const targetedChecks = Array.isArray(targetedValidation.checks) ? targetedValidation.checks : [];
    return {
      ...proposal,
      target_path: targetPath,
      preview_path: previewPath,
      operation: typeof proposal.operation === 'string' ? proposal.operation : 'create',
      diff,
      applied: proposal.applied === true,
      requires_confirmation: proposal.requires_confirmation !== false,
      validation: {
        status: typeof validation.status === 'string' ? validation.status : 'failed',
        checks,
        failures: Array.isArray(validation.failures) ? validation.failures : [],
      },
      post_apply_verification: {
        status: typeof postApplyVerification.status === 'string' ? postApplyVerification.status : '',
        checks: verifyChecks,
        failures: Array.isArray(postApplyVerification.failures) ? postApplyVerification.failures : [],
      },
      targeted_validation: {
        status: typeof targetedValidation.status === 'string' ? targetedValidation.status : '',
        checks: targetedChecks,
        failures: Array.isArray(targetedValidation.failures) ? targetedValidation.failures : [],
      },
    };
  }

  appendArtifactPatchProposal(article, proposal) {
    if (!proposal || typeof proposal !== 'object') return;

    const status = String(proposal.validation?.status || 'failed').toLowerCase();
    const verifyStatus = String(proposal.post_apply_verification?.status || '').toLowerCase();
    const targetedStatus = String(proposal.targeted_validation?.status || '').toLowerCase();
    const panel = document.createElement('section');
    panel.className = 'artifact-patch-proposal';

    const header = document.createElement('div');
    header.className = 'artifact-patch-proposal-header';
    header.innerHTML = `
      <strong>Patch proposal</strong>
      <span class="artifact-patch-chip ${proposal.applied ? 'is-applied' : 'is-draft'}">${proposal.applied ? 'applied' : 'draft only / not applied'}</span>
      <span class="artifact-patch-chip ${status === 'passed' ? 'is-valid' : 'is-invalid'}">validation: ${status}</span>
    `;

    if (verifyStatus) {
      const verifyChip = document.createElement('span');
      verifyChip.className = `artifact-patch-chip ${verifyStatus === 'passed' ? 'is-valid' : 'is-invalid'}`;
      verifyChip.textContent = `post-apply verify: ${verifyStatus}`;
      header.append(verifyChip);
    }

    if (targetedStatus) {
      const targetedChip = document.createElement('span');
      targetedChip.className = `artifact-patch-chip ${targetedStatus === 'passed' ? 'is-valid' : 'is-invalid'}`;
      targetedChip.textContent = `targeted validation: ${targetedStatus}`;
      header.append(targetedChip);
    }

    const summary = document.createElement('p');
    summary.className = 'artifact-patch-proposal-summary';
    summary.textContent = `target: ${proposal.target_path} | operation: ${proposal.operation} | confirmation required: ${proposal.requires_confirmation ? 'yes' : 'no'}`;

    const previewLine = proposal.preview_path
      ? `preview: ${proposal.preview_path}`
      : '';
    if (previewLine) {
      const preview = document.createElement('p');
      preview.className = 'artifact-patch-proposal-summary artifact-patch-preview';
      preview.textContent = previewLine;
      panel.append(header, summary, preview);
    } else {
      panel.append(header, summary);
    }

    const diffBlock = document.createElement('pre');
    diffBlock.className = 'artifact-patch-diff';
    diffBlock.textContent = proposal.diff || 'No diff generated.';

    const checks = Array.isArray(proposal.validation?.checks) ? proposal.validation.checks : [];
    if (checks.length) {
      const list = document.createElement('ul');
      list.className = 'artifact-patch-checks';
      checks.slice(0, 8).forEach((check) => {
        if (!check || typeof check !== 'object') return;
        const item = document.createElement('li');
        item.textContent = `${check.name || 'check'}: ${check.status || 'unknown'}`;
        list.append(item);
      });
      panel.append(list, diffBlock);
    } else {
      panel.append(diffBlock);
    }

    const verifyChecks = Array.isArray(proposal.post_apply_verification?.checks)
      ? proposal.post_apply_verification.checks
      : [];
    if (verifyChecks.length) {
      const verifyList = document.createElement('ul');
      verifyList.className = 'artifact-patch-checks artifact-patch-checks-verify';
      verifyChecks.slice(0, 8).forEach((check) => {
        if (!check || typeof check !== 'object') return;
        const item = document.createElement('li');
        item.textContent = `verify ${check.name || 'check'}: ${check.status || 'unknown'}`;
        verifyList.append(item);
      });
      panel.append(verifyList);
    }

    const targetedChecks = Array.isArray(proposal.targeted_validation?.checks)
      ? proposal.targeted_validation.checks
      : [];
    if (targetedChecks.length) {
      const targetedList = document.createElement('ul');
      targetedList.className = 'artifact-patch-checks artifact-patch-checks-targeted';
      targetedChecks.slice(0, 8).forEach((check) => {
        if (!check || typeof check !== 'object') return;
        const item = document.createElement('li');
        item.textContent = `targeted ${check.name || 'check'}: ${check.status || 'unknown'}`;
        targetedList.append(item);
      });
      panel.append(targetedList);
    }

    if (!proposal.applied && proposal.requires_confirmation) {
      const applyButton = document.createElement('button');
      applyButton.type = 'button';
      applyButton.className = 'artifact-patch-apply-button';
      applyButton.textContent = 'Apply Patch';
      applyButton.addEventListener('click', () => {
        const approved = typeof window.confirm === 'function'
          ? window.confirm('Apply the pending patch proposal to the workspace?')
          : false;
        if (!approved) return;
        void this.sendQuickPrompt('apply patch');
      });
      panel.append(applyButton);
    }

    article.append(panel);
  }

  collectCodeArtifacts(message) {
    const source = message && typeof message === 'object' ? message : {};
    const metadata = source.metadata && typeof source.metadata === 'object' ? source.metadata : source;
    const artifacts = [];
    const seen = new Set();

    const addArtifact = (artifact) => {
      const normalized = this.normalizeCodeArtifact(artifact);
      if (!normalized) return;
      const key = this.codeArtifactKey(normalized);
      if (seen.has(key)) return;
      seen.add(key);
      artifacts.push(normalized);
    };

    if (Array.isArray(metadata.code_artifacts)) {
      metadata.code_artifacts.forEach(addArtifact);
    }

    if (metadata.code_artifact && typeof metadata.code_artifact === 'object') {
      addArtifact(metadata.code_artifact);
    }

    return artifacts;
  }

  normalizeCodeArtifact(artifact) {
    if (!artifact || typeof artifact !== 'object') return null;
    const filename = typeof artifact.filename === 'string' ? artifact.filename.trim() : '';
    const content = typeof artifact.content === 'string' ? artifact.content : '';
    if (!filename || !content) return null;
    return {
      ...artifact,
      filename,
      content,
      language: typeof artifact.language === 'string' ? artifact.language : '',
      applied: artifact.applied === true,
      previewable: artifact.previewable === true,
    };
  }

  codeArtifactKey(artifact) {
    return [
      artifact.filename,
      artifact.language,
      artifact.content,
      artifact.applied ? '1' : '0',
      artifact.previewable ? '1' : '0',
    ].join('\u001f');
  }

  debugArtifactReceipt(message, metadata) {
    const debugEnabled = Boolean(window.__XV7_DEBUG_ARTIFACTS);
    if (!debugEnabled || !console || typeof console.debug !== 'function') return;
    const artifacts = this.collectCodeArtifacts(message);
    const metaArtifacts = [];
    if (metadata && typeof metadata === 'object') {
      if (Array.isArray(metadata.code_artifacts)) {
        metaArtifacts.push(...metadata.code_artifacts);
      }
      if (metadata.code_artifact && typeof metadata.code_artifact === 'object') {
        metaArtifacts.push(metadata.code_artifact);
      }
    }
    console.debug('XV7 artifact receipt', {
      messageArtifacts: artifacts.length,
      metadataArtifacts: metaArtifacts.length,
      hasCodeArtifact: metaArtifacts.length > 0 || artifacts.length > 0,
      hasPatchProposal: Boolean(this.collectArtifactPatchProposal(metadata)),
    });
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
