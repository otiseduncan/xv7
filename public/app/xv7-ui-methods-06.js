export function installXv7UiMethods06(Xv7UI, deps) {
  const {
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
  } = deps;
  Object.assign(Xv7UI.prototype, {
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
    },

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
    },

    setupVoiceOutput() {
      return setupVoiceOutputHelper({
        voiceState: this.voiceState,
        setSpeechOutputSupported: (v) => { this.speechOutputSupported = v; },
        setAvailableVoices: (v) => { this.availableVoices = v; },
        setVoiceAvailabilityNote: (v) => { this.voiceAvailabilityNote = v; },
        renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
        refreshVoiceVoicesFn: this.refreshVoiceVoices.bind(this),
      });
    },

    loadVoicePreferences() {
      return loadVoicePreferencesHelper(this.voiceSettings);
    },

    saveVoicePreferences() {
      return saveVoicePreferencesHelper(this.voiceSettings);
    },

    clampVoiceNumber(value, min, max, fallback) {
      return clampVoiceNumberHelper(value, min, max, fallback);
    },

    refreshVoiceVoices() {
      return refreshVoiceVoicesHelper({
        speechOutputSupported: this.speechOutputSupported,
        setAvailableVoices: (v) => { this.availableVoices = v; },
        renderVoiceSelectOptionsFn: this.renderVoiceSelectOptions.bind(this),
        applyPreferredVoiceIfNeededFn: this.applyPreferredVoiceIfNeeded.bind(this),
        renderVoiceDiagnosticsFn: this.renderVoiceDiagnostics.bind(this),
      });
    },

    renderVoiceSelectOptions() {
      return renderVoiceSelectOptionsHelper(this.els, this.voiceSettings, this.availableVoices);
    },

    applyPreferredVoiceIfNeeded() {
      return applyPreferredVoiceIfNeededHelper(this.voiceSettings, this.availableVoices, {
        setVoiceAvailabilityNote: (v) => { this.voiceAvailabilityNote = v; },
        saveVoicePreferencesFn: this.saveVoicePreferences.bind(this),
        syncVoiceSettingsToControlsFn: this.syncVoiceSettingsToControls.bind(this),
      });
    },

    choosePreferredVoice(voices) {
      return choosePreferredVoiceHelper(voices);
    },

    isFemaleLikeVoice(voice) {
      return isFemaleLikeVoiceHelper(voice);
    },

    syncVoiceSettingsToControls() {
      return syncVoiceSettingsToControlsHelper(this.els, this.voiceSettings, this.availableVoices);
    },

    initializeAvatar() {
      if (!this.els.avatarVideo) return;
      this.applyAvatarClipForState(this.avatarState);
      this.renderAvatarStateUI();
      this.renderAvatarDiagnostics();
    },

    scheduleAvatarReset(nextState = 'idle', delayMs = 1400) {
      if (this.avatarResetTimer) {
        window.clearTimeout(this.avatarResetTimer);
      }
      this.avatarResetTimer = window.setTimeout(() => {
        this.setAvatarState(nextState, 'state-timeout');
        this.avatarResetTimer = null;
      }, delayMs);
    },

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
    },

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
    },

    avatarStateLabel(stateName) {
      return avatarStateLabelHelper(stateName);
    },

    renderAvatarStateUI() {
      return renderAvatarStateUIHelper(this.els, this.avatarState);
    },

    renderAvatarDiagnostics() {
      return renderAvatarDiagnosticsHelper(
        this.els, this.avatarState, this.avatarClips,
        this.avatarMediaEnabled, this.avatarClipLoaded, this.avatarLastEvent,
      );
    },

    setVoiceVolume(value) {
      this.voiceSettings.volume = this.clampVoiceNumber(value, 0, 1, 1);
      this.saveVoicePreferences();
      this.renderVoiceDiagnostics();
    },

    setVoiceMuted(muted) {
      this.voiceSettings.muted = Boolean(muted);
      this.saveVoicePreferences();
      this.renderVoiceDiagnostics();
    },

    buildSpeechUtterance(text) {
      return buildSpeechUtteranceHelper(text, this.voiceSettings, this.availableVoices);
    },

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
    },

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
    },

    async playVoiceSample() {
      return playVoiceSampleHelper({
        startSpeechPlaybackFn: this.startSpeechPlayback.bind(this),
        voiceSettings: this.voiceSettings,
        setVoiceStatusFn: this.setVoiceStatus.bind(this),
      });
    },

    mergeTranscript(existingValue, transcript) {
      return mergeTranscriptHelper(existingValue, transcript);
    },

    setVoiceStatus(message) {
      return setVoiceStatusHelper(this.els, message);
    },

    renderVoiceDiagnostics() {
      return renderVoiceDiagnosticsHelper(
        this.els, this.voiceState, this.voiceSettings,
        this.availableVoices, this.voiceAvailabilityNote,
        {
          syncVoiceSettingsToControlsFn: this.syncVoiceSettingsToControls.bind(this),
          renderAvatarDiagnosticsFn: this.renderAvatarDiagnostics.bind(this),
        },
      );
    },

    dispatchVoiceEvent(name, detail = {}) {
      return dispatchVoiceEventHelper(name, detail);
    },

    renderReadAloudButton(button, messageId) {
      return renderReadAloudButtonHelper(
        button, messageId, this.speaking, this.speakingMessageId, this.speechOutputSupported,
      );
    },

    updateReadAloudButtons() {
      return updateReadAloudButtonsHelper(
        this.els, this.speaking, this.speakingMessageId, this.speechOutputSupported,
      );
    },

    async toggleReadAloud(article) {
      return toggleReadAloudHelper(article, {
        speechOutputSupported: this.speechOutputSupported,
        speaking: this.speaking,
        speakingMessageId: this.speakingMessageId,
        stopVoicePlaybackFn: this.stopVoicePlayback.bind(this),
        startSpeechPlaybackFn: this.startSpeechPlayback.bind(this),
        showAlertFn: this.showAlert.bind(this),
      });
    },

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
    },

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
    },

    async copyToClipboard(text) {
      await copyToClipboardText(text);
    },

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
    },

    nowIso() {
      return nowIsoHelper();
    },

    inferAssistantTimestamp(metadata) {
      return inferAssistantTimestampHelper(metadata, this.nowIso.bind(this));
    }
    
    /**
     * @param {string} path
     * @param {RequestInit} init
     */,

    async fetchJson(path, init, timeoutMs = 15 * 60 * 1000, externalSignal = undefined) {
      return fetchJsonWithBase(this.apiBase, path, init, timeoutMs, externalSignal);
    },

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
    },

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
    },

    refreshStatusTimestamp() {
      const date = new Date();
      this.statusSummary.lastChecked = `last checked ${date.toLocaleTimeString()}`;
    },

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
    },

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
    },

    applyStatusTone(el, rawValue) {
      applyStatusToneHelper(el, rawValue);
    },

    appendReceiptField(container, label, value) {
      appendReceiptFieldHelper(container, label, value, this.receiptField.bind(this));
    },

    operatorChipLabel(actionName, status) {
      return operatorChipLabelHelper(actionName, status);
    },

    summarizeContextReceipt(value) {
      return summarizeContextReceiptHelper(value, this.extractReceiptId.bind(this));
    },

    contextLayerChipLabel(layerOrLabel) {
      return contextLayerChipLabelHelper(layerOrLabel);
    },

    parseLayeredContextFromCompact(value) {
      return parseLayeredContextFromCompactHelper(value, this.contextLayerChipLabel.bind(this));
    },

    extractReceiptId(value) {
      return extractReceiptIdHelper(value);
    },

    resolveAssistantVisibleText(metadata, content) {
      return resolveAssistantVisibleTextHelper({
        metadata,
        content,
        stripReasoningTokens: this.stripReasoningTokens.bind(this),
        sanitizeVisibleAssistantTextFn: this.sanitizeVisibleAssistantText.bind(this),
        looksLikeStructuredPayloadFn: this.looksLikeStructuredPayload.bind(this),
      });
    },

    sanitizeVisibleAssistantText(text) {
      return sanitizeVisibleAssistantTextHelper(text);
    },

    looksLikeStructuredPayload(text) {
      return looksLikeStructuredPayloadHelper(text);
    },

    receiptField(value) {
      return receiptFieldHelper(value);
    },

  });
}
