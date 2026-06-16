export function nowIso() {
  return new Date().toISOString();
}

export function inferAssistantTimestamp(metadata, nowIsoFn = nowIso) {
  const receipts = Array.isArray(metadata?.operator_receipts) ? metadata.operator_receipts : [];
  const latest = receipts[receipts.length - 1];
  if (latest && typeof latest.completed_at === 'string') {
    return latest.completed_at;
  }
  return nowIsoFn();
}

export function operatorRuntimeStatusLabel(status) {
  if (status === 'passed' || status === 'success' || status === 'succeeded') return 'Complete';
  if (status === 'needs_approval') return 'Approval required';
  if (status === 'failed' || status === 'error') return 'Failed';
  if (status === 'denied' || status === 'blocked') return 'Blocked';
  if (status === 'running' || status === 'pending') return 'Running';
  return 'Complete';
}

export function operatorRuntimeStatusTone(status) {
  if (status === 'passed' || status === 'success' || status === 'succeeded') return 'success';
  if (status === 'needs_approval' || status === 'pending') return 'pending';
  if (status === 'failed' || status === 'error') return 'failed';
  if (status === 'denied' || status === 'blocked') return 'blocked';
  if (status === 'running') return 'running';
  return 'success';
}

export function operatorChipLabel(actionName, status) {
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

export function extractReceiptId(value) {
  const text = String(value || '').trim();
  if (!text) return '-';
  const match = text.match(/(XV7-[A-Z-]+-\d+)/);
  return match ? match[1] : text;
}

export function summarizeContextReceipt(value, extractReceiptIdFn = extractReceiptId) {
  const text = String(value || '').trim();
  if (!text) return '-';

  const id = extractReceiptIdFn(text);
  if (id !== text) {
    if (text.toLowerCase().includes('verified status')) {
      return `Verified Status ${id}`;
    }
    return id;
  }

  return text.length > 72 ? `${text.slice(0, 69)}...` : text;
}

export function contextLayerChipLabel(layerOrLabel) {
  const normalized = String(layerOrLabel || '').toLowerCase();
  if (normalized.includes('system_prompt') || normalized.includes('system prompt')) return 'System';
  if (normalized.includes('active_focus') || normalized.includes('active focus')) return 'Focus';
  if (normalized.includes('verified_status') || normalized.includes('verified status')) return 'Verified';
  if (normalized.includes('knowledge')) return 'Knowledge';
  if (normalized.includes('memory')) return 'Memory';
  return 'Context';
}

export function parseLayeredContextFromCompact(value, contextLayerChipLabelFn = contextLayerChipLabel) {
  const text = String(value || '');
  const out = [];
  const pattern = /(System Prompt|Active Focus|Knowledge|Memory|Verified Status)\s+(XV7-[A-Z-]+-\d+)/g;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    out.push({
      label: contextLayerChipLabelFn(match[1]),
      recordId: match[2],
    });
  }
  return out;
}

export function sanitizeVisibleAssistantText(text) {
  const raw = String(text || '').trim();
  if (!raw) return '';

  const blockedPatterns = [
    /\binternal reasoning\b/i,
    /\bhidden reasoning\b/i,
    /\bprivate reasoning\b/i,
    /\bchain(?:-|\s+)of(?:-|\s+)thought\b/i,
  ];

  const filtered = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !blockedPatterns.some((pattern) => pattern.test(line)))
    .join('\n')
    .trim();

  return filtered;
}

export function looksLikeStructuredPayload(text) {
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

export function receiptField(value) {
  if (typeof value !== 'string') return '-';
  const cleaned = value.trim();
  return cleaned || '-';
}

export function resolveAssistantVisibleText({
  metadata,
  content,
  stripReasoningTokens,
  sanitizeVisibleAssistantTextFn = sanitizeVisibleAssistantText,
  looksLikeStructuredPayloadFn = looksLikeStructuredPayload,
}) {
  const meta = metadata && typeof metadata === 'object' ? metadata : {};
  const fromMeta = typeof meta.visible_text === 'string' ? meta.visible_text.trim() : '';
  const safeMeta = sanitizeVisibleAssistantTextFn(fromMeta);
  if (safeMeta) return safeMeta;
  if (fromMeta) return 'Response withheld for safety.';

  const stripped = stripReasoningTokens(String(content || '')).trim();
  if (!stripped) return 'No assistant content returned.';

  if (looksLikeStructuredPayloadFn(stripped)) {
    return 'Structured response received. Expand receipts for details.';
  }

  const safeContent = sanitizeVisibleAssistantTextFn(stripped);
  return safeContent || 'Response withheld for safety.';
}

export function safeOperatorActionName(value) {
  const text = String(value || '').trim();
  const lowered = text.toLowerCase();
  if (!text || lowered === 'unknown' || lowered === 'operator_action' || lowered === 'operator_action unknown') return '';
  return text;
}

export function operatorActionDisplayLabel(actionName) {
  const labels = {
    repo_status: 'Repo status',
    operator_status_report: 'Check the repo',
    operator_validation_report: 'Run validation',
    operator_commit_report: 'Commit and push',
    operator_repair_report: 'Repair check',
    operator_patch_report: 'Patch approval check',
  };
  return labels[actionName] || actionName.replace(/_/g, ' ');
}

export function hasMeaningfulValue(value, options = {}) {
  const { allowFalse = false } = options;

  if (value === null || value === undefined) return false;
  if (typeof value === 'boolean') return value === true || allowFalse;
  if (typeof value === 'number') return Number.isFinite(value);

  if (typeof value === 'string') {
    const text = value.trim();
    if (!text) return false;
    const lowered = text.toLowerCase();
    if (lowered === '-' || lowered === 'none' || lowered === 'n/a' || lowered === 'null' || lowered === 'undefined') {
      return false;
    }
    return true;
  }

  if (Array.isArray(value)) {
    return value.some((item) => hasMeaningfulValue(item, options));
  }

  if (typeof value === 'object') {
    return Object.values(value).some((item) => hasMeaningfulValue(item, options));
  }

  return false;
}

export function formatMeaningfulValue(value, options = {}, hasMeaningfulValueFn = hasMeaningfulValue) {
  const { allowFalse = false } = options;
  if (!hasMeaningfulValueFn(value, { allowFalse })) return null;

  if (Array.isArray(value)) {
    const items = value
      .map((item) => formatMeaningfulValue(item, { allowFalse }, hasMeaningfulValueFn))
      .filter((item) => typeof item === 'string' && item.trim());
    return items.length ? items.join(', ') : null;
  }

  if (typeof value === 'object') {
    const pairs = Object.entries(value)
      .map(([key, nested]) => {
        const rendered = formatMeaningfulValue(nested, { allowFalse }, hasMeaningfulValueFn);
        return rendered ? `${key}=${rendered}` : '';
      })
      .filter(Boolean);
    return pairs.length ? pairs.join('; ') : null;
  }

  return String(value).trim();
}

export function safeTraceText(
  value,
  {
    hasMeaningfulValueFn = hasMeaningfulValue,
    formatMeaningfulValueFn = formatMeaningfulValue,
  } = {},
) {
  if (!hasMeaningfulValueFn(value, { allowFalse: true })) return '';
  const text = formatMeaningfulValueFn(value, { allowFalse: true }, hasMeaningfulValueFn);
  if (!text) return '';
  const lowered = text.trim().toLowerCase();
  if (lowered === 'unknown' || lowered === 'operator_action unknown' || lowered === 'operator_action') return '';
  return text.trim();
}

export function safeTraceResponseType(meta, policy, hints = {}, safeTraceTextFn = safeTraceText) {
  const explicit = safeTraceTextFn(
    policy.response_type || meta.response_type || policy.response_mode || meta.response_mode || '',
  );
  if (explicit) return explicit;
  if (hints.actionName) return 'operator';
  if (hints.artifactType) return 'artifact';
  if (hints.validationSummary) return 'validation';
  return '';
}

export function safeTraceSourceLayers(meta, contextReceipt, contextLayerChipLabelFn = contextLayerChipLabel) {
  const contextEntries = Array.isArray(contextReceipt.context_receipts) ? contextReceipt.context_receipts : [];
  const layers = contextEntries
    .map((entry) => contextLayerChipLabelFn(entry?.layer || entry?.receipt_label || ''))
    .filter((label) => label && label !== 'Context');

  if (meta.context_includes_focus === true && !layers.includes('Focus')) layers.push('Focus');
  return [...new Set(layers)].join(', ');
}

export function safeTraceArtifactType(
  meta,
  policy,
  {
    getMessageSiteBundle,
    collectArtifactPatchProposal,
    collectCodeArtifacts,
    safeTraceTextFn = safeTraceText,
  },
) {
  const siteBundle = getMessageSiteBundle(meta);
  if (siteBundle) return 'site bundle';
  const patchProposal = collectArtifactPatchProposal(meta);
  if (patchProposal) return 'artifact patch';
  const artifacts = collectCodeArtifacts(meta);
  if (artifacts.length) {
    const first = artifacts[0] || {};
    return safeTraceTextFn(first.type || first.artifact_type || first.language || 'code artifact');
  }
  return safeTraceTextFn(policy.artifact_generation || meta.artifact_type || '');
}

export function safeTraceSafetyState(result, receipt, meta) {
  const commitPushState = result?.commit_push_state && typeof result.commit_push_state === 'object'
    ? result.commit_push_state
    : {};
  const safety = receipt?.safety && typeof receipt.safety === 'object' ? receipt.safety : {};

  if (
    commitPushState.requires_separate_approval === true
    || result?.status === 'needs_approval'
    || meta.requires_confirmation === true
  ) {
    return 'approval required';
  }
  if (safety.allowed === false) return 'blocked';
  if (safety.read_only === true || result?.read_only === true || receipt?.read_only === true) return 'read-only';
  if (safety.allowed === true) return 'approved';
  return '';
}

export function safeTraceValidationSummary(
  result,
  meta,
  policy,
  {
    collectArtifactPatchProposal,
    safeTraceTextFn = safeTraceText,
  },
) {
  const validationSummary = result?.validation_summary && typeof result.validation_summary === 'object'
    ? result.validation_summary
    : {};
  const patchProposal = collectArtifactPatchProposal(meta);
  const validationStatus = safeTraceTextFn(
    validationSummary.status
      || validationSummary.result
      || patchProposal?.validation?.status
      || policy.validation
      || policy.artifact_validation
      || '',
  );
  const passed = validationSummary.passed ?? validationSummary.pass_count ?? validationSummary.passed_count;
  const failed = validationSummary.failed ?? validationSummary.fail_count ?? validationSummary.failed_count;
  if (validationStatus && (passed !== undefined || failed !== undefined)) {
    return `${validationStatus}; pass=${passed ?? 0}; fail=${failed ?? 0}`;
  }
  if (validationStatus) return validationStatus;
  const commands = Array.isArray(result?.validation_commands_run)
    ? result.validation_commands_run.filter(Boolean)
    : [];
  if (commands.length) return `${commands.length} validation command${commands.length === 1 ? '' : 's'} reported`;
  return '';
}

export function createResponseDetailsSection(title) {
  const section = document.createElement('section');
  section.className = 'response-details-section';

  const heading = document.createElement('p');
  heading.className = 'response-details-section-title';
  heading.textContent = title;

  section.append(heading);
  return section;
}

export function appendMeaningfulReceiptField(
  container,
  label,
  value,
  options = {},
  { formatMeaningfulValueFn, appendReceiptFieldFn },
) {
  const rendered = formatMeaningfulValueFn(value, options);
  if (!rendered) return false;
  appendReceiptFieldFn(container, label, rendered);
  return true;
}

export function getSafeTraceSummary(messageMetadata, deps) {
  const {
    getMessageOperatorResult,
    safeOperatorActionName,
    safeTraceText,
    safeTraceSourceLayers,
    safeTraceArtifactType,
    safeTraceSafetyState,
    safeTraceValidationSummary,
    safeTraceResponseType,
    operatorActionDisplayLabel,
  } = deps;

  const meta = messageMetadata && typeof messageMetadata === 'object' ? messageMetadata : {};
  const result = getMessageOperatorResult(meta);
  const receipts = Array.isArray(meta.operator_receipts)
    ? meta.operator_receipts.filter((receipt) => receipt && typeof receipt === 'object')
    : [];
  const latestReceipt = receipts.length ? receipts[receipts.length - 1] : {};
  const policy = meta.policy_provenance && typeof meta.policy_provenance === 'object' ? meta.policy_provenance : {};
  const contextReceipt = meta.context_receipt && typeof meta.context_receipt === 'object' ? meta.context_receipt : {};

  const actionName = safeOperatorActionName(
    result?.action_name || latestReceipt.action_name || meta.operator_action || '',
  );
  const status = safeTraceText(
    result?.status || latestReceipt.status || meta.status || policy.status || '',
  );
  const sourceLayers = safeTraceSourceLayers(meta, contextReceipt);
  const artifactType = safeTraceArtifactType(meta, policy);
  const safetyState = safeTraceSafetyState(result, latestReceipt, meta);
  const validationSummary = safeTraceValidationSummary(result, meta, policy);
  const responseType = safeTraceResponseType(meta, policy, {
    actionName,
    artifactType,
    validationSummary,
  });

  const rows = [
    ['response type', responseType],
    ['action taken', actionName ? operatorActionDisplayLabel(actionName) : ''],
    ['status', status],
    ['source layers', sourceLayers],
    ['artifact type', artifactType],
    ['safety/approval', safetyState],
    ['validation summary', validationSummary],
  ];

  const meaningfulTraceSignals = [actionName, status, sourceLayers, safetyState, validationSummary]
    .some((value) => safeTraceText(value));
  if (!meaningfulTraceSignals) return [];

  return rows
    .map(([label, value]) => [label, safeTraceText(value)])
    .filter(([, value]) => value);
}

export function appendSafeTraceSummarySection(container, messageMetadata, deps) {
  const { getSafeTraceSummaryFn, createResponseDetailsSectionFn, appendReceiptFieldFn } = deps;
  const trace = getSafeTraceSummaryFn(messageMetadata);
  if (!trace.length) return false;

  const section = createResponseDetailsSectionFn('Trace summary');
  const body = document.createElement('div');
  body.className = 'receipt-detail-grid response-details-grid safe-trace-grid';

  trace.forEach(([label, value]) => {
    appendReceiptFieldFn(body, label, value);
  });

  section.append(body);
  container.append(section);
  return true;
}

export function appendResponseDetailsDisclosure(article, messageMetadata, deps) {
  const {
    appendSafeTraceSummarySectionFn,
    appendOperatorReceiptsSection,
    appendOperatorResultSection,
    appendWhyThisAnswerSection,
    prepareResponseRevealSection,
  } = deps;

  const details = document.createElement('details');
  details.className = 'response-details-disclosure';

  const summary = document.createElement('summary');
  summary.className = 'response-details-summary';
  summary.textContent = 'Details';

  const body = document.createElement('div');
  body.className = 'response-details-body';

  let hasAnySection = false;
  hasAnySection = appendSafeTraceSummarySectionFn(body, messageMetadata) || hasAnySection;
  hasAnySection = appendOperatorReceiptsSection(body, messageMetadata) || hasAnySection;
  hasAnySection = appendOperatorResultSection(body, messageMetadata) || hasAnySection;
  hasAnySection = appendWhyThisAnswerSection(body, messageMetadata) || hasAnySection;

  if (!hasAnySection) return;

  details.append(summary, body);
  prepareResponseRevealSection(details, 'details');
  article.append(details);
}

export function appendOperatorReceiptsSection(container, messageMetadata, deps) {
  const {
    createResponseDetailsSectionFn,
    appendMeaningfulReceiptFieldFn,
    safeOperatorActionName,
    safeTraceText,
  } = deps;
  const meta = messageMetadata && typeof messageMetadata === 'object' ? messageMetadata : {};
  const receipts = Array.isArray(meta.operator_receipts) ? meta.operator_receipts : [];
  const validReceipts = receipts.filter((receipt) => receipt && typeof receipt === 'object');
  if (!validReceipts.length) return false;

  const section = createResponseDetailsSectionFn('Operator status');

  validReceipts.forEach((receipt, index) => {
    const grid = document.createElement('div');
    grid.className = 'receipt-detail-grid response-details-grid';
    let hasRows = false;
    hasRows = appendMeaningfulReceiptFieldFn(
      grid,
      'receipt',
      receipt.receipt_label || `operator receipt ${index + 1}`,
    ) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(grid, 'action_id', receipt.action_id) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(
      grid,
      'action_name',
      safeOperatorActionName(receipt.action_name),
    ) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(grid, 'status', safeTraceText(receipt.status)) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(
      grid,
      'read_only',
      receipt.read_only,
      { allowFalse: true },
    ) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(grid, 'target', receipt.target) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(grid, 'summary', receipt.summary) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(grid, 'limitation', receipt.limitation) || hasRows;
    hasRows = appendMeaningfulReceiptFieldFn(
      grid,
      'timestamp',
      receipt.completed_at || receipt.started_at,
    ) || hasRows;
    if (hasRows) {
      section.append(grid);
    }
  });

  if (!section.querySelector('.response-details-grid')) return false;
  container.append(section);
  return true;
}

export function appendOperatorResultSection(container, messageMetadata, deps) {
  const { getMessageOperatorResult, createResponseDetailsSectionFn, appendMeaningfulReceiptFieldFn } = deps;
  const result = getMessageOperatorResult(messageMetadata);
  if (!result) return false;

  const actionName = String(result.action_name || '').trim();
  const status = String(result.status || '').trim();
  const changedFiles = Array.isArray(result.changed_files) ? result.changed_files : [];
  const validationCommands = Array.isArray(result.validation_commands_run)
    ? result.validation_commands_run
    : [];
  const firstFailure = String(result.first_failure || '').trim();
  const safetyNotes = Array.isArray(result.safety_notes) ? result.safety_notes : [];
  const localOnlyWarning = Array.isArray(result.local_only_files_warning)
    ? result.local_only_files_warning
    : [];
  const commitPushState = result.commit_push_state && typeof result.commit_push_state === 'object'
    ? result.commit_push_state
    : {};

  const commitCreated = commitPushState.commit_created === true;
  const pushPerformed = commitPushState.push_performed === true;
  const separateApproval = commitPushState.requires_separate_approval === true;

  const sectionTitle = [actionName, status].filter(Boolean).join(' • ');
  const section = createResponseDetailsSectionFn(
    sectionTitle ? `Operator result (${sectionTitle})` : 'Operator result',
  );

  const body = document.createElement('div');
  body.className = 'receipt-detail-grid response-details-grid';
  let hasRows = false;

  hasRows = appendMeaningfulReceiptFieldFn(body, 'changed_files', changedFiles) || hasRows;
  hasRows = appendMeaningfulReceiptFieldFn(body, 'validation_commands', validationCommands) || hasRows;

  if (firstFailure) {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'first_failure', firstFailure) || hasRows;
  }

  if (status === 'needs_approval') {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'approval', 'required') || hasRows;
  } else if (status === 'needs_patch') {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'patch', 'required') || hasRows;
  } else if (status === 'blocked') {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'blocked', 'true') || hasRows;
  }

  if (safetyNotes.length) {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'safety', safetyNotes) || hasRows;
  }

  if (localOnlyWarning.length) {
    hasRows = appendMeaningfulReceiptFieldFn(body, 'local_only', localOnlyWarning) || hasRows;
  }

  const commitState = `commit_created=${commitCreated ? 'true' : 'false'}; push_performed=${pushPerformed ? 'true' : 'false'}${separateApproval ? '; separate_approval=true' : ''}`;
  hasRows = appendMeaningfulReceiptFieldFn(body, 'commit_push', commitState) || hasRows;

  if (!hasRows) return false;

  section.append(body);
  container.append(section);
  return true;
}

export function appendWhyThisAnswerSection(container, messageMetadata, deps) {
  const {
    contextLayerChipLabelFn,
    collectArtifactPatchProposal,
    boolText,
    createResponseDetailsSectionFn,
    appendMeaningfulReceiptFieldFn,
  } = deps;

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
    .map((entry) => contextLayerChipLabelFn(entry?.layer || entry?.receipt_label || ''))
    .filter((label) => label && label !== 'Context');

  const modelUseReceipt = meta.model_use_receipt && typeof meta.model_use_receipt === 'object'
    ? meta.model_use_receipt
    : {};

  const artifactGeneration = policy.artifact_generation || '-';
  const artifactIsFallback = artifactGeneration === 'deterministic_prompt_template_fallback';
  const resolvedModelUsed = policy.model_used || modelUseReceipt.model_tag || meta.model_used || '';
  const resolvedFallbackReason =
    policy.fallback_reason || meta.fallback_reason || policy.brain_answer_source || '-';
  const revisionMode = policy.revision_mode || meta.revision_mode || '-';
  const revisionNumber = policy.revision_number || meta.revision_number || '-';
  const sourceArtifact =
    policy.source_artifact || policy.source_artifact_key || meta.source_artifact || '-';
  const patchProposal = collectArtifactPatchProposal(meta);
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
  const promptFidelityColors = Array.isArray(promptFidelity.requested_colors)
    && promptFidelity.requested_colors.length
    ? promptFidelity.requested_colors.join(', ')
    : '-';
  const promptFidelityRepairAttempted = boolText(promptFidelity.repair_attempted);

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
    ['patch_applied', boolText(patchProposal?.applied ?? policy.applied)],
    ['model_used', resolvedModelUsed],
    ['artifact_validation', policy.artifact_validation || '-'],
    ['fallback_used', (meta.fallback_used === true || artifactIsFallback) ? 'true' : ''],
    ['fallback_reason', resolvedFallbackReason],
    ['learned_record_id', meta.learned_record_id || '-'],
    ['learning_layer', meta.learning_layer || '-'],
    ['learning_status', meta.learning_status || '-'],
    ['requires_confirmation', boolText(meta.requires_confirmation)],
    ['protected_boundary', boolText(meta.protected_boundary)],
    ['selected_layers', selectedLayers.length ? selectedLayers.join(', ') : '-'],
    ['source_record_ids', sourceRecordIds.length ? sourceRecordIds.join(', ') : '-'],
    ['active_focus_id', policy.active_focus_id || meta.active_focus_id || '-'],
    ['focus_applied', boolText(policy.focus_applied ?? meta.focus_applied)],
    ['context_includes_focus', (meta.context_includes_focus === true || selectedLayers.includes('Focus')) ? 'true' : ''],
  ];

  const section = createResponseDetailsSectionFn('Why this answer');

  const body = document.createElement('div');
  body.className = 'receipt-detail-grid response-details-grid';
  let hasRows = false;
  fields.forEach(([label, value]) => {
    hasRows = appendMeaningfulReceiptFieldFn(body, String(label), value) || hasRows;
  });

  if (!hasRows) return false;

  section.append(body);
  container.append(section);
  return true;
}

export function renderOperatorActivity(history, deps) {
  const { operatorActivityList, operatorSummaryChip, appendReceiptFieldFn } = deps;
  const list = operatorActivityList;
  const chip = operatorSummaryChip;
  const items = Array.isArray(history) ? history.slice().reverse() : [];

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
    appendReceiptFieldFn(detailGrid, 'action_id', entry.action_id);
    appendReceiptFieldFn(detailGrid, 'status', status);
    appendReceiptFieldFn(detailGrid, 'read_only', entry.read_only);
    appendReceiptFieldFn(detailGrid, 'target', entry.target);
    appendReceiptFieldFn(detailGrid, 'summary', entry.summary);
    appendReceiptFieldFn(detailGrid, 'limitation', entry.limitation);
    appendReceiptFieldFn(detailGrid, 'timestamp', entry.completed_at || entry.started_at);
    details.append(detailsSummary, detailGrid);

    li.append(summary, meta, detail, details);
    list.append(li);
  });
}

export function renderRetrievalJournal(response, deps) {
  const { retrievalJournal, stripReasoningTokensFn } = deps;
  const journal = retrievalJournal;
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
    const content = stripReasoningTokensFn(String(entry.content || '')).slice(0, 280);
    li.textContent = `[${role}] ${content || 'No content'}`;
    journal.append(li);
  });
}

export function renderBrainRecordsViews(deps) {
  const {
    brainRecordsViews,
    brainRecordCounts,
    brainRecordsView,
    brainLibraryControls,
    brainReviewToolbar,
    brainRecordsApplyCleanupButton,
    approvedCleanupRecommendations,
    syncBrainLibraryFiltersFromUi,
  } = deps;
  const tabMount = brainRecordsViews;
  if (!tabMount) return;
  const counts = brainRecordCounts;
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
    const isActive = button.dataset.view === brainRecordsView;
    button.classList.toggle('is-active', isActive);
    button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });

  if (brainLibraryControls) {
    brainLibraryControls.classList.toggle('hidden', brainRecordsView !== 'library');
  }

  if (brainReviewToolbar) {
    const approvedCount = Object.keys(approvedCleanupRecommendations).length;
    const showToolbar = brainRecordsView === 'review' && approvedCount > 0;
    brainReviewToolbar.classList.toggle('hidden', !showToolbar);
  }

  if (brainRecordsApplyCleanupButton) {
    const approvedCount = Object.keys(approvedCleanupRecommendations).length;
    brainRecordsApplyCleanupButton.textContent = `Apply approved cleanup (${approvedCount})`;
  }

  syncBrainLibraryFiltersFromUi();
}

export function updateStatusFromHistory(history, deps) {
  const { renderStatusStrip, statusSummary, refreshStatusTimestamp } = deps;
  const items = Array.isArray(history) ? history : [];
  if (!items.length) {
    renderStatusStrip();
    return;
  }

  const latest = items[items.length - 1];
  if (latest && typeof latest === 'object') {
    const status = typeof latest.status === 'string' ? latest.status : 'unknown';
    const actionName = typeof latest.action_name === 'string' ? latest.action_name : 'operator_action';
    statusSummary.lastAction = `${actionName} ${status}`;
    refreshStatusTimestamp();
    renderStatusStrip();
  }
}

export function isReviewCandidate(record) {
  const status = String(record?.status_label || record?.status || '').toLowerCase();
  const storedRelevance = String(record?.relevance_state || '').toLowerCase();
  const effectiveRelevance = String(record?.effective_relevance_state || storedRelevance || '').toLowerCase();
  const recs = Array.isArray(record?.hygiene_recommendations) ? record.hygiene_recommendations : [];
  const flags = new Set((Array.isArray(record?.hygiene_flags) ? record.hygiene_flags : [])
    .map((item) => String(item).toLowerCase()));

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

export function isHistoryCandidate(record) {
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
