export function installXv7UiMethods03(Xv7UI, deps) {
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
    shouldSuppressSiteBundleForOperatorPayload(metadata) {
      return shouldSuppressSiteBundleForOperatorPayloadHelper(metadata, {
        getMessageOperatorResultFn: this.getMessageOperatorResult.bind(this),
      });
    },

    normalizeSiteBundle(bundlePayload) {
      return normalizeSiteBundleHelper(bundlePayload, {
        inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
      });
    },

    deriveSiteBundleFileLabel(path) {
      return deriveSiteBundleFileLabelHelper(path);
    },

    getSiteBundleFileOptions(bundle) {
      return getSiteBundleFileOptionsHelper(bundle, {
        deriveSiteBundleFileLabelFn: this.deriveSiteBundleFileLabel.bind(this),
      });
    },

    findSiteBundleFile(bundle, path) {
      return findSiteBundleFileHelper(bundle, path);
    },

    isSiteBundlePreviewableFile(file) {
      return isSiteBundlePreviewableFileHelper(file);
    },

    normalizeBundlePath(path) {
      return normalizeBundlePathHelper(path);
    },

    splitAssetReference(reference) {
      return splitAssetReferenceHelper(reference);
    },

    isLocalBundleAssetReference(reference) {
      return isLocalBundleAssetReferenceHelper(reference);
    },

    resolveBundleAssetPath(baseFilePath, reference) {
      return resolveBundleAssetPathHelper(baseFilePath, reference, {
        isLocalBundleAssetReferenceFn: this.isLocalBundleAssetReference.bind(this),
        splitAssetReferenceFn: this.splitAssetReference.bind(this),
        normalizeBundlePathFn: this.normalizeBundlePath.bind(this),
      });
    },

    siteBundlePreviewAllowsScripts() {
      return siteBundlePreviewAllowsScriptsHelper();
    },

    buildSiteBundlePreviewSrcdoc(bundle, selectedFile) {
      return buildSiteBundlePreviewSrcdocHelper(bundle, selectedFile, {
        isSiteBundlePreviewableFileFn: this.isSiteBundlePreviewableFile.bind(this),
        normalizeBundlePathFn: this.normalizeBundlePath.bind(this),
        resolveBundleAssetPathFn: this.resolveBundleAssetPath.bind(this),
        siteBundlePreviewAllowsScriptsFn: this.siteBundlePreviewAllowsScripts.bind(this),
      });
    },

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
    },

    appendCodeArtifacts(article, messageMetadata) {
      return appendCodeArtifactsHelper(article, messageMetadata, {
        collectCodeArtifactsFn: this.collectCodeArtifacts.bind(this),
        createCodeArtifactCardFn: this.createCodeArtifactCard.bind(this),
        prepareResponseRevealSectionFn: this.prepareResponseRevealSection.bind(this),
        appendRenderErrorNoticeFn: this.appendRenderErrorNotice.bind(this),
        showAlertFn: this.showAlert.bind(this),
      });
    },

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
    },

    renderArtifactCodeRows(content, language) {
      return renderArtifactCodeRowsHelper(content, language, {
        createArtifactHighlightStateFn: this.createArtifactHighlightState.bind(this),
        appendArtifactHighlightedLineFn: this.appendArtifactHighlightedLine.bind(this),
      });
    },

    createArtifactHighlightState(language) {
      return createArtifactHighlightStateHelper(language, {
        normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
      });
    },

    appendArtifactHighlightedLine(container, line, language, state) {
      return appendArtifactHighlightedLineHelper(container, line, language, state, {
        normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
        appendHtmlArtifactLineFn: this.appendHtmlArtifactLine.bind(this),
        appendCssArtifactLineFn: this.appendCssArtifactLine.bind(this),
        appendPythonArtifactLineFn: this.appendPythonArtifactLine.bind(this),
        appendPlainArtifactLineFn: this.appendPlainArtifactLine.bind(this),
      });
    },

    appendPlainArtifactLine(container, line) {
      return appendPlainArtifactLineHelper(container, line);
    },

    appendHtmlArtifactLine(container, line, state) {
      return appendHtmlArtifactLineHelper(container, line, state, {
        appendCssArtifactLineFn: this.appendCssArtifactLine.bind(this),
        appendArtifactTokenFn: this.appendArtifactToken.bind(this),
        appendHtmlTagTokensFn: this.appendHtmlTagTokens.bind(this),
      });
    },

    appendHtmlTagTokens(container, rawTag, state) {
      return appendHtmlTagTokensHelper(container, rawTag, state, {
        appendArtifactTokenFn: this.appendArtifactToken.bind(this),
      });
    },

    appendCssArtifactLine(container, line, state) {
      return appendCssArtifactLineHelper(container, line, state, {
        appendCssValueTokensFn: (target, text) => this.appendCssTokenizedLine(target, text),
        appendArtifactTokenFn: this.appendArtifactToken.bind(this),
        appendCssTokenizedLineFn: this.appendCssTokenizedLine.bind(this),
      });
    },

    appendCssTokenizedLine(container, text) {
      return appendCssTokenizedLineHelper(container, text, {
        appendArtifactTokenFn: this.appendArtifactToken.bind(this),
      });
    },

    appendPythonArtifactLine(container, line) {
      return appendPythonArtifactLineHelper(container, line, {
        appendArtifactTokenFn: this.appendArtifactToken.bind(this),
      });
    },

    appendArtifactToken(container, className, text) {
      return appendArtifactTokenHelper(container, className, text);
    },

    switchArtifactTab(card, tabName) {
      return switchArtifactTabHelper(card, tabName);
    },

    normalizeArtifactLanguage(language) {
      return normalizeArtifactLanguageHelper(language);
    },

    inferLanguageFromFilename(filename) {
      return inferLanguageFromFilenameHelper(filename);
    },

    languageLabel(language) {
      return languageLabelHelper(language, {
        normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
      });
    },

    isArtifactPreviewable(artifact, filename, language) {
      return isArtifactPreviewableHelper(artifact, filename, language, {
        normalizeArtifactLanguageFn: this.normalizeArtifactLanguage.bind(this),
        inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
      });
    },

    async copyCodeArtifact(card, artifact, button) {
      return copyCodeArtifactHelper(card, artifact, button, {
        copyToClipboardFn: this.copyToClipboard.bind(this),
        artifactCopyState: this.artifactCopyState,
      });
    },

    downloadCodeArtifact(artifact) {
      return downloadCodeArtifactHelper(artifact, {
        sanitizeArtifactDownloadNameFn: this.sanitizeArtifactDownloadName.bind(this),
      });
    },

    sanitizeArtifactDownloadName(filename) {
      return sanitizeArtifactDownloadNameHelper(filename);
    },

    toggleArtifactPreview(card, artifact, button) {
      return toggleArtifactPreviewHelper(card, artifact, button, {
        switchArtifactTabFn: this.switchArtifactTab.bind(this),
      });
    },

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
    },

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
    },

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
    },

    summarizeOperatorList(value, max = 3) {
      const items = Array.isArray(value)
        ? value.map((item) => String(item || '').trim()).filter(Boolean)
        : [];
      if (!items.length) return 'none';
      if (items.length <= max) return items.join(', ');
      return `${items.slice(0, max).join(', ')} (+${items.length - max} more)`;
    },

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
    },

    operatorRuntimeBoolLabel(value, trueLabel, falseLabel) {
      if (value === true) return trueLabel;
      if (value === false) return falseLabel;
      const text = String(value ?? '').trim().toLowerCase();
      if (!text) return '';
      if (['true', 'yes', 'clean', 'synced', 'in_sync'].includes(text)) return trueLabel;
      if (['false', 'no', 'dirty', 'not_clean', 'not_synced', 'out_of_sync', 'ahead', 'behind', 'diverged'].includes(text)) return falseLabel;
      return String(value).trim();
    },

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
    },

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
    },

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
    },

    operatorRuntimeStatusLabel(status) {
      return operatorRuntimeStatusLabelHelper(status);
    },

    operatorRuntimeStatusTone(status) {
      return operatorRuntimeStatusToneHelper(status);
    },

    appendResponseDetailsDisclosure(article, messageMetadata) {
      appendResponseDetailsDisclosureHelper(article, messageMetadata, {
        appendSafeTraceSummarySectionFn: this.appendSafeTraceSummarySection.bind(this),
        appendOperatorReceiptsSection: this.appendOperatorReceiptsSection.bind(this),
        appendOperatorResultSection: this.appendOperatorResultSection.bind(this),
        appendWhyThisAnswerSection: this.appendWhyThisAnswerSection.bind(this),
        prepareResponseRevealSection: this.prepareResponseRevealSection.bind(this),
      });
    },

    appendSafeTraceSummarySection(container, messageMetadata) {
      return appendSafeTraceSummarySectionHelper(container, messageMetadata, {
        getSafeTraceSummaryFn: this.getSafeTraceSummary.bind(this),
        createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
        appendReceiptFieldFn: this.appendReceiptField.bind(this),
      });
    },

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
    },

    safeTraceResponseType(meta, policy, hints = {}) {
      return safeTraceResponseTypeHelper(meta, policy, hints, this.safeTraceText.bind(this));
    },

    safeTraceSourceLayers(meta, contextReceipt) {
      return safeTraceSourceLayersHelper(meta, contextReceipt, this.contextLayerChipLabel.bind(this));
    },

    safeTraceArtifactType(meta, policy) {
      return safeTraceArtifactTypeHelper(meta, policy, {
        getMessageSiteBundle: this.getMessageSiteBundle.bind(this),
        collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
        collectCodeArtifacts: this.collectCodeArtifacts.bind(this),
        safeTraceTextFn: this.safeTraceText.bind(this),
      });
    },

    safeTraceSafetyState(result, receipt, meta) {
      return safeTraceSafetyStateHelper(result, receipt, meta);
    },

    safeTraceValidationSummary(result, meta, policy) {
      return safeTraceValidationSummaryHelper(result, meta, policy, {
        collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
        safeTraceTextFn: this.safeTraceText.bind(this),
      });
    },

    safeOperatorActionName(value) {
      return safeOperatorActionNameHelper(value);
    },

    operatorActionDisplayLabel(actionName) {
      return operatorActionDisplayLabelHelper(actionName);
    },

    safeTraceText(value) {
      return safeTraceTextHelper(value, {
        hasMeaningfulValueFn: this.hasMeaningfulValue.bind(this),
        formatMeaningfulValueFn: this.formatMeaningfulValue.bind(this),
      });
    },

    createResponseDetailsSection(title) {
      return createResponseDetailsSectionHelper(title);
    },

    hasMeaningfulValue(value, options = {}) {
      return hasMeaningfulValueHelper(value, options);
    },

    formatMeaningfulValue(value, options = {}) {
      return formatMeaningfulValueHelper(value, options, this.hasMeaningfulValue.bind(this));
    },

    appendMeaningfulReceiptField(container, label, value, options = {}) {
      return appendMeaningfulReceiptFieldHelper(container, label, value, options, {
        formatMeaningfulValueFn: this.formatMeaningfulValue.bind(this),
        appendReceiptFieldFn: this.appendReceiptField.bind(this),
      });
    },

    appendOperatorReceiptsSection(container, messageMetadata) {
      return appendOperatorReceiptsSectionHelper(container, messageMetadata, {
        createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
        appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
        safeOperatorActionName: this.safeOperatorActionName.bind(this),
        safeTraceText: this.safeTraceText.bind(this),
      });
    },

    appendOperatorResultSection(container, messageMetadata) {
      return appendOperatorResultSectionHelper(container, messageMetadata, {
        getMessageOperatorResult: this.getMessageOperatorResult.bind(this),
        createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
        appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
      });
    },

    appendWhyThisAnswerSection(container, messageMetadata) {
      return appendWhyThisAnswerSectionHelper(container, messageMetadata, {
        contextLayerChipLabelFn: this.contextLayerChipLabel.bind(this),
        collectArtifactPatchProposal: this.collectArtifactPatchProposal.bind(this),
        boolText: this.boolText.bind(this),
        createResponseDetailsSectionFn: this.createResponseDetailsSection.bind(this),
        appendMeaningfulReceiptFieldFn: this.appendMeaningfulReceiptField.bind(this),
      });
    },

    boolText(value) {
      if (value === true) return 'true';
      if (value === false) return 'false';
      return '-';
    },

    renderOperatorActivity(history) {
      renderOperatorActivityHelper(history, {
        operatorActivityList: this.els.operatorActivityList,
        operatorSummaryChip: this.els.operatorSummaryChip,
        appendReceiptFieldFn: this.appendReceiptField.bind(this),
      });
    },

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
     */,

    renderRetrievalJournal(response) {
      renderRetrievalJournalHelper(response, {
        retrievalJournal: this.els.retrievalJournal,
        stripReasoningTokensFn: this.stripReasoningTokens.bind(this),
      });
    },

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
    },

  });
}
