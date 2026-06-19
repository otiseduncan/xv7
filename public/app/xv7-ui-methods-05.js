export function installXv7UiMethods05(Xv7UI, deps) {
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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
    },

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
     */,

    extractReasoning(text) {
      const matches = [...text.matchAll(/<\|think\|>([\s\S]*?)<\/\|think\|>/g)];
      if (!matches.length) return null;
      return matches.map((m) => m[1]).join('\n\n');
    },

    collectArtifactPatchProposal(message) {
      const source = message && typeof message === 'object' ? message : {};
      const metadata = source.metadata && typeof source.metadata === 'object' ? source.metadata : source;
      const proposal = metadata.artifact_patch_proposal;
      return this.normalizeArtifactPatchProposal(proposal);
    },

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
    },

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
    },

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
    },

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
    },

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
    },

    codeArtifactKey(artifact) {
      return [
        artifact.filename,
        artifact.language,
        artifact.content,
        artifact.applied ? '1' : '0',
        artifact.previewable ? '1' : '0',
      ].join('\u001f');
    },

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
     */,

    stripReasoningTokens(text) {
      return stripReasoningTokensHelper(text);
    },

    normalizeSpeechText(text) {
      return normalizeSpeechTextHelper(text);
    },

    updateSessionTelemetry() {
      this.els.sessionIdValue.textContent = this.currentSessionId || 'not initialized';
      this.els.memoryCountValue.textContent = String(this.memoryLogCount);
      this.statusSummary.memory = this.currentSessionId ? 'available' : 'idle';
      this.renderStatusStrip();
    }
    
    /**
     * @param {string} label
     * @param {number} percent
     */,

    setHardwareLoad(label, percent) {
      this.els.hardwareLoadValue.textContent = `${label} (${percent}%)`;
      this.els.hardwareLoadBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    }
    
    /**
     * @param {boolean} locked
     */,

    setSendBusy(locked) {
      this.isSending = locked;
      this.els.promptInput.disabled = locked;
      this.els.sendButton.textContent = locked ? 'Stop' : 'Send';
      this.els.sendButton.classList.toggle('is-stop', locked);
      this.els.sendButton.classList.toggle('is-busy', locked);
      this.els.sendButton.setAttribute('aria-label', locked ? 'Stop active request' : 'Send message');
      this.els.sendButton.title = locked ? 'Stop active request' : 'Send message';
      this.syncComposerSendAvailability();
    },

    syncComposerSendAvailability() {
      this.els.sendButton.disabled = false;
    },

    lockInput(locked) {
      this.setSendBusy(locked);
    },

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
    },

    setRuntimeStatus(model) {
      this.runtimeStatusModel = createRuntimeStatusModel(model || {});
      this.renderPendingAssistantStatus(this.runtimeStatusModel);
      return this.runtimeStatusModel;
    },

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
    },

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
    },

    consumePendingAssistantCard() {
      const article = this.pendingAssistantArticle && this.pendingAssistantArticle.isConnected
        ? this.pendingAssistantArticle
        : null;
      this.pendingAssistantArticle = null;
      this.pendingAssistantStatusElement = null;
      return article;
    },

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
    },

    removePendingAssistantCard() {
      const article = this.consumePendingAssistantCard();
      article?.remove();
    },

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
     */,

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
     */,

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
    },

  });
}
