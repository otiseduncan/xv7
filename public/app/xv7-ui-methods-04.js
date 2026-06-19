export function installXv7UiMethods04(Xv7UI, deps) {
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
    syncBrainLibraryFiltersFromUi() {
      this.brainRecordsFilters.layer = String(this.els.brainLibraryLayerFilter?.value || 'all');
      this.brainRecordsFilters.status = String(this.els.brainLibraryStatusFilter?.value || 'active');
      this.brainRecordsFilters.relevance = String(this.els.brainLibraryRelevanceFilter?.value || 'all');
      this.brainRecordsFilters.source = String(this.els.brainLibrarySourceFilter?.value || 'all');
      this.brainRecordsFilters.search = String(this.els.brainLibrarySearch?.value || '').trim().toLowerCase();
      this.brainRecordsFilters.showArchived = Boolean(this.els.brainLibraryShowArchived?.checked);
      this.brainRecordsFilters.showRawJson = Boolean(this.els.brainLibraryShowRawJson?.checked);
    },

    pendingLearnedCount() {
      return this.brainRecordCounts.review;
    },

    isPendingLearnedRecord(record) {
      const tags = new Set((Array.isArray(record?.tags) ? record.tags : []).map((tag) => String(tag).toLowerCase()));
      const status = String(record?.status_label || record?.status || '').toLowerCase();
      return status === 'pending' && (tags.has('learned-rule') || tags.has('otis-learning'));
    },

    normalizeRecordSource(record) {
      return String(record?.source || '').toLowerCase() === 'runtime_override' ? 'runtime' : 'seed';
    },

    recordStatusLabel(record) {
      const status = String(record?.status_label || record?.status || '').toLowerCase();
      const tags = new Set((Array.isArray(record?.tags) ? record.tags : []).map((tag) => String(tag).toLowerCase()));
      if (status === 'active') return 'ACTIVE';
      if (status === 'pending' || status === 'pending_review') return 'PENDING';
      if (status === 'disabled' || (status === 'archived' && tags.has('deactivated'))) return 'DISABLED';
      if (status === 'archived') return 'ARCHIVED';
      return String(status || 'ARCHIVED').toUpperCase();
    },

    recordRelevanceLabel(record) {
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || 'current').toLowerCase();
      if (relevance === 'needs_review') return 'NEEDS REVIEW';
      return relevance.replace('_', ' ').toUpperCase();
    },

    sourceStatusLabel(record) {
      return this.normalizeRecordSource(record) === 'runtime' ? 'RUNTIME OVERRIDE' : 'SEED';
    },

    sourceRuntime(record) {
      return this.normalizeRecordSource(record) === 'runtime';
    },

    primaryHygieneRecommendation(record) {
      const recs = Array.isArray(record?.hygiene_recommendations) ? record.hygiene_recommendations : [];
      if (!recs.length) return null;
      const split = recs.find((item) => String(item?.type || '') === 'split_record');
      if (split) return split;
      return recs[0];
    },

    isReviewCandidate(record) {
      return isReviewCandidateHelper(record);
    },

    isHistoryCandidate(record) {
      return isHistoryCandidateHelper(record);
    },

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
    },

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
    },

    isBrainRecordsStale() {
      if (!this.brainRecordsLastRefreshAt) return true;
      return (Date.now() - this.brainRecordsLastRefreshAt) > this.brainRecordsStaleMs;
    },

    historyViewRecords() {
      return this.brainRecords.filter((record) => this.isHistoryCandidate(record));
    },

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
    },

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
    },

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
    },

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
    },

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
    },

    makeBrainRecordAction(label, onClick) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'xv7-control-button brain-record-action';
      button.textContent = label;
      button.disabled = this.brainRecordBusy;
      button.addEventListener('click', onClick);
      return button;
    },

    isRecordCurrent(record) {
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
      return relevance === 'current';
    },

    isRecordHistorical(record) {
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
      return relevance === 'historical' || relevance === 'superseded' || relevance === 'expired';
    },

    isRecordDisabled(record) {
      const status = String(record?.status_label || record?.status || '').toLowerCase();
      return status === 'disabled' || status === 'archived';
    },

    isRecordReviewActionable(record) {
      const status = String(record?.status_label || record?.status || '').toLowerCase();
      const relevance = String(record?.effective_relevance_state || record?.relevance_state || '').toLowerCase();
      return status === 'pending' || status === 'pending_review' || relevance === 'needs_review';
    },

    shouldShowSplitAction(record) {
      const recommendation = this.primaryHygieneRecommendation(record);
      if (String(recommendation?.type || '') === 'split_record') return true;
      const flags = new Set((Array.isArray(record?.hygiene_flags) ? record.hygiene_flags : []).map((item) => String(item).toLowerCase()));
      return flags.has('mixed_historical_and_current') || flags.has('mixed_historical_and_operational');
    },

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
    },

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
    },

    closeBrainRecordEditor() {
      this.brainRecordEditorRecord = null;
      this.brainRecordEditorId = null;
      if (this.els.brainRecordEditor) this.els.brainRecordEditor.classList.add('hidden');
    },

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
    },

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
    },

  });
}
