/**
 * xv7 zero-dependency SPA controller.
 *
 * Architecture goals:
 * - Keep state local and explicit for predictable UI updates.
 * - Favor async/await and cancellation-safe request handling.
 * - Leave extension points for streaming/WebSocket and avatar channels.
 */
import {
  classifyPromptRuntime,
  createRuntimeStatusModel,
  phaseFromOperatorStatus,
  runtimeActionLabel,
  updateRuntimeStatusElement,
} from './runtime-status.js';
import { fetchJsonWithBase } from './app/api-client.js';
import {
  resolveAvatarMediaEnabled as resolveAvatarMediaEnabledHelper,
  avatarStateLabel as avatarStateLabelHelper,
  renderAvatarStateUI as renderAvatarStateUIHelper,
  renderAvatarDiagnostics as renderAvatarDiagnosticsHelper,
} from './app/avatar-controller.js';
import {
  applyPreferredVoiceIfNeeded as applyPreferredVoiceIfNeededHelper,
  buildSpeechUtterance as buildSpeechUtteranceHelper,
  choosePreferredVoice as choosePreferredVoiceHelper,
  clampVoiceNumber as clampVoiceNumberHelper,
  dispatchVoiceEvent as dispatchVoiceEventHelper,
  isFemaleLikeVoice as isFemaleLikeVoiceHelper,
  loadVoicePreferences as loadVoicePreferencesHelper,
  mergeTranscript as mergeTranscriptHelper,
  normalizeSpeechText as normalizeSpeechTextHelper,
  playVoiceSample as playVoiceSampleHelper,
  refreshVoiceVoices as refreshVoiceVoicesHelper,
  renderReadAloudButton as renderReadAloudButtonHelper,
  renderVoiceDiagnostics as renderVoiceDiagnosticsHelper,
  renderVoiceSelectOptions as renderVoiceSelectOptionsHelper,
  saveVoicePreferences as saveVoicePreferencesHelper,
  setVoiceStatus as setVoiceStatusHelper,
  setupVoiceOutput as setupVoiceOutputHelper,
  startSpeechPlayback as startSpeechPlaybackHelper,
  stopVoicePlayback as stopVoicePlaybackHelper,
  stripReasoningTokens as stripReasoningTokensHelper,
  syncVoiceSettingsToControls as syncVoiceSettingsToControlsHelper,
  toggleReadAloud as toggleReadAloudHelper,
  updateReadAloudButtons as updateReadAloudButtonsHelper,
} from './app/voice-controller.js';
import {
  applyStatusTone as applyStatusToneHelper,
  appendReceiptField as appendReceiptFieldHelper,
  copyToClipboardText,
} from './app/dom-helpers.js';
import {
  appendArtifactHighlightedLine as appendArtifactHighlightedLineHelper,
  appendArtifactToken as appendArtifactTokenHelper,
  appendCodeArtifacts as appendCodeArtifactsHelper,
  appendCssArtifactLine as appendCssArtifactLineHelper,
  appendCssTokenizedLine as appendCssTokenizedLineHelper,
  appendHtmlArtifactLine as appendHtmlArtifactLineHelper,
  appendHtmlTagTokens as appendHtmlTagTokensHelper,
  appendPlainArtifactLine as appendPlainArtifactLineHelper,
  appendPythonArtifactLine as appendPythonArtifactLineHelper,
  appendSiteBundleCard as appendSiteBundleCardHelper,
  buildSiteBundlePreviewSrcdoc as buildSiteBundlePreviewSrcdocHelper,
  collectSiteBundleFiles as collectSiteBundleFilesHelper,
  copyCodeArtifact as copyCodeArtifactHelper,
  createArtifactHighlightState as createArtifactHighlightStateHelper,
  createCodeArtifactCard as createCodeArtifactCardHelper,
  deriveSiteBundleFileLabel as deriveSiteBundleFileLabelHelper,
  downloadCodeArtifact as downloadCodeArtifactHelper,
  findSiteBundleFile as findSiteBundleFileHelper,
  getMessageSiteBundle as getMessageSiteBundleHelper,
  getSiteBundleFileOptions as getSiteBundleFileOptionsHelper,
  inferLanguageFromFilename as inferLanguageFromFilenameHelper,
  isArtifactPreviewable as isArtifactPreviewableHelper,
  isLocalBundleAssetReference as isLocalBundleAssetReferenceHelper,
  isSiteBundlePreviewableFile as isSiteBundlePreviewableFileHelper,
  languageLabel as languageLabelHelper,
  normalizeArtifactLanguage as normalizeArtifactLanguageHelper,
  normalizeBundlePath as normalizeBundlePathHelper,
  normalizeSiteBundle as normalizeSiteBundleHelper,
  renderArtifactCodeRows as renderArtifactCodeRowsHelper,
  resolveBundleAssetPath as resolveBundleAssetPathHelper,
  sanitizeArtifactDownloadName as sanitizeArtifactDownloadNameHelper,
  shouldSuppressSiteBundleForOperatorPayload as shouldSuppressSiteBundleForOperatorPayloadHelper,
  siteBundlePreviewAllowsScripts as siteBundlePreviewAllowsScriptsHelper,
  splitAssetReference as splitAssetReferenceHelper,
  switchArtifactTab as switchArtifactTabHelper,
  toggleArtifactPreview as toggleArtifactPreviewHelper,
} from './app/artifact-renderer.js';
import {
  appendMeaningfulReceiptField as appendMeaningfulReceiptFieldHelper,
  appendOperatorReceiptsSection as appendOperatorReceiptsSectionHelper,
  appendOperatorResultSection as appendOperatorResultSectionHelper,
  appendResponseDetailsDisclosure as appendResponseDetailsDisclosureHelper,
  appendSafeTraceSummarySection as appendSafeTraceSummarySectionHelper,
  appendWhyThisAnswerSection as appendWhyThisAnswerSectionHelper,
  createResponseDetailsSection as createResponseDetailsSectionHelper,
  contextLayerChipLabel as contextLayerChipLabelHelper,
  extractReceiptId as extractReceiptIdHelper,
  formatMeaningfulValue as formatMeaningfulValueHelper,
  getSafeTraceSummary as getSafeTraceSummaryHelper,
  hasMeaningfulValue as hasMeaningfulValueHelper,
  isHistoryCandidate as isHistoryCandidateHelper,
  isReviewCandidate as isReviewCandidateHelper,
  inferAssistantTimestamp as inferAssistantTimestampHelper,
  looksLikeStructuredPayload as looksLikeStructuredPayloadHelper,
  nowIso as nowIsoHelper,
  operatorActionDisplayLabel as operatorActionDisplayLabelHelper,
  operatorChipLabel as operatorChipLabelHelper,
  operatorRuntimeStatusLabel as operatorRuntimeStatusLabelHelper,
  operatorRuntimeStatusTone as operatorRuntimeStatusToneHelper,
  renderBrainRecordsViews as renderBrainRecordsViewsHelper,
  renderOperatorActivity as renderOperatorActivityHelper,
  renderRetrievalJournal as renderRetrievalJournalHelper,
  receiptField as receiptFieldHelper,
  resolveAssistantVisibleText as resolveAssistantVisibleTextHelper,
  safeOperatorActionName as safeOperatorActionNameHelper,
  safeTraceArtifactType as safeTraceArtifactTypeHelper,
  safeTraceResponseType as safeTraceResponseTypeHelper,
  safeTraceSafetyState as safeTraceSafetyStateHelper,
  safeTraceSourceLayers as safeTraceSourceLayersHelper,
  safeTraceText as safeTraceTextHelper,
  safeTraceValidationSummary as safeTraceValidationSummaryHelper,
  sanitizeVisibleAssistantText as sanitizeVisibleAssistantTextHelper,
  summarizeContextReceipt as summarizeContextReceiptHelper,
  updateStatusFromHistory as updateStatusFromHistoryHelper,
  parseLayeredContextFromCompact as parseLayeredContextFromCompactHelper,
} from './app/render-helpers.js';

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
  chatMessageTimeoutMs = 3 * 60 * 1000;

  /** @type {boolean} */
  isSending = false;

  /** @type {AbortController | null} */
  activeRequestController = null;

  /** @type {boolean} */
  requestStopRequested = false;

  /** @type {{phase:string,label:string,hint:string,actionName:string,startedAt:number,endedAt:number|null,busy:boolean}|null} */
  runtimeStatusModel = null;

  /** @type {HTMLElement | null} */
  pendingAssistantArticle = null;

  /** @type {HTMLElement | null} */
  pendingAssistantStatusElement = null;

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

    this.setRuntimeStatus({
      phase: 'idle',
      label: 'Ready',
      hint: 'Ready for the next instruction.',
    });

    this.bindEvents();
    void this.initialize();
  }

  resolveAvatarMediaEnabled() {
    return resolveAvatarMediaEnabledHelper();
  }

  bindEvents() {
    this.els.sendButton.addEventListener('click', () => {
      if (this.isSending) {
        this.stopActiveRequest();
        return;
      }
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
      const payload = await this.fetchJson('/api/operator/commands?operator_mode=true', {
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
    this.syncComposerSendAvailability();
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
    if (this.isSending) return;

    const raw = this.els.promptInput.value.trim();
    if (!raw) return;

    const classifiedRuntime = classifyPromptRuntime(raw);
    const activePhase = classifiedRuntime.phase === 'needs_approval'
      ? 'routing'
      : classifiedRuntime.phase;

    this.requestStopRequested = false;
    this.activeRequestController = new AbortController();

    this.setAvatarState('thinking', 'message-sent');

    this.showAlert('', false);
    this.setSendBusy(true);
    this.setHardwareLoad('Inference', 74);

    try {
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

      const pendingArticle = this.beginPendingAssistantCard({
        phase: activePhase,
        label: classifiedRuntime.label,
        actionName: '',
      });

      await this.ensureSession(this.activeRequestController.signal);

      if (raw.startsWith('/')) {
        const firstClassPrefix = raw.toLowerCase().trim().split(/\s+/)[0];
        const firstClassSlash = new Set(['/build', '/export', '/write', '/commit', '/push', '/github', '/publish']);
        if (firstClassSlash.has(firstClassPrefix)) {
          const data = await this.fetchJson(
            `/api/sessions/${this.currentSessionId}/messages`,
            {
              method: 'POST',
              body: JSON.stringify({ raw_text: raw }),
            },
            this.chatMessageTimeoutMs,
            this.activeRequestController.signal,
          );
          this.setRuntimeStatus({
            phase: 'streaming',
            label: 'Streaming',
            hint: 'Rendering the response.',
          });
          this.renderSessionResponse(data);
          return;
        }

        await this.sendSlashCommand(raw, this.activeRequestController.signal, pendingArticle);
        this.memoryLogCount += 1;
        this.updateSessionTelemetry();
        this.setHardwareLoad('Ready', 12);
        this.setAvatarState('idle', 'operator-stage-response');
        this.setRuntimeStatus({
          phase: 'complete',
          label: 'Complete',
          hint: 'Finished.',
        });
        return;
      }

      const messagePayload = { raw_text: raw };
      if (this.operatorModeActive) {
        messagePayload.operator_mode = true;
      }

      const data = await this.fetchJson(
        `/api/sessions/${this.currentSessionId}/messages`,
        {
          method: 'POST',
          body: JSON.stringify(messagePayload),
        },
        this.chatMessageTimeoutMs,
        this.activeRequestController.signal,
      );

      this.setRuntimeStatus({
        phase: 'streaming',
        label: 'Streaming',
        hint: 'Rendering the response.',
      });
      this.renderSessionResponse(data);
    } catch (error) {
      if (error && typeof error === 'object' && error.name === 'AbortError' && this.requestStopRequested) {
        this.setHardwareLoad('Ready', 12);
        this.setAvatarState('idle', 'message-stopped');
        this.setRuntimeStatus({
          phase: 'blocked',
          label: 'Stopped',
          hint: 'Request cancelled.',
        });
        this.finalizePendingAssistantCard(
          {
            phase: 'blocked',
            label: 'Stopped',
            hint: 'Request cancelled.',
          },
          'Stopped. Request cancelled.',
        );
        return;
      }

      const failureMessage = this.humanizeError(error);
      this.setHardwareLoad('Recovery', 24);
      this.showAlert(failureMessage, true);
      this.setAvatarState('error', 'message-error');
      this.scheduleAvatarReset('idle', 1800);
      this.setRuntimeStatus({
        phase: 'failed',
        label: 'Failed',
        hint: 'Action failed. Review the result card.',
      });
      this.finalizePendingAssistantCard(
        {
          phase: 'failed',
          label: 'Failed',
          hint: 'Action failed. Review the result card.',
        },
        `Failed: ${failureMessage}`,
      );
    } finally {
      this.activeRequestController = null;
      this.requestStopRequested = false;
      this.setSendBusy(false);
      if (this.pendingAssistantArticle) {
        this.finalizePendingAssistantCard(
          {
            phase: 'failed',
            label: 'Failed',
            hint: 'Action failed. Review the result card.',
          },
          'Failed: Response did not complete. Please retry.',
        );
      }
      this.els.promptInput.focus();
    }
  }

  renderSessionResponse(data) {
    const response = data && typeof data === 'object' ? data : {};
    const responseMetadata = response.metadata && typeof response.metadata === 'object' ? response.metadata : {};
      // Site bundle rendering
      const siteBundlePayload = this.getMessageSiteBundle({
        ...response,
        metadata: responseMetadata,
      });
      if (siteBundlePayload) {
        const bundleText = typeof response.visible_text === 'string' ? response.visible_text : 'Site bundle generated.';
        const bundleMeta = {
          site_bundle: siteBundlePayload,
        };
        const bundleArticle = this.appendMessageCard(
          'assistant',
          bundleText,
          null,
          bundleMeta,
          this.nowIso(),
          this.consumePendingAssistantCard(),
        );
        if (bundleArticle) {
          try {
            this.appendSiteBundleCard(bundleArticle, siteBundlePayload);
            this.scheduleResponseReveal(bundleArticle);
            if (typeof siteBundlePayload === 'object') {
              this.latestAssistantMeta = bundleMeta;
            }
          } catch (bundleError) {
            this.appendRenderErrorNotice(
              bundleArticle,
              bundleError,
              'The assistant response rendered, but the site bundle card could not be displayed.',
            );
            this.showAlert('Recovered from site bundle render failure. You can retry the request.', true, 3000);
          }
        }
        this.memoryLogCount = response.messages ? response.messages.length : this.memoryLogCount;
        this.updateSessionTelemetry();
        this.renderRetrievalJournal(response);
        this.setHardwareLoad('Ready', 12);
        this.setAvatarState('idle', 'assistant-response-received');
        this.setRuntimeStatus({
          phase: 'complete',
          label: 'Complete',
          hint: 'Site preview ready.',
        });
        return;
      }
    const messages = Array.isArray(response.messages) ? response.messages : [];
    const resolvedAssistant = this.resolveAssistantPayload(response);
    const assistantMessage = resolvedAssistant.payload;
    const hasValidAssistantMessage = assistantMessage && typeof assistantMessage === 'object';
    const assistantContent = hasValidAssistantMessage && typeof assistantMessage.content === 'string'
      ? assistantMessage.content
      : '';
    const assistantMeta = hasValidAssistantMessage && assistantMessage.metadata && typeof assistantMessage.metadata === 'object'
      ? assistantMessage.metadata
      : (hasValidAssistantMessage ? assistantMessage : {});
    const fallbackAssistantMetaRaw =
      responseMetadata.last_assistant_payload && typeof responseMetadata.last_assistant_payload === 'object'
        ? responseMetadata.last_assistant_payload
        : {};
    const fallbackAssistantMeta = { ...fallbackAssistantMetaRaw };
    if (resolvedAssistant.assistantFromMessages) {
      delete fallbackAssistantMeta.visible_text;
      delete fallbackAssistantMeta.content;
    }
    const mergedAssistantMeta = {
      ...fallbackAssistantMeta,
      ...assistantMeta,
    };
    const mergedSiteBundlePayload = this.getMessageSiteBundle(mergedAssistantMeta);
    const responseError = hasValidAssistantMessage
      ? null
      : new Error('Assistant response did not include a valid assistant payload.');
    const assistantArtifacts = this.collectCodeArtifacts(assistantMessage);
    if (assistantArtifacts.length) {
      mergedAssistantMeta.code_artifacts = assistantArtifacts;
    }
    if (responseError) {
      mergedAssistantMeta.render_error = responseError.message;
    }

    this.debugArtifactReceipt(assistantMessage, mergedAssistantMeta);
    const assistantText = this.resolveAssistantVisibleText(mergedAssistantMeta, assistantContent);
    const reasoningText = this.extractReasoning(assistantContent);

    let assistantArticle;
    let renderError = null;
    try {
      assistantArticle = this.appendMessageCard(
        'assistant',
        assistantText || 'No assistant content returned.',
        reasoningText,
        mergedAssistantMeta,
        this.inferAssistantTimestamp(mergedAssistantMeta),
        this.consumePendingAssistantCard(),
      );
    } catch (error) {
      renderError = error;
      assistantArticle = this.appendMessageCard(
        'assistant',
        assistantText || 'No assistant content returned.',
        reasoningText,
        null,
        this.nowIso(),
        this.consumePendingAssistantCard(),
      );
    }

    if (responseError && assistantArticle) {
      const detailLines = [
        `response had messages array: ${resolvedAssistant.hasMessagesArray}`,
        `assistant message found: ${resolvedAssistant.assistantFromMessages}`,
        `last_assistant_payload found: ${resolvedAssistant.hasLastAssistantPayload}`,
      ];
      this.appendRenderErrorNotice(
        assistantArticle,
        responseError,
        'Xoduz response was received, but the UI could not render the assistant message.',
        detailLines,
      );
      this.showAlert('Recovered from malformed assistant response. Please retry if needed.', true, 2600);
    }

    if (renderError && assistantArticle) {
      this.appendRenderErrorNotice(assistantArticle, renderError);
      this.showAlert(`Recovered from assistant render failure: ${this.humanizeError(renderError)}`, true, 2600);
    }

    if (mergedSiteBundlePayload && assistantArticle) {
      try {
        this.appendSiteBundleCard(assistantArticle, mergedSiteBundlePayload);
        this.scheduleResponseReveal(assistantArticle);
      } catch (bundleError) {
        this.appendRenderErrorNotice(
          assistantArticle,
          bundleError,
          'The assistant response rendered, but the site bundle card could not be displayed.',
        );
        this.showAlert('Recovered from site bundle render failure. You can retry the request.', true, 3000);
      }
    }

    this.setAvatarState('idle', 'assistant-response-received');

    const spokenText = String(assistantText || 'No assistant content returned.').trim();
    if (spokenText && assistantArticle) {
      this.startSpeechPlayback(spokenText, {
        messageId: assistantArticle?.dataset?.messageId || null,
        startStatus: 'Reading response aloud...',
        stopStatus: 'Read-aloud stopped.',
        failStatus: 'Browser blocked voice playback. Try clicking Read again.',
      });
    }

    this.renderModelUseReceipt(responseMetadata.model_use_receipt);
    this.renderOperatorActivity(responseMetadata.operator_action_history);
    this.updateStatusFromHistory(responseMetadata.operator_action_history);

    const operatorHistory = Array.isArray(responseMetadata.operator_action_history)
      ? responseMetadata.operator_action_history
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
    this.renderRetrievalJournal(response);
    this.setHardwareLoad('Ready', 12);

    if (operatorHistory.length) {
      this.updateRuntimeStatusFromHistory(operatorHistory);
    } else {
      this.setRuntimeStatus({
        phase: 'complete',
        label: 'Complete',
        hint: 'Finished.',
      });
    }
  }

  resolveAssistantPayload(responseJson) {
    const response = responseJson && typeof responseJson === 'object' ? responseJson : {};
    const messages = Array.isArray(response.messages) ? response.messages : [];
    const latestAssistant = [...messages]
      .reverse()
      .find((message) => message && typeof message === 'object' && String(message.role || '').toLowerCase() === 'assistant');

    const metadata = response.metadata && typeof response.metadata === 'object' ? response.metadata : {};
    const lastAssistantPayload = metadata.last_assistant_payload && typeof metadata.last_assistant_payload === 'object'
      ? metadata.last_assistant_payload
      : null;

    return {
      payload: latestAssistant || lastAssistantPayload,
      hasMessagesArray: Array.isArray(response.messages),
      assistantFromMessages: Boolean(latestAssistant),
      hasLastAssistantPayload: Boolean(lastAssistantPayload),
    };
  }

  async sendQuickPrompt(text) {
    const value = String(text || '').trim();
    if (!value) return;
    this.els.promptInput.value = value;
    await this.sendMessage();
  }

  async ensureSession(signal = undefined) {
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
    }, undefined, signal);
    this.currentSessionId = sessionData.session_id;
    if (!this.currentSessionId || typeof this.currentSessionId !== 'string') {
      throw new Error('Session creation response did not include a valid session_id.');
    }
  }

  async sendSlashCommand(commandText, signal = undefined, replaceArticle = null) {
    let payload;
    try {
      payload = await this.fetchJson('/api/operator/stage', {
        method: 'POST',
        body: JSON.stringify({
          session_id: this.currentSessionId,
          command_text: commandText,
          operator_mode: this.operatorModeActive,
        }),
      }, undefined, signal);
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
    this.appendMessageCard(
      'assistant',
      payload?.answer || 'Operator action processed.',
      null,
      assistantMeta,
      this.nowIso(),
      replaceArticle || this.consumePendingAssistantCard(),
    );

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
  appendMessageCard(role, content, reasoning, messageMetadata = null, timestamp = '', replaceArticle = null) {
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

    if (role === 'assistant') {
      article.classList.add('response-reveal-card');
      this.prepareResponseRevealSection(text, 'body');
      this.prepareResponseRevealSection(actions, 'actions');
      article.append(roleLabel, text);
    } else {
      article.append(roleLabel, actions, text);
    }

    const copyPayload = {
      role,
      text: content,
      timestamp: timestamp || '',
      receiptSummary: [],
    };

    const siteBundlePayload = role === 'assistant' ? this.getMessageSiteBundle(messageMetadata) : null;
    const hasCodeArtifacts = role === 'assistant' && this.collectCodeArtifacts(messageMetadata).length > 0;
    const patchProposal = role === 'assistant' ? this.collectArtifactPatchProposal(messageMetadata) : null;

    if (role === 'assistant') {
      try {
        // Site bundle payloads use appendSiteBundleCard (called by the caller after this
        // returns) — skip per-file card rendering to prevent duplicate individual cards.
        if (!siteBundlePayload) {
          this.appendCodeArtifacts(article, messageMetadata);
        }
        this.appendOperatorRuntimeCard(article, messageMetadata);
        this.appendArtifactPatchProposal(article, patchProposal, content, messageMetadata);
        copyPayload.receiptSummary = this.appendReceiptChips(article, messageMetadata);
        this.markResponseChildrenForReveal(article, '.receipt-chip-row', 'actions');
        article.append(actions);
        this.appendResponseDetailsDisclosure(article, messageMetadata);
        if (messageMetadata && typeof messageMetadata === 'object') {
          this.latestAssistantMeta = messageMetadata;
          this.updateBrainRecordsCalmSummary();
        }
      } catch (error) {
        this.appendRenderErrorNotice(article, error);
        this.showAlert(`Recovered from assistant render failure: ${this.humanizeError(error)}`, true, 2600);
      }
    }

    if (replaceArticle && replaceArticle.parentElement === this.els.chatTimeline) {
      replaceArticle.replaceWith(article);
      if (this.pendingAssistantArticle === replaceArticle) {
        this.pendingAssistantArticle = null;
        this.pendingAssistantStatusElement = null;
      }
    } else {
      this.els.chatTimeline.append(article);
    }
    if (role === 'assistant') {
      this.scheduleResponseReveal(article);
    }
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

  responseRevealReducedMotion() {
    return Boolean(
      typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    );
  }

  prepareResponseRevealSection(element, kind = 'body') {
    if (!element) return null;
    element.classList.add('response-reveal', `response-reveal--${kind}`);
    if (this.responseRevealReducedMotion()) {
      this.markResponseSectionVisible(element);
    }
    return element;
  }

  markResponseSectionVisible(section) {
    if (!section) return null;
    section.classList.add('is-visible');
    return section;
  }

  markResponseChildrenForReveal(article, selector, kind = 'body') {
    if (!article || !selector) return [];
    return [...article.querySelectorAll(selector)].map((element) =>
      this.prepareResponseRevealSection(element, kind),
    );
  }

  scheduleResponseReveal(card) {
    if (!card || card.dataset.role !== 'assistant') return;

    const orderedSections = [
      ...card.querySelectorAll('.response-reveal--body'),
      ...card.querySelectorAll('.response-reveal--artifact'),
      ...card.querySelectorAll('.response-reveal--actions'),
      ...card.querySelectorAll('.response-reveal--details'),
    ].filter((section, index, sections) => section && sections.indexOf(section) === index);

    if (this.responseRevealReducedMotion()) {
      orderedSections.forEach((section) => this.markResponseSectionVisible(section));
      return;
    }

    const delaysByKind = {
      body: 0,
      artifact: 80,
      actions: 140,
      details: 210,
    };

    orderedSections.forEach((section) => {
      if (section.classList.contains('is-visible')) return;
      const kind = section.classList.contains('response-reveal--details')
        ? 'details'
        : section.classList.contains('response-reveal--actions')
          ? 'actions'
          : section.classList.contains('response-reveal--artifact')
            ? 'artifact'
            : 'body';
      window.setTimeout(() => {
        this.markResponseSectionVisible(section);
      }, delaysByKind[kind]);
    });
  }

  appendRenderErrorNotice(article, error, titleText = 'Recovered from a render error.', extraLines = []) {
    if (!article) return;

    const notice = document.createElement('div');
    notice.className = 'chat-render-error';

    const title = document.createElement('p');
    title.className = 'chat-render-error-title';
    title.textContent = titleText;

    const message = document.createElement('p');
    message.className = 'chat-render-error-message';
    message.textContent = `Details: ${this.humanizeError(error)}`;

    notice.append(title, message);

    extraLines
      .filter((line) => typeof line === 'string' && line.trim())
      .forEach((line) => {
        const detail = document.createElement('p');
        detail.className = 'chat-render-error-message';
        detail.textContent = line;
        notice.append(detail);
      });

    article.append(notice);
  }

  collectSiteBundleFiles(bundlePayload) {
    return collectSiteBundleFilesHelper(bundlePayload);
  }

  getMessageSiteBundle(message) {
    return getMessageSiteBundleHelper(message, {
      shouldSuppressSiteBundleForOperatorPayloadFn: this.shouldSuppressSiteBundleForOperatorPayload.bind(this),
      inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
    });
  }

  shouldSuppressSiteBundleForOperatorPayload(metadata) {
    return shouldSuppressSiteBundleForOperatorPayloadHelper(metadata, {
      getMessageOperatorResultFn: this.getMessageOperatorResult.bind(this),
    });
  }

  normalizeSiteBundle(bundlePayload) {
    return normalizeSiteBundleHelper(bundlePayload, {
      inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
    });
  }

  deriveSiteBundleFileLabel(path) {
    return deriveSiteBundleFileLabelHelper(path);
  }

  getSiteBundleFileOptions(bundle) {
    return getSiteBundleFileOptionsHelper(bundle, {
      deriveSiteBundleFileLabelFn: this.deriveSiteBundleFileLabel.bind(this),
    });
  }

  findSiteBundleFile(bundle, path) {
    return findSiteBundleFileHelper(bundle, path);
  }

  isSiteBundlePreviewableFile(file) {
    return isSiteBundlePreviewableFileHelper(file);
  }

  normalizeBundlePath(path) {
    return normalizeBundlePathHelper(path);
  }

  splitAssetReference(reference) {
    return splitAssetReferenceHelper(reference);
  }

  isLocalBundleAssetReference(reference) {
    return isLocalBundleAssetReferenceHelper(reference);
  }

  resolveBundleAssetPath(baseFilePath, reference) {
    return resolveBundleAssetPathHelper(baseFilePath, reference, {
      isLocalBundleAssetReferenceFn: this.isLocalBundleAssetReference.bind(this),
      splitAssetReferenceFn: this.splitAssetReference.bind(this),
      normalizeBundlePathFn: this.normalizeBundlePath.bind(this),
    });
  }

  siteBundlePreviewAllowsScripts() {
    return siteBundlePreviewAllowsScriptsHelper();
  }

  buildSiteBundlePreviewSrcdoc(bundle, selectedFile) {
    return buildSiteBundlePreviewSrcdocHelper(bundle, selectedFile, {
      isSiteBundlePreviewableFileFn: this.isSiteBundlePreviewableFile.bind(this),
      normalizeBundlePathFn: this.normalizeBundlePath.bind(this),
      resolveBundleAssetPathFn: this.resolveBundleAssetPath.bind(this),
      siteBundlePreviewAllowsScriptsFn: this.siteBundlePreviewAllowsScripts.bind(this),
    });
  }

  appendSiteBundleCard(article, bundlePayload) {
    return appendSiteBundleCardHelper(article, bundlePayload, {
      normalizeSiteBundleFn: this.normalizeSiteBundle.bind(this),
      getSiteBundleFileOptionsFn: this.getSiteBundleFileOptions.bind(this),
      findSiteBundleFileFn: this.findSiteBundleFile.bind(this),
      isSiteBundlePreviewableFileFn: this.isSiteBundlePreviewableFile.bind(this),
      renderArtifactCodeRowsFn: this.renderArtifactCodeRows.bind(this),
      buildSiteBundlePreviewSrcdocFn: this.buildSiteBundlePreviewSrcdoc.bind(this),
      prepareResponseRevealSectionFn: this.prepareResponseRevealSection.bind(this),
    });
  }

  appendCodeArtifacts(article, messageMetadata) {
    return appendCodeArtifactsHelper(article, messageMetadata, {
      collectCodeArtifactsFn: this.collectCodeArtifacts.bind(this),
      createCodeArtifactCardFn: this.createCodeArtifactCard.bind(this),
      prepareResponseRevealSectionFn: this.prepareResponseRevealSection.bind(this),
      appendRenderErrorNoticeFn: this.appendRenderErrorNotice.bind(this),
      showAlertFn: this.showAlert.bind(this),
    });
  }

  createCodeArtifactCard(artifact) {
    return createCodeArtifactCardHelper(artifact, {
      normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
      inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
      isArtifactPreviewableFn: this.isArtifactPreviewable.bind(this),
      languageLabelFn: this.languageLabel.bind(this),
      copyCodeArtifactFn: this.copyCodeArtifact.bind(this),
      downloadCodeArtifactFn: this.downloadCodeArtifact.bind(this),
      toggleArtifactPreviewFn: this.toggleArtifactPreview.bind(this),
      renderArtifactCodeRowsFn: this.renderArtifactCodeRows.bind(this),
      sendQuickPromptFn: this.sendQuickPrompt.bind(this),
      switchArtifactTabFn: this.switchArtifactTab.bind(this),
      nextArtifactId: () => `artifact-${++this.messageCounter}`,
    });
  }

  renderArtifactCodeRows(content, language) {
    return renderArtifactCodeRowsHelper(content, language, {
      createArtifactHighlightStateFn: this.createArtifactHighlightState.bind(this),
      appendArtifactHighlightedLineFn: this.appendArtifactHighlightedLine.bind(this),
    });
  }

  createArtifactHighlightState(language) {
    return createArtifactHighlightStateHelper(language, {
      normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
    });
  }

  appendArtifactHighlightedLine(container, line, language, state) {
    return appendArtifactHighlightedLineHelper(container, line, language, state, {
      normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
      appendHtmlArtifactLineFn: this.appendHtmlArtifactLine.bind(this),
      appendCssArtifactLineFn: this.appendCssArtifactLine.bind(this),
      appendPythonArtifactLineFn: this.appendPythonArtifactLine.bind(this),
      appendPlainArtifactLineFn: this.appendPlainArtifactLine.bind(this),
    });
  }

  appendPlainArtifactLine(container, line) {
    return appendPlainArtifactLineHelper(container, line);
  }

  appendHtmlArtifactLine(container, line, state) {
    return appendHtmlArtifactLineHelper(container, line, state, {
      appendCssArtifactLineFn: this.appendCssArtifactLine.bind(this),
      appendArtifactTokenFn: this.appendArtifactToken.bind(this),
      appendHtmlTagTokensFn: this.appendHtmlTagTokens.bind(this),
    });
  }

  appendHtmlTagTokens(container, rawTag, state) {
    return appendHtmlTagTokensHelper(container, rawTag, state, {
      appendArtifactTokenFn: this.appendArtifactToken.bind(this),
    });
  }

  appendCssArtifactLine(container, line, state) {
    return appendCssArtifactLineHelper(container, line, state, {
      appendCssValueTokensFn: (target, text) => this.appendCssTokenizedLine(target, text),
      appendArtifactTokenFn: this.appendArtifactToken.bind(this),
      appendCssTokenizedLineFn: this.appendCssTokenizedLine.bind(this),
    });
  }

  appendCssTokenizedLine(container, text) {
    return appendCssTokenizedLineHelper(container, text, {
      appendArtifactTokenFn: this.appendArtifactToken.bind(this),
    });
  }

  appendPythonArtifactLine(container, line) {
    return appendPythonArtifactLineHelper(container, line, {
      appendArtifactTokenFn: this.appendArtifactToken.bind(this),
    });
  }

  appendArtifactToken(container, className, text) {
    return appendArtifactTokenHelper(container, className, text);
  }

  switchArtifactTab(card, tabName) {
    return switchArtifactTabHelper(card, tabName);
  }

  normalizeArtifactLanguage(language) {
    return normalizeArtifactLanguageHelper(language);
  }

  inferLanguageFromFilename(filename) {
    return inferLanguageFromFilenameHelper(filename);
  }

  languageLabel(language) {
    return languageLabelHelper(language, {
      normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
    });
  }

  isArtifactPreviewable(artifact, filename, language) {
    return isArtifactPreviewableHelper(artifact, filename, language, {
      normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
      inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
    });
  }

  async copyCodeArtifact(card, artifact, button) {
    return copyCodeArtifactHelper(card, artifact, button, {
      copyToClipboardFn: this.copyToClipboard.bind(this),
      artifactCopyState: this.artifactCopyState,
    });
  }

  downloadCodeArtifact(artifact) {
    return downloadCodeArtifactHelper(artifact, {
      sanitizeArtifactDownloadNameFn: this.sanitizeArtifactDownloadName.bind(this),
    });
  }

  sanitizeArtifactDownloadName(filename) {
    return sanitizeArtifactDownloadNameHelper(filename);
  }

  toggleArtifactPreview(card, artifact, button) {
    return toggleArtifactPreviewHelper(card, artifact, button, {
      switchArtifactTabFn: this.switchArtifactTab.bind(this),
    });
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

    return compactReceipts;
  }

  resolveOperatorResult(meta) {
    if (!meta || typeof meta !== 'object') return null;
    if (meta.operator_result && typeof meta.operator_result === 'object') {
      return meta.operator_result;
    }
    const receipts = Array.isArray(meta.operator_receipts) ? meta.operator_receipts : [];
    for (const receipt of receipts) {
      if (receipt && typeof receipt === 'object' && receipt.operator_result && typeof receipt.operator_result === 'object') {
        return receipt.operator_result;
      }
    }
    return null;
  }

  getMessageOperatorResult(message) {
    const meta = message && typeof message === 'object' ? message : {};
    const result = this.resolveOperatorResult(meta);
    if (!result || typeof result !== 'object') return null;

    const actionName = String(result.action_name || '').trim();
    const status = String(result.status || '').trim();
    const changedFiles = Array.isArray(result.changed_files) ? result.changed_files.filter(Boolean) : [];
    const validationCommands = Array.isArray(result.validation_commands_run) ? result.validation_commands_run.filter(Boolean) : [];
    const safetyNotes = Array.isArray(result.safety_notes) ? result.safety_notes.filter(Boolean) : [];
    const localOnlyWarning = Array.isArray(result.local_only_files_warning) ? result.local_only_files_warning.filter(Boolean) : [];
    const firstFailure = String(result.first_failure || '').trim();
    const commitPushState = result.commit_push_state && typeof result.commit_push_state === 'object'
      ? result.commit_push_state
      : {};

    const meaningfulAction = actionName && actionName !== 'operator_action' && actionName !== 'unknown';
    const meaningfulStatus = status && status !== 'unknown';
    const meaningfulCommitState = Object.values(commitPushState).some((value) => value === true);
    const hasMeaningfulPayload = meaningfulAction
      || meaningfulStatus
      || changedFiles.length > 0
      || validationCommands.length > 0
      || safetyNotes.length > 0
      || localOnlyWarning.length > 0
      || Boolean(firstFailure)
      || meaningfulCommitState;

    if (!hasMeaningfulPayload) return null;

    return {
      ...result,
      action_name: meaningfulAction ? actionName : '',
      status: meaningfulStatus ? status : '',
      changed_files: changedFiles,
      validation_commands_run: validationCommands,
      safety_notes: safetyNotes,
      local_only_files_warning: localOnlyWarning,
      first_failure: firstFailure,
      commit_push_state: commitPushState,
    };
  }

  summarizeOperatorList(value, max = 3) {
    const items = Array.isArray(value)
      ? value.map((item) => String(item || '').trim()).filter(Boolean)
      : [];
    if (!items.length) return 'none';
    if (items.length <= max) return items.join(', ');
    return `${items.slice(0, max).join(', ')} (+${items.length - max} more)`;
  }

  firstOperatorRuntimeValue(sources, keys) {
    const sourceList = Array.isArray(sources) ? sources : [];
    const keyList = Array.isArray(keys) ? keys : [];
    for (const source of sourceList) {
      if (!source || typeof source !== 'object') continue;
      for (const key of keyList) {
        const value = source[key];
        if (this.hasMeaningfulValue(value, { allowFalse: true })) return value;
      }
    }
    return null;
  }

  operatorRuntimeBoolLabel(value, trueLabel, falseLabel) {
    if (value === true) return trueLabel;
    if (value === false) return falseLabel;
    const text = String(value ?? '').trim().toLowerCase();
    if (!text) return '';
    if (['true', 'yes', 'clean', 'synced', 'in_sync'].includes(text)) return trueLabel;
    if (['false', 'no', 'dirty', 'not_clean', 'not_synced', 'out_of_sync', 'ahead', 'behind', 'diverged'].includes(text)) return falseLabel;
    return String(value).trim();
  }

  appendOperatorRuntimeRows(card, rows) {
    const safeRows = Array.isArray(rows) ? rows.filter((row) => row && row.value) : [];
    if (!safeRows.length) return false;

    const list = document.createElement('dl');
    list.className = 'operator-runtime-card-facts';
    safeRows.forEach((row) => {
      const item = document.createElement('div');
      item.className = 'operator-runtime-card-fact';

      const label = document.createElement('dt');
      label.textContent = row.label;

      const value = document.createElement('dd');
      value.textContent = row.value;

      item.append(label, value);
      list.append(item);
    });
    card.append(list);
    return true;
  }

  appendOperatorRuntimeCard(article, messageMetadata) {
    const data = this.getOperatorRuntimeCardData(messageMetadata);
    if (!data) return false;

    const card = document.createElement('section');
    card.className = `operator-runtime-card status-${data.statusTone}`;
    this.prepareResponseRevealSection(card, 'artifact');

    const header = document.createElement('div');
    header.className = 'operator-runtime-card-header';

    const title = document.createElement('p');
    title.className = 'operator-runtime-card-title';
    title.textContent = data.title;

    const badge = document.createElement('span');
    badge.className = `operator-runtime-card-badge status-${data.statusTone}`;
    badge.textContent = data.statusLabel;

    header.append(title, badge);

    const summary = document.createElement('p');
    summary.className = 'operator-runtime-card-summary';
    summary.textContent = data.summary;

    card.append(header, summary);
    this.appendOperatorRuntimeRows(card, data.rows);
    article.append(card);
    return true;
  }

  getOperatorRuntimeCardData(messageMetadata) {
    const result = this.getMessageOperatorResult(messageMetadata);
    if (!result) return null;

    const actionName = String(result.action_name || '').trim();
    const actionLabels = {
      operator_status_report: 'Check the repo',
      operator_validation_report: 'Run validation',
      operator_commit_report: 'Commit and push',
    };
    const title = actionLabels[actionName];
    if (!title) return null;

    const normalizedStatus = String(result.status || '').trim().toLowerCase();
    const statusLabel = this.operatorRuntimeStatusLabel(normalizedStatus);
    const statusTone = this.operatorRuntimeStatusTone(normalizedStatus);
    const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
    const validationCommands = Array.isArray(result.validation_commands_run) ? result.validation_commands_run : [];
    const commitPushState = result.commit_push_state && typeof result.commit_push_state === 'object'
      ? result.commit_push_state
      : {};
    const meta = messageMetadata && typeof messageMetadata === 'object' ? messageMetadata : {};
    const receipts = Array.isArray(meta.operator_receipts) ? meta.operator_receipts.filter((receipt) => receipt && typeof receipt === 'object') : [];
    const latestReceipt = receipts.length ? receipts[receipts.length - 1] : {};
    const receiptPreview = latestReceipt.data_preview && typeof latestReceipt.data_preview === 'object'
      ? latestReceipt.data_preview
      : {};
    const repoState = result.repo_state && typeof result.repo_state === 'object'
      ? result.repo_state
      : {};
    const validationSummary = result.validation_summary && typeof result.validation_summary === 'object'
      ? result.validation_summary
      : {};
    const runtimeSources = [result, repoState, receiptPreview, latestReceipt];
    const rows = [];

    let summary = '';
    if (actionName === 'operator_status_report') {
      summary = changedFiles.length
        ? `Changed files: ${this.summarizeOperatorList(changedFiles, 2)}.`
        : 'No changed files reported.';
      const branch = this.firstOperatorRuntimeValue(runtimeSources, ['branch', 'current_branch', 'git_branch']);
      const clean = this.firstOperatorRuntimeValue(runtimeSources, ['clean', 'working_tree_clean', 'is_clean']);
      const sync = this.firstOperatorRuntimeValue(runtimeSources, ['sync', 'sync_status', 'remote_sync', 'remote_tracking_status']);
      if (branch) rows.push({ label: 'Branch', value: String(branch).trim() });
      const cleanLabel = this.operatorRuntimeBoolLabel(clean, 'Clean', 'Dirty');
      if (cleanLabel) rows.push({ label: 'Working tree', value: cleanLabel });
      const syncLabel = this.operatorRuntimeBoolLabel(sync, 'Synced', 'Not synced');
      if (syncLabel) rows.push({ label: 'Remote', value: syncLabel });
    } else if (actionName === 'operator_validation_report') {
      summary = validationCommands.length
        ? `Checks: ${this.summarizeOperatorList(validationCommands, 1)}.`
        : 'No validation commands were reported.';
      const validationStatus = this.firstOperatorRuntimeValue(
        [validationSummary, result, receiptPreview, latestReceipt],
        ['status', 'validation_status', 'result'],
      );
      const passCount = this.firstOperatorRuntimeValue(
        [validationSummary, result, receiptPreview],
        ['passed', 'pass_count', 'passed_count'],
      );
      const failCount = this.firstOperatorRuntimeValue(
        [validationSummary, result, receiptPreview],
        ['failed', 'fail_count', 'failed_count'],
      );
      const validationLabel = validationStatus
        ? String(validationStatus).trim()
        : (normalizedStatus ? statusLabel : '');
      if (validationLabel) rows.push({ label: 'Validation', value: validationLabel });
      if (passCount !== null || failCount !== null) {
        rows.push({
          label: 'Summary',
          value: `pass=${passCount ?? 0}; fail=${failCount ?? 0}`,
        });
      } else if (result.first_failure) {
        rows.push({ label: 'Summary', value: 'fail=1' });
      }
    } else if (actionName === 'operator_commit_report') {
      if (commitPushState.commit_created === true || commitPushState.push_performed === true) {
        summary = `Commit created: ${commitPushState.commit_created === true ? 'yes' : 'no'}; push performed: ${commitPushState.push_performed === true ? 'yes' : 'no'}.`;
      } else {
        summary = normalizedStatus === 'needs_approval'
          ? 'Waiting for explicit approval before mutation.'
          : 'No commit or push was performed.';
      }
      rows.push({
        label: 'Approval',
        value: commitPushState.requires_separate_approval === true || normalizedStatus === 'needs_approval'
          ? 'Required'
          : 'Not required',
      });
      rows.push({
        label: 'Mutation',
        value: `commit=${commitPushState.commit_created === true ? 'created' : 'not created'}; push=${commitPushState.push_performed === true ? 'performed' : 'not performed'}`,
      });
    }

    if (!summary) return null;
    return {
      title,
      statusLabel,
      statusTone,
      summary,
      rows,
    };
  }

  operatorRuntimeStatusLabel(status) {
    return operatorRuntimeStatusLabelHelper(status);
  }

  operatorRuntimeStatusTone(status) {
    return operatorRuntimeStatusToneHelper(status);
  }

  appendResponseDetailsDisclosure(article, messageMetadata) {
    appendResponseDetailsDisclosureHelper(article, messageMetadata, {
      appendSafeTraceSummarySectionFn: this.appendSafeTraceSummarySection.bind(this),
      appendOperatorReceiptsSection: this.appendOperatorReceiptsSection.bind(this),
      appendOperatorResultSection: this.appendOperatorResultSection.bind(this),
      appendWhyThisAnswerSection: this.appendWhyThisAnswerSection.bind(this),
      prepareResponseRevealSection: this.prepareResponseRevealSection.bind(this),
    });
  }

  appendSafeTraceSummarySection(container, messageMetadata) {
    return appendSafeTraceSummarySectionHelper(container, messageMetadata, {
      getSafeTraceSummaryFn: this.getSafeTraceSummary.bind(this),
      createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
      appendReceiptFieldFn: this.appendReceiptField.bind(this),
    });
  }

  getSafeTraceSummary(messageMetadata) {
    return getSafeTraceSummaryHelper(messageMetadata, {
      getMessageOperatorResult: this.getMessageOperatorResult.bind(this),
      safeOperatorActionName: this.safeOperatorActionName.bind(this),
      safeTraceText: this.safeTraceText.bind(this),
      safeTraceSourceLayers: this.safeTraceSourceLayers.bind(this),
      safeTraceArtifactType: this.safeTraceArtifactType.bind(this),
      safeTraceSafetyState: this.safeTraceSafetyState.bind(this),
      safeTraceValidationSummary: this.safeTraceValidationSummary.bind(this),
      safeTraceResponseType: this.safeTraceResponseType.bind(this),
      operatorActionDisplayLabel: this.operatorActionDisplayLabel.bind(this),
    });
  }

  safeTraceResponseType(meta, policy, hints = {}) {
    return safeTraceResponseTypeHelper(meta, policy, hints, this.safeTraceText.bind(this));
  }

  safeTraceSourceLayers(meta, contextReceipt) {
    return safeTraceSourceLayersHelper(meta, contextReceipt, this.contextLayerChipLabel.bind(this));
  }

  safeTraceArtifactType(meta, policy) {
    return safeTraceArtifactTypeHelper(meta, policy, {
      getMessageSiteBundle: this.getMessageSiteBundle.bind(this),
      collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
      collectCodeArtifacts: this.collectCodeArtifacts.bind(this),
      safeTraceTextFn: this.safeTraceText.bind(this),
    });
  }

  safeTraceSafetyState(result, receipt, meta) {
    return safeTraceSafetyStateHelper(result, receipt, meta);
  }

  safeTraceValidationSummary(result, meta, policy) {
    return safeTraceValidationSummaryHelper(result, meta, policy, {
      collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
      safeTraceTextFn: this.safeTraceText.bind(this),
    });
  }

  safeOperatorActionName(value) {
    return safeOperatorActionNameHelper(value);
  }

  operatorActionDisplayLabel(actionName) {
    return operatorActionDisplayLabelHelper(actionName);
  }

  safeTraceText(value) {
    return safeTraceTextHelper(value, {
      hasMeaningfulValueFn: this.hasMeaningfulValue.bind(this),
      formatMeaningfulValueFn: this.formatMeaningfulValue.bind(this),
    });
  }

  createResponseDetailsSection(title) {
    return createResponseDetailsSectionHelper(title);
  }

  hasMeaningfulValue(value, options = {}) {
    return hasMeaningfulValueHelper(value, options);
  }

  formatMeaningfulValue(value, options = {}) {
    return formatMeaningfulValueHelper(value, options, this.hasMeaningfulValue.bind(this));
  }

  appendMeaningfulReceiptField(container, label, value, options = {}) {
    return appendMeaningfulReceiptFieldHelper(container, label, value, options, {
      formatMeaningfulValueFn: this.formatMeaningfulValue.bind(this),
      appendReceiptFieldFn: this.appendReceiptField.bind(this),
    });
  }

  appendOperatorReceiptsSection(container, messageMetadata) {
    return appendOperatorReceiptsSectionHelper(container, messageMetadata, {
      createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
      appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
      safeOperatorActionName: this.safeOperatorActionName.bind(this),
      safeTraceText: this.safeTraceText.bind(this),
    });
  }

  appendOperatorResultSection(container, messageMetadata) {
    return appendOperatorResultSectionHelper(container, messageMetadata, {
      getMessageOperatorResult: this.getMessageOperatorResult.bind(this),
      createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
      appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
    });
  }

  appendWhyThisAnswerSection(container, messageMetadata) {
    return appendWhyThisAnswerSectionHelper(container, messageMetadata, {
      contextLayerChipLabelFn: this.contextLayerChipLabel.bind(this),
      collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
      boolText: this.boolText.bind(this),
      createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
      appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
    });
  }

  boolText(value) {
    if (value === true) return 'true';
    if (value === false) return 'false';
    return '-';
  }

  renderOperatorActivity(history) {
    renderOperatorActivityHelper(history, {
      operatorActivityList: this.els.operatorActivityList,
      operatorSummaryChip: this.els.operatorSummaryChip,
      appendReceiptFieldFn: this.appendReceiptField.bind(this),
    });
  }

  updateStatusFromHistory(history) {
    updateStatusFromHistoryHelper(history, {
      renderStatusStrip: this.renderStatusStrip.bind(this),
      statusSummary: this.statusSummary,
      refreshStatusTimestamp: this.refreshStatusTimestamp.bind(this),
    });
  }

  /**
   * Displays top retrieval snippets if backend supplies them; otherwise uses
   * recent assistant/user timeline as a local fallback preview.
   *
   * @param {any} response
   */
  renderRetrievalJournal(response) {
    renderRetrievalJournalHelper(response, {
      retrievalJournal: this.els.retrievalJournal,
      stripReasoningTokensFn: this.stripReasoningTokens.bind(this),
    });
  }

  renderBrainRecordsViews() {
    renderBrainRecordsViewsHelper({
      brainRecordsViews: this.els.brainRecordsViews,
      brainRecordCounts: this.brainRecordCounts,
      brainRecordsView: this.brainRecordsView,
      brainLibraryControls: this.els.brainLibraryControls,
      brainReviewToolbar: this.els.brainReviewToolbar,
      brainRecordsApplyCleanupButton: this.els.brainRecordsApplyCleanupButton,
      approvedCleanupRecommendations: this.approvedCleanupRecommendations,
      syncBrainLibraryFiltersFromUi: this.syncBrainLibraryFiltersFromUi.bind(this),
    });
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
    return isReviewCandidateHelper(record);
  }

  isHistoryCandidate(record) {
    return isHistoryCandidateHelper(record);
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

  resolveArtifactPatchProposalTitle(proposal, content = '', messageMetadata = null) {
    if (!proposal || typeof proposal !== 'object') return 'Patch proposal';
    if (proposal.applied !== true) return 'Patch proposal';

    const provenance = messageMetadata && typeof messageMetadata === 'object' && messageMetadata.provenance && typeof messageMetadata.provenance === 'object'
      ? messageMetadata.provenance
      : {};
    const visibleText = String(content || '').toLowerCase();
    const artifactPatch = String(provenance.artifact_patch || '').toLowerCase();

    if (artifactPatch === 'full_test_guard' || visibleText.includes('full-suite validation')) {
      return 'Full-test guard';
    }
    if (artifactPatch === 'post_apply_targeted_validation' || visibleText.startsWith('targeted validation')) {
      return 'Targeted validation';
    }
    if (artifactPatch === 'post_apply_preview' || visibleText.startsWith('preview path is')) {
      return 'Preview ready';
    }
    if (artifactPatch === 'post_apply_verified' || visibleText.startsWith('post-apply verification')) {
      return 'Post-apply verification';
    }
    return 'Patch applied';
  }

  appendArtifactPatchProposal(article, proposal, content = '', messageMetadata = null) {
    if (!proposal || typeof proposal !== 'object') return;

    const status = String(proposal.validation?.status || 'failed').toLowerCase();
    const verifyStatus = String(proposal.post_apply_verification?.status || '').toLowerCase();
    const targetedStatus = String(proposal.targeted_validation?.status || '').toLowerCase();
    const panel = document.createElement('section');
    panel.className = 'artifact-patch-proposal';
    this.prepareResponseRevealSection(panel, 'artifact');

    const header = document.createElement('div');
    header.className = 'artifact-patch-proposal-header';
    const title = this.resolveArtifactPatchProposalTitle(proposal, content, messageMetadata);
    header.innerHTML = `
      <strong>${title}</strong>
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
    return stripReasoningTokensHelper(text);
  }

  normalizeSpeechText(text) {
    return normalizeSpeechTextHelper(text);
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
  setSendBusy(locked) {
    this.isSending = locked;
    this.els.promptInput.disabled = locked;
    this.els.sendButton.textContent = locked ? 'Stop' : 'Send';
    this.els.sendButton.classList.toggle('is-stop', locked);
    this.els.sendButton.classList.toggle('is-busy', locked);
    this.els.sendButton.setAttribute('aria-label', locked ? 'Stop active request' : 'Send message');
    this.els.sendButton.title = locked ? 'Stop active request' : 'Send message';
    this.syncComposerSendAvailability();
  }

  syncComposerSendAvailability() {
    this.els.sendButton.disabled = false;
  }

  lockInput(locked) {
    this.setSendBusy(locked);
  }

  stopActiveRequest() {
    if (!this.isSending) return;
    this.requestStopRequested = true;
    if (this.activeRequestController && !this.activeRequestController.signal.aborted) {
      this.activeRequestController.abort();
      return;
    }

    this.setRuntimeStatus({
      phase: 'blocked',
      label: 'Stopped',
      hint: 'Request cancelled.',
    });
    this.setSendBusy(false);
  }

  setRuntimeStatus(model) {
    this.runtimeStatusModel = createRuntimeStatusModel(model || {});
    this.renderPendingAssistantStatus(this.runtimeStatusModel);
    return this.runtimeStatusModel;
  }

  beginPendingAssistantCard(model) {
    this.removePendingAssistantCard();

    const article = document.createElement('article');
    article.className = 'chat-card chat-card-assistant pending-assistant';
    article.dataset.role = 'assistant';
    article.dataset.timestamp = this.nowIso();
    article.dataset.messageId = `pending-${++this.messageCounter}`;

    const roleLabel = document.createElement('p');
    roleLabel.className = 'chat-role-label';
    roleLabel.textContent = 'Assistant Output';

    const actions = document.createElement('div');
    actions.className = 'message-actions';
    actions.hidden = true;

    const status = document.createElement('div');
    status.className = 'runtime-status assistant-runtime-status';

    article.append(roleLabel, actions, status);
    this.els.chatTimeline.append(article);
    this.els.chatTimeline.scrollTop = this.els.chatTimeline.scrollHeight;

    this.pendingAssistantArticle = article;
    this.pendingAssistantStatusElement = status;
    this.setRuntimeStatus(model);
    return article;
  }

  renderPendingAssistantStatus(model) {
    const article = this.pendingAssistantArticle;
    const element = this.pendingAssistantStatusElement;
    if (!article || !element || !article.isConnected) return null;

    const status = updateRuntimeStatusElement(element, model) || createRuntimeStatusModel(model || {});
    article.dataset.runtimePhase = status.phase;
    article.classList.toggle('is-busy', status.busy);
    article.classList.toggle('is-failed', status.phase === 'failed');
    article.classList.toggle('is-blocked', status.phase === 'blocked');
    article.classList.toggle('needs-approval', status.phase === 'needs_approval');
    return status;
  }

  consumePendingAssistantCard() {
    const article = this.pendingAssistantArticle && this.pendingAssistantArticle.isConnected
      ? this.pendingAssistantArticle
      : null;
    this.pendingAssistantArticle = null;
    this.pendingAssistantStatusElement = null;
    return article;
  }

  finalizePendingAssistantCard(model, fallbackText = '') {
    const replaceArticle = this.consumePendingAssistantCard();
    if (!replaceArticle) return null;

    const status = createRuntimeStatusModel(model || {});
    const text = String(fallbackText || status.hint || status.label || 'Action failed.').trim();
    const article = this.appendMessageCard(
      'assistant',
      text,
      null,
      null,
      this.nowIso(),
      replaceArticle,
    );

    if (article) {
      article.dataset.runtimePhase = status.phase;
      article.classList.toggle('is-failed', status.phase === 'failed');
      article.classList.toggle('is-blocked', status.phase === 'blocked');
      article.classList.remove('is-busy');
    }

    return article;
  }

  removePendingAssistantCard() {
    const article = this.consumePendingAssistantCard();
    article?.remove();
  }

  updateRuntimeStatusFromHistory(history) {
    const items = Array.isArray(history) ? history : [];
    if (!items.length) return;

    const latest = items[items.length - 1];
    const actionName = typeof latest?.action_name === 'string' ? latest.action_name : '';
    const actionLabel = runtimeActionLabel(actionName);
    const phase = phaseFromOperatorStatus(latest?.status);
    let hint = 'Finished.';

    if (phase === 'failed') {
      hint = `${actionLabel} failed. Review the result card.`;
    } else if (phase === 'blocked') {
      hint = `${actionLabel} was blocked by safety policy.`;
    } else if (phase === 'needs_approval') {
      hint = `${actionLabel} is waiting for explicit approval.`;
    } else if (phase === 'complete') {
      hint = `Finished: ${actionLabel}.`;
    }

    this.setRuntimeStatus({
      phase,
      label: phase === 'needs_approval'
        ? 'Approval required'
        : phase === 'blocked'
          ? 'Blocked'
          : phase === 'failed'
            ? 'Failed'
            : phase === 'complete'
              ? 'Complete'
              : actionLabel,
      hint,
      actionName,
    });
  }

  /**
   * @param {unknown} error
   */
  humanizeError(error) {
    const fallback =
      'xv7-core is currently resetting or loading heavy model weights. Wait a moment and retry your request.';

    if (error && typeof error === 'object' && error.name === 'AbortError') {
      return 'The request timed out or stayed pending too long. The UI recovered so you can retry.';
    }

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
    return setupVoiceOutputHelper({
      voiceState: this.voiceState,
      setSpeechOutputSupported: (v) => { this.speechOutputSupported = v; },
      setAvailableVoices: (v) => { this.availableVoices = v; },
      setVoiceAvailabilityNote: (v) => { this.voiceAvailabilityNote = v; },
      renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
      refreshVoiceVoicesFn: this.refreshVoiceVoices.bind(this),
    });
  }

  loadVoicePreferences() {
    return loadVoicePreferencesHelper(this.voiceSettings);
  }

  saveVoicePreferences() {
    return saveVoicePreferencesHelper(this.voiceSettings);
  }

  clampVoiceNumber(value, min, max, fallback) {
    return clampVoiceNumberHelper(value, min, max, fallback);
  }

  refreshVoiceVoices() {
    return refreshVoiceVoicesHelper({
      speechOutputSupported: this.speechOutputSupported,
      setAvailableVoices: (v) => { this.availableVoices = v; },
      renderVoiceSelectOptionsFn: this.renderVoiceSelectOptions.bind(this),
      applyPreferredVoiceIfNeededFn: this.applyPreferredVoiceIfNeeded.bind(this),
      renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
    });
  }

  renderVoiceSelectOptions() {
    return renderVoiceSelectOptionsHelper(this.els, this.voiceSettings, this.availableVoices);
  }

  applyPreferredVoiceIfNeeded() {
    return applyPreferredVoiceIfNeededHelper(this.voiceSettings, this.availableVoices, {
      setVoiceAvailabilityNote: (v) => { this.voiceAvailabilityNote = v; },
      saveVoicePreferencesFn: this.saveVoicePreferences.bind(this),
      syncVoiceSettingsToControlsFn: this.syncVoiceSettingsToControls.bind(this),
    });
  }

  choosePreferredVoice(voices) {
    return choosePreferredVoiceHelper(voices);
  }

  isFemaleLikeVoice(voice) {
    return isFemaleLikeVoiceHelper(voice);
  }

  syncVoiceSettingsToControls() {
    return syncVoiceSettingsToControlsHelper(this.els, this.voiceSettings, this.availableVoices);
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
    return avatarStateLabelHelper(stateName);
  }

  renderAvatarStateUI() {
    return renderAvatarStateUIHelper(this.els, this.avatarState);
  }

  renderAvatarDiagnostics() {
    return renderAvatarDiagnosticsHelper(
      this.els, this.avatarState, this.avatarClips,
      this.avatarMediaEnabled, this.avatarClipLoaded, this.avatarLastEvent,
    );
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
    return buildSpeechUtteranceHelper(text, this.voiceSettings, this.availableVoices);
  }

  startSpeechPlayback(text, options = {}) {
    return startSpeechPlaybackHelper(text, options, {
      speechOutputSupported: this.speechOutputSupported,
      voiceState: this.voiceState,
      buildSpeechUtteranceFn: this.buildSpeechUtterance.bind(this),
      setSpeaking: (v) => { this.speaking = v; },
      setSpeakingMessageId: (v) => { this.speakingMessageId = v; },
      setActiveUtterance: (v) => { this.activeUtterance = v; },
      getCurrentSpeaking: () => this.speaking,
      getCurrentSpeakingMessageId: () => this.speakingMessageId,
      dispatchVoiceEventFn: this.dispatchVoiceEvent.bind(this),
      setVoiceStatusFn: this.setVoiceStatus.bind(this),
      renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
      updateReadAloudButtonsFn: this.updateReadAloudButtons.bind(this),
      showAlertFn: this.showAlert.bind(this),
    });
  }

  stopVoicePlayback() {
    return stopVoicePlaybackHelper({
      speechOutputSupported: this.speechOutputSupported,
      voiceState: this.voiceState,
      setSpeaking: (v) => { this.speaking = v; },
      setSpeakingMessageId: (v) => { this.speakingMessageId = v; },
      setActiveUtterance: (v) => { this.activeUtterance = v; },
      setVoiceStatusFn: this.setVoiceStatus.bind(this),
      dispatchVoiceEventFn: this.dispatchVoiceEvent.bind(this),
      renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
      updateReadAloudButtonsFn: this.updateReadAloudButtons.bind(this),
    });
  }

  async playVoiceSample() {
    return playVoiceSampleHelper({
      startSpeechPlaybackFn: this.startSpeechPlayback.bind(this),
      voiceSettings: this.voiceSettings,
      setVoiceStatusFn: this.setVoiceStatus.bind(this),
    });
  }

  mergeTranscript(existingValue, transcript) {
    return mergeTranscriptHelper(existingValue, transcript);
  }

  setVoiceStatus(message) {
    return setVoiceStatusHelper(this.els, message);
  }

  renderVoiceDiagnostics() {
    return renderVoiceDiagnosticsHelper(
      this.els, this.voiceState, this.voiceSettings,
      this.availableVoices, this.voiceAvailabilityNote,
      {
        syncVoiceSettingsToControlsFn: this.syncVoiceSettingsToControls.bind(this),
        renderAvatarDiagnosticsFn: this.renderAvatarDiagnostics.bind(this),
      },
    );
  }

  dispatchVoiceEvent(name, detail = {}) {
    return dispatchVoiceEventHelper(name, detail);
  }

  renderReadAloudButton(button, messageId) {
    return renderReadAloudButtonHelper(
      button, messageId, this.speaking, this.speakingMessageId, this.speechOutputSupported,
    );
  }

  updateReadAloudButtons() {
    return updateReadAloudButtonsHelper(
      this.els, this.speaking, this.speakingMessageId, this.speechOutputSupported,
    );
  }

  async toggleReadAloud(article) {
    return toggleReadAloudHelper(article, {
      speechOutputSupported: this.speechOutputSupported,
      speaking: this.speaking,
      speakingMessageId: this.speakingMessageId,
      stopVoicePlaybackFn: this.stopVoicePlayback.bind(this),
      startSpeechPlaybackFn: this.startSpeechPlayback.bind(this),
      showAlertFn: this.showAlert.bind(this),
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
    await copyToClipboardText(text);
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
    return nowIsoHelper();
  }

  inferAssistantTimestamp(metadata) {
    return inferAssistantTimestampHelper(metadata, this.nowIso.bind(this));
  }

  /**
   * @param {string} path
   * @param {RequestInit} init
   */
  async fetchJson(path, init, timeoutMs = 15 * 60 * 1000, externalSignal = undefined) {
    return fetchJsonWithBase(this.apiBase, path, init, timeoutMs, externalSignal);
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
    applyStatusToneHelper(el, rawValue);
  }

  appendReceiptField(container, label, value) {
    appendReceiptFieldHelper(container, label, value, this.receiptField.bind(this));
  }

  operatorChipLabel(actionName, status) {
    return operatorChipLabelHelper(actionName, status);
  }

  summarizeContextReceipt(value) {
    return summarizeContextReceiptHelper(value, this.extractReceiptId.bind(this));
  }

  contextLayerChipLabel(layerOrLabel) {
    return contextLayerChipLabelHelper(layerOrLabel);
  }

  parseLayeredContextFromCompact(value) {
    return parseLayeredContextFromCompactHelper(value, this.contextLayerChipLabel.bind(this));
  }

  extractReceiptId(value) {
    return extractReceiptIdHelper(value);
  }

  resolveAssistantVisibleText(metadata, content) {
    return resolveAssistantVisibleTextHelper({
      metadata,
      content,
      stripReasoningTokens: this.stripReasoningTokens.bind(this),
      sanitizeVisibleAssistantTextFn: this.sanitizeVisibleAssistantText.bind(this),
      looksLikeStructuredPayloadFn: this.looksLikeStructuredPayload.bind(this),
    });
  }

  sanitizeVisibleAssistantText(text) {
    return sanitizeVisibleAssistantTextHelper(text);
  }

  looksLikeStructuredPayload(text) {
    return looksLikeStructuredPayloadHelper(text);
  }

  receiptField(value) {
    return receiptFieldHelper(value);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  // Global entrypoint for future module extension (streaming, avatars, sockets).
  if (!window.__XV7_DISABLE_AUTO_INIT) {
    window.__XV7_UI_INSTANCE = new Xv7UI();
  }
});

export { Xv7UI };
