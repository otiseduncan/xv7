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
import { installXv7UiMethods01 } from './app/xv7-ui-methods-01.js';
import { installXv7UiMethods02 } from './app/xv7-ui-methods-02.js';
import { installXv7UiMethods03 } from './app/xv7-ui-methods-03.js';
import { installXv7UiMethods04 } from './app/xv7-ui-methods-04.js';
import { installXv7UiMethods05 } from './app/xv7-ui-methods-05.js';
import { installXv7UiMethods06 } from './app/xv7-ui-methods-06.js';

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





















































































































































































































}


const XV7_UI_METHOD_DEPS = {
  appendArtifactHighlightedLineHelper,
  appendArtifactTokenHelper,
  appendCodeArtifactsHelper,
  appendCssArtifactLineHelper,
  appendCssTokenizedLineHelper,
  appendHtmlArtifactLineHelper,
  appendHtmlTagTokensHelper,
  appendMeaningfulReceiptFieldHelper,
  appendOperatorReceiptsSectionHelper,
  appendOperatorResultSectionHelper,
  appendPlainArtifactLineHelper,
  appendPythonArtifactLineHelper,
  appendReceiptFieldHelper,
  appendResponseDetailsDisclosureHelper,
  appendSafeTraceSummarySectionHelper,
  appendSiteBundleCardHelper,
  appendWhyThisAnswerSectionHelper,
  applyPreferredVoiceIfNeededHelper,
  applyStatusToneHelper,
  avatarStateLabelHelper,
  buildSiteBundlePreviewSrcdocHelper,
  buildSpeechUtteranceHelper,
  choosePreferredVoiceHelper,
  clampVoiceNumberHelper,
  classifyPromptRuntime,
  collectSiteBundleFilesHelper,
  contextLayerChipLabelHelper,
  copyCodeArtifactHelper,
  copyToClipboardText,
  createArtifactHighlightStateHelper,
  createCodeArtifactCardHelper,
  createResponseDetailsSectionHelper,
  createRuntimeStatusModel,
  deriveSiteBundleFileLabelHelper,
  dispatchVoiceEventHelper,
  downloadCodeArtifactHelper,
  extractReceiptIdHelper,
  fetchJsonWithBase,
  findSiteBundleFileHelper,
  formatMeaningfulValueHelper,
  getMessageSiteBundleHelper,
  getSafeTraceSummaryHelper,
  getSiteBundleFileOptionsHelper,
  hasMeaningfulValueHelper,
  inferAssistantTimestampHelper,
  inferLanguageFromFilenameHelper,
  isArtifactPreviewableHelper,
  isFemaleLikeVoiceHelper,
  isHistoryCandidateHelper,
  isLocalBundleAssetReferenceHelper,
  isReviewCandidateHelper,
  isSiteBundlePreviewableFileHelper,
  languageLabelHelper,
  loadVoicePreferencesHelper,
  looksLikeStructuredPayloadHelper,
  mergeTranscriptHelper,
  normalizeArtifactLanguageHelper,
  normalizeBundlePathHelper,
  normalizeSiteBundleHelper,
  normalizeSpeechTextHelper,
  nowIsoHelper,
  operatorActionDisplayLabelHelper,
  operatorChipLabelHelper,
  operatorRuntimeStatusLabelHelper,
  operatorRuntimeStatusToneHelper,
  parseLayeredContextFromCompactHelper,
  phaseFromOperatorStatus,
  playVoiceSampleHelper,
  receiptFieldHelper,
  refreshVoiceVoicesHelper,
  renderArtifactCodeRowsHelper,
  renderAvatarDiagnosticsHelper,
  renderAvatarStateUIHelper,
  renderBrainRecordsViewsHelper,
  renderOperatorActivityHelper,
  renderReadAloudButtonHelper,
  renderRetrievalJournalHelper,
  renderVoiceDiagnosticsHelper,
  renderVoiceSelectOptionsHelper,
  resolveAssistantVisibleTextHelper,
  resolveAvatarMediaEnabledHelper,
  resolveBundleAssetPathHelper,
  runtimeActionLabel,
  safeOperatorActionNameHelper,
  safeTraceArtifactTypeHelper,
  safeTraceResponseTypeHelper,
  safeTraceSafetyStateHelper,
  safeTraceSourceLayersHelper,
  safeTraceTextHelper,
  safeTraceValidationSummaryHelper,
  sanitizeArtifactDownloadNameHelper,
  sanitizeVisibleAssistantTextHelper,
  saveVoicePreferencesHelper,
  setVoiceStatusHelper,
  setupVoiceOutputHelper,
  shouldSuppressSiteBundleForOperatorPayloadHelper,
  siteBundlePreviewAllowsScriptsHelper,
  splitAssetReferenceHelper,
  startSpeechPlaybackHelper,
  stopVoicePlaybackHelper,
  stripReasoningTokensHelper,
  summarizeContextReceiptHelper,
  switchArtifactTabHelper,
  syncVoiceSettingsToControlsHelper,
  toggleArtifactPreviewHelper,
  toggleReadAloudHelper,
  updateReadAloudButtonsHelper,
  updateRuntimeStatusElement,
  updateStatusFromHistoryHelper,
};

installXv7UiMethods01(Xv7UI, XV7_UI_METHOD_DEPS);
installXv7UiMethods02(Xv7UI, XV7_UI_METHOD_DEPS);
installXv7UiMethods03(Xv7UI, XV7_UI_METHOD_DEPS);
installXv7UiMethods04(Xv7UI, XV7_UI_METHOD_DEPS);
installXv7UiMethods05(Xv7UI, XV7_UI_METHOD_DEPS);
installXv7UiMethods06(Xv7UI, XV7_UI_METHOD_DEPS);
window.addEventListener('DOMContentLoaded', () => {
  // Global entrypoint for future module extension (streaming, avatars, sockets).
  if (!window.__XV7_DISABLE_AUTO_INIT) {
    window.__XV7_UI_INSTANCE = new Xv7UI();
  }
});

export { Xv7UI };
