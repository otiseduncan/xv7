import { vi } from 'vitest';

function buildDom() {
  document.body.innerHTML = `
    <select id="personaSelect"></select>
    <p id="personaHint"></p>
    <span id="sessionIdValue"></span>
    <span id="memoryCountValue"></span>
    <span id="hardwareLoadValue"></span>
    <div id="hardwareLoadBar"></div>
    <section id="alertBox" class="hidden"></section>
    <ul id="retrievalJournal"></ul>
    <button id="copyChatButton"></button>
    <div id="copyToast" class="hidden"></div>
    <div id="chatTimeline"></div>
    <button id="operatorModeToggle"></button>
    <div id="operatorModeBanner" class="hidden"></div>
    <div id="operatorConfirmArea" class="hidden"></div>
    <textarea id="promptInput"></textarea>
    <div id="slashMenu" class="hidden"></div>
    <button id="micButton"></button>
    <button id="sendButton"></button>
    <section id="avatarCard" class="avatar-card">
      <button id="avatarToggleButton" aria-expanded="true"></button>
      <div id="avatarCardBody"></div>
      <div id="avatarShell"></div>
      <video id="avatarVideo"></video>
      <div id="avatarFallback"></div>
      <p id="avatarStateText"></p>
      <p id="avatarVoiceLabel"></p>
    </section>
    <div id="voiceStatus"></div>
    <p id="voiceSettingsStatus"></p>
    <select id="voiceSelect"></select>
    <input id="voiceVolume" type="range" />
    <input id="sidebarVoiceVolume" type="range" />
    <span id="sidebarVoiceVolumeValue"></span>
    <input id="voiceRate" type="range" />
    <input id="voicePitch" type="range" />
    <input id="voiceMute" type="checkbox" />
    <button id="sidebarVoiceMuteButton"></button>
    <span id="sidebarVoiceMuteIconOn"></span>
    <span id="sidebarVoiceMuteIconOff"></span>
    <span id="sidebarVoiceMuteLabel"></span>
    <span id="sidebarVoiceMuteState"></span>
    <button id="voiceTestButton"></button>
    <button id="voiceStopButton"></button>
    <span id="avatarDiagState"></span>
    <span id="avatarDiagClip"></span>
    <span id="avatarDiagLoaded"></span>
    <span id="avatarDiagVisible"></span>
    <span id="avatarDiagEvent"></span>
    <span id="voiceDiagInput"></span>
    <span id="voiceDiagMicState"></span>
    <span id="voiceDiagOutput"></span>
    <span id="voiceDiagSpeaking"></span>
    <span id="voiceDiagVoiceCount"></span>
    <span id="voiceDiagSelected"></span>
    <span id="voiceDiagVolume"></span>
    <span id="voiceDiagRate"></span>
    <span id="voiceDiagPitch"></span>
    <span id="modelActiveProfile"></span>
    <span id="modelProfileSource"></span>
    <span id="modelOllamaReachable"></span>
    <span id="modelEffectiveChat"></span>
    <select id="modelProfileSelect"></select>
    <button id="modelApplyButton"></button>
    <button id="modelClearButton"></button>
    <span id="modelResolvedChat"></span>
    <span id="modelResolvedReasoning"></span>
    <span id="modelResolvedCode"></span>
    <span id="modelResolvedEmbedding"></span>
    <span id="modelAvailabilityChat"></span>
    <span id="modelAvailabilityReasoning"></span>
    <span id="modelAvailabilityCode"></span>
    <span id="modelAvailabilityEmbedding"></span>
    <p id="modelPanelStatus"></p>
    <span id="chatReceiptProfile"></span>
    <span id="chatReceiptSource"></span>
    <span id="chatReceiptRole"></span>
    <span id="chatReceiptModelTag"></span>
    <span id="chatReceiptSelectionSource"></span>
    <span id="chatReceiptRequestId"></span>
    <ul id="operatorActivityList"></ul>
    <span id="statusCoreApi"></span>
    <span id="statusRuntimeHealth"></span>
    <span id="statusActiveProfile"></span>
    <span id="statusOperatorMode"></span>
    <span id="statusMemory"></span>
    <span id="statusLastAction"></span>
    <span id="statusLastChecked"></span>
    <span id="statusCoreApiChip"></span>
    <span id="statusRuntimeHealthChip"></span>
    <span id="statusActiveProfileChip"></span>
    <span id="statusOperatorModeChip"></span>
    <span id="statusLastCheckedChip"></span>
    <div id="operatorSummaryChip" class="hidden"></div>
    <aside id="diagnosticsDrawer"></aside>
    <div id="diagnosticsBackdrop" class="hidden"></div>
    <button id="diagnosticsToggleButton"></button>
    <button id="diagnosticsCloseButton"></button>
    <p id="brainRecordsStatus"></p>
    <div id="brainRecordsViews">
      <button data-view="now"></button>
      <button data-view="review"></button>
      <button data-view="history"></button>
      <button data-view="library"></button>
    </div>
    <p id="brainNowCounts"></p>
    <div id="brainReviewToolbar" class="hidden">
      <button id="brainRecordsApplyCleanupButton"></button>
    </div>
    <p id="brainNowFocus"></p>
    <p id="brainNowSelectedRecords"></p>
    <p id="brainNowAnswerMeta"></p>
    <div id="brainLibraryControls" class="hidden"></div>
    <select id="brainLibraryLayerFilter">
      <option value="all">all</option>
      <option value="active_focus">active_focus</option>
      <option value="memory">memory</option>
      <option value="knowledge">knowledge</option>
      <option value="verified_status">verified_status</option>
      <option value="system_prompt">system_prompt</option>
    </select>
    <select id="brainLibraryStatusFilter">
      <option value="active">active</option>
      <option value="pending">pending</option>
      <option value="disabled">disabled</option>
      <option value="archived">archived</option>
      <option value="all">all</option>
    </select>
    <select id="brainLibraryRelevanceFilter">
      <option value="all">all</option>
      <option value="current">current</option>
      <option value="needs_review">needs_review</option>
      <option value="historical">historical</option>
      <option value="superseded">superseded</option>
      <option value="expired">expired</option>
    </select>
    <select id="brainLibrarySourceFilter">
      <option value="all">all</option>
      <option value="runtime">runtime</option>
      <option value="seed">seed</option>
    </select>
    <input id="brainLibrarySearch" />
    <input id="brainLibraryShowArchived" type="checkbox" />
    <input id="brainLibraryShowRawJson" type="checkbox" />
    <ul id="brainRecordsList"></ul>
    <div id="brainRecordEditor" class="hidden"></div>
    <span id="brainRecordEditorId"></span>
    <select id="brainRecordEditorLayer"></select>
    <input id="brainRecordEditorTitle" />
    <textarea id="brainRecordEditorBody"></textarea>
    <input id="brainRecordEditorTags" />
    <select id="brainRecordEditorStatus"></select>
    <button id="brainRecordEditorSaveButton"></button>
    <button id="brainRecordEditorCancelButton"></button>
    <textarea id="brainRecordEditorRaw"></textarea>
  `;
}

export { buildDom };
