export function installXv7UiMethods01(Xv7UI, deps) {
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
    resolveAvatarMediaEnabled() {
      return resolveAvatarMediaEnabledHelper();
    },

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
    },

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
    },

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
    },

    renderOperatorModeUi() {
      if (this.els.operatorModeToggle) {
        this.els.operatorModeToggle.setAttribute('aria-pressed', this.operatorModeActive ? 'true' : 'false');
        this.els.operatorModeToggle.textContent = this.operatorModeActive ? 'Operator Mode: ON' : 'Operator Mode: OFF';
        this.els.operatorModeToggle.classList.toggle('operator-mode-on', this.operatorModeActive);
      }
      if (this.els.operatorModeBanner) {
        this.els.operatorModeBanner.classList.toggle('hidden', !this.operatorModeActive);
      }
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

    asBoolLabel(value) {
      return value ? 'available' : 'unavailable';
    },

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
    },

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
     */,

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
    },

  });
}
