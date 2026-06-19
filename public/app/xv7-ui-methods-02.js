export function installXv7UiMethods02(Xv7UI, deps) {
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
    },

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
    },

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
    },

    async sendQuickPrompt(text) {
      const value = String(text || '').trim();
      if (!value) return;
      this.els.promptInput.value = value;
      await this.sendMessage();
    },

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
    },

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
    },

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
    },

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
     */,

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
    },

    responseRevealReducedMotion() {
      return Boolean(
        typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      );
    },

    prepareResponseRevealSection(element, kind = 'body') {
      if (!element) return null;
      element.classList.add('response-reveal', `response-reveal--${kind}`);
      if (this.responseRevealReducedMotion()) {
        this.markResponseSectionVisible(element);
      }
      return element;
    },

    markResponseSectionVisible(section) {
      if (!section) return null;
      section.classList.add('is-visible');
      return section;
    },

    markResponseChildrenForReveal(article, selector, kind = 'body') {
      if (!article || !selector) return [];
      return [...article.querySelectorAll(selector)].map((element) =>
        this.prepareResponseRevealSection(element, kind),
      );
    },

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
    },

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
    },

    collectSiteBundleFiles(bundlePayload) {
      return collectSiteBundleFilesHelper(bundlePayload);
    },

    getMessageSiteBundle(message) {
      return getMessageSiteBundleHelper(message, {
        shouldSuppressSiteBundleForOperatorPayloadFn: this.shouldSuppressSiteBundleForOperatorPayload.bind(this),
        inferLanguageFromFilenameFn: this.inferLanguageFromFilename.bind(this),
      });
    },

  });
}
