export function collectSiteBundleFiles(bundlePayload) {
  const bundle = bundlePayload && typeof bundlePayload === 'object' ? bundlePayload : {};
  if (Array.isArray(bundle.files)) return bundle.files;
  if (bundle.site_bundle && Array.isArray(bundle.site_bundle.files)) return bundle.site_bundle.files;
  return [];
}

export function getMessageSiteBundle(message, deps) {
  const { shouldSuppressSiteBundleForOperatorPayloadFn } = deps;
  const source = message && typeof message === 'object' ? message : null;
  if (!source) return null;

  const metadata = source.metadata && typeof source.metadata === 'object' ? source.metadata : source;
  if (shouldSuppressSiteBundleForOperatorPayloadFn(metadata)) return null;
  const candidates = [];

  if (source.site_bundle && typeof source.site_bundle === 'object') {
    candidates.push(source.site_bundle);
  }
  if (metadata.site_bundle && typeof metadata.site_bundle === 'object') {
    candidates.push(metadata.site_bundle);
  }

  for (const candidate of candidates) {
    const normalized = normalizeSiteBundle(candidate, deps);
    if (normalized) return normalized;
  }

  return null;
}

export function shouldSuppressSiteBundleForOperatorPayload(metadata, deps) {
  const { getMessageOperatorResultFn } = deps;
  const meta = metadata && typeof metadata === 'object' ? metadata : null;
  if (!meta) return false;

  const operatorResult = getMessageOperatorResultFn(meta);
  const receipts = Array.isArray(meta.operator_receipts) ? meta.operator_receipts : [];
  const hasOperatorPayload = Boolean(operatorResult) || receipts.length > 0;
  if (!hasOperatorPayload) return false;

  const actionName = String(
    operatorResult?.action_name
    || receipts[receipts.length - 1]?.action_name
    || '',
  ).trim().toLowerCase();

  if (!actionName) return true;
  return !actionName.startsWith('site_bundle');
}

export function normalizeSiteBundle(bundlePayload, deps) {
  const { inferLanguageFromFilenameFn } = deps;
  const bundle = bundlePayload && typeof bundlePayload === 'object' ? bundlePayload : null;
  if (!bundle) return null;

  const files = collectSiteBundleFiles(bundle)
    .filter((file) => file && typeof file === 'object')
    .map((file) => {
      const path = String(file.path || '').trim();
      const content = typeof file.content === 'string' ? file.content : '';
      const language = String(file.language || inferLanguageFromFilenameFn(path));
      return {
        ...file,
        path,
        content,
        language,
      };
    })
    .filter((file) => file.path && file.content);

  const hasBundleShape = String(bundle.artifact_type || '').trim() === 'site_bundle'
    || Array.isArray(bundle.files)
    || Boolean(bundle.site_bundle && Array.isArray(bundle.site_bundle.files))
    || Array.isArray(bundle.route_manifest);

  if (!hasBundleShape || !files.length) return null;

  const htmlFiles = files.filter((file) => /\.html?$/i.test(file.path));
  const entry = String(bundle.entry || htmlFiles[0]?.path || files[0]?.path || '').trim();
  const activeFile = String(bundle.active_file || entry || htmlFiles[0]?.path || files[0]?.path || '').trim();
  const previewEntrypoint = String(bundle.preview_entrypoint || entry || htmlFiles[0]?.path || files[0]?.path || '').trim();
  const previewFile = htmlFiles.find((file) => file.path === previewEntrypoint)
    || htmlFiles.find((file) => file.path === entry)
    || htmlFiles.find((file) => file.path === activeFile)
    || htmlFiles[0]
    || null;

  return {
    ...bundle,
    artifact_type: 'site_bundle',
    files,
    entry,
    active_file: activeFile,
    preview_entrypoint: previewFile?.path || previewEntrypoint || entry,
  };
}

export function deriveSiteBundleFileLabel(path) {
  const name = String(path || '').trim().split('/').pop() || 'file';
  if (/^index\.html?$/i.test(name)) return 'Home';
  return name.replace(/\.[a-z0-9]+$/i, '').replace(/[-_]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

export function getSiteBundleFileOptions(bundle) {
  const files = Array.isArray(bundle?.files) ? bundle.files : [];
  const htmlPaths = new Set(files.filter((file) => /\.html?$/i.test(file.path)).map((file) => file.path));
  const manifest = Array.isArray(bundle?.route_manifest) ? bundle.route_manifest : [];
  const manifestOptions = manifest
    .filter((entry) => entry && typeof entry === 'object')
    .map((entry) => {
      const path = String(entry.path || '').trim();
      if (!path || !htmlPaths.has(path)) return null;
      return {
        path,
        label: String(entry.label || deriveSiteBundleFileLabel(path)).trim() || deriveSiteBundleFileLabel(path),
        route: String(entry.route || '').trim(),
        isEntry: entry.is_entry === true,
      };
    })
    .filter(Boolean);

  if (manifestOptions.length) return manifestOptions;

  return files.map((file) => ({
    path: file.path,
    label: deriveSiteBundleFileLabel(file.path),
    route: /\.html?$/i.test(file.path) ? `/${file.path}` : '',
    isEntry: file.path === bundle?.entry,
  }));
}

export function findSiteBundleFile(bundle, path) {
  const files = Array.isArray(bundle?.files) ? bundle.files : [];
  return files.find((file) => file.path === path) || null;
}

export function isSiteBundlePreviewableFile(file) {
  return Boolean(file && typeof file === 'object' && /\.html?$/i.test(String(file.path || '')));
}

export function normalizeBundlePath(path) {
  const raw = String(path || '').trim().replace(/\\/g, '/');
  if (!raw) return '';

  const hasLeadingSlash = raw.startsWith('/');
  const parts = raw.split('/');
  const normalizedParts = [];
  parts.forEach((part) => {
    if (!part || part === '.') return;
    if (part === '..') {
      if (normalizedParts.length > 0) {
        normalizedParts.pop();
      }
      return;
    }
    normalizedParts.push(part);
  });

  const normalized = normalizedParts.join('/');
  return hasLeadingSlash ? `/${normalized}` : normalized;
}

export function splitAssetReference(reference) {
  const ref = String(reference || '').trim();
  if (!ref) {
    return { path: '', suffix: '' };
  }

  const hashIndex = ref.indexOf('#');
  const queryIndex = ref.indexOf('?');
  const breakpoints = [hashIndex, queryIndex].filter((index) => index >= 0);
  const splitIndex = breakpoints.length ? Math.min(...breakpoints) : -1;

  if (splitIndex < 0) {
    return { path: ref, suffix: '' };
  }
  return {
    path: ref.slice(0, splitIndex),
    suffix: ref.slice(splitIndex),
  };
}

export function isLocalBundleAssetReference(reference) {
  const ref = String(reference || '').trim();
  if (!ref || ref.startsWith('#') || ref.startsWith('//')) return false;
  return !/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(ref);
}

export function resolveBundleAssetPath(baseFilePath, reference) {
  if (!isLocalBundleAssetReference(reference)) return '';
  const { path: referencePath } = splitAssetReference(reference);
  const trimmedRef = String(referencePath || '').trim();
  if (!trimmedRef) return '';

  if (trimmedRef.startsWith('/')) {
    return normalizeBundlePath(trimmedRef.slice(1));
  }

  const normalizedBase = normalizeBundlePath(baseFilePath || '');
  const baseParts = normalizedBase ? normalizedBase.split('/') : [];
  if (baseParts.length > 0) {
    baseParts.pop();
  }
  const joined = [...baseParts, trimmedRef].join('/');
  return normalizeBundlePath(joined);
}

export function siteBundlePreviewAllowsScripts() {
  return true;
}

export function buildSiteBundlePreviewSrcdoc(bundle, selectedFile) {
  if (!selectedFile || !isSiteBundlePreviewableFile(selectedFile)) {
    return String(selectedFile?.content || '');
  }

  const files = Array.isArray(bundle?.files) ? bundle.files : [];
  const fileMap = new Map();
  files.forEach((file) => {
    const normalizedPath = normalizeBundlePath(file?.path || '');
    if (!normalizedPath) return;
    fileMap.set(normalizedPath, String(file?.content || ''));
  });

  const source = String(selectedFile.content || '');
  const parser = new DOMParser();
  const doc = parser.parseFromString(source, 'text/html');

  const stylesheetLinks = [...doc.querySelectorAll('link[rel~="stylesheet"][href]')];
  stylesheetLinks.forEach((linkNode) => {
    const href = String(linkNode.getAttribute('href') || '').trim();
    const resolvedPath = resolveBundleAssetPath(selectedFile.path, href);
    const css = resolvedPath ? fileMap.get(resolvedPath) : null;
    if (typeof css !== 'string') return;

    const styleNode = doc.createElement('style');
    styleNode.setAttribute('data-site-bundle-inline', resolvedPath);
    styleNode.textContent = css;
    linkNode.replaceWith(styleNode);
  });

  const allowScripts = siteBundlePreviewAllowsScripts();
  const scriptNodes = [...doc.querySelectorAll('script[src]')];
  scriptNodes.forEach((scriptNode) => {
    const src = String(scriptNode.getAttribute('src') || '').trim();
    const resolvedPath = resolveBundleAssetPath(selectedFile.path, src);
    const scriptSource = resolvedPath ? fileMap.get(resolvedPath) : null;
    if (typeof scriptSource !== 'string') return;

    if (!allowScripts) {
      scriptNode.remove();
      return;
    }

    const inlineScriptNode = doc.createElement('script');
    [...scriptNode.attributes].forEach((attribute) => {
      if (attribute.name.toLowerCase() === 'src') return;
      inlineScriptNode.setAttribute(attribute.name, attribute.value);
    });
    inlineScriptNode.setAttribute('data-site-bundle-inline', resolvedPath);
    inlineScriptNode.textContent = scriptSource;
    scriptNode.replaceWith(inlineScriptNode);
  });

  const hasDoctype = /^\s*<!doctype\s+html/i.test(source);
  const docMarkup = doc.documentElement ? doc.documentElement.outerHTML : source;
  return hasDoctype ? `<!doctype html>\n${docMarkup}` : docMarkup;
}

export function appendSiteBundleCard(article, bundlePayload, deps) {
  const { prepareResponseRevealSectionFn, renderArtifactCodeRowsFn } = deps;
  const bundle = normalizeSiteBundle(bundlePayload, deps);
  if (!bundle) return;
  const title = String(bundle.title || 'Site Bundle');
  const slug = String(bundle.slug || '');
  const entry = String(bundle.entry || 'index.html');
  const activeFile = String(bundle.active_file || entry || 'index.html');
  const previewEntrypoint = String(bundle.preview_entrypoint || entry || 'index.html');
  const allFiles = Array.isArray(bundle.files) ? bundle.files : [];
  const fileOptions = getSiteBundleFileOptions(bundle);
  const initialFile = findSiteBundleFile(bundle, activeFile)
    || findSiteBundleFile(bundle, previewEntrypoint)
    || findSiteBundleFile(bundle, entry)
    || allFiles[0]
    || null;

  const card = document.createElement('section');
  card.className = 'site-bundle-card';
  card.dataset.slug = slug;

  const header = document.createElement('div');
  header.className = 'site-bundle-header';

  const titleEl = document.createElement('p');
  titleEl.className = 'site-bundle-title';
  titleEl.textContent = title;

  const label = document.createElement('span');
  label.className = 'site-bundle-label';
  label.textContent = 'Site bundle artifact';

  const meta = document.createElement('p');
  meta.className = 'site-bundle-meta';
  meta.textContent = `${allFiles.length} file${allFiles.length !== 1 ? 's' : ''} · entry: ${entry} · active: ${activeFile} · preview: ${previewEntrypoint} · slug: ${slug || '(none)'}`;

  header.append(titleEl, label, meta);

  const controls = document.createElement('div');
  controls.className = 'site-bundle-controls';

  const modeTabs = document.createElement('div');
  modeTabs.className = 'site-bundle-mode-tabs';

  const codeButton = document.createElement('button');
  codeButton.type = 'button';
  codeButton.className = 'code-artifact-tab site-bundle-mode-button is-active';
  codeButton.textContent = 'Code';

  const previewButton = document.createElement('button');
  previewButton.type = 'button';
  previewButton.className = 'code-artifact-tab site-bundle-mode-button';
  previewButton.textContent = 'Preview';

  modeTabs.append(codeButton, previewButton);

  const filePicker = document.createElement('div');
  filePicker.className = 'site-bundle-file-picker';
  fileOptions.forEach((option) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'site-bundle-file-button';
    button.dataset.path = option.path;
    button.textContent = option.label;
    button.title = option.route ? `${option.path} · ${option.route}` : option.path;
    filePicker.append(button);
  });

  controls.append(modeTabs, filePicker);

  const filesDisclosure = document.createElement('details');
  filesDisclosure.className = 'site-bundle-files-disclosure';

  const filesSummary = document.createElement('summary');
  filesSummary.className = 'site-bundle-files-summary';
  filesSummary.textContent = 'Bundle files';

  const filesBody = document.createElement('div');
  filesBody.className = 'site-bundle-files-body';

  const fileList = document.createElement('ul');
  fileList.className = 'site-bundle-file-list';
  allFiles.forEach((f) => {
    const item = document.createElement('li');
    item.className = 'site-bundle-file-item';
    item.textContent = f.path + (f.language ? ` [${f.language}]` : '');
    fileList.append(item);
  });

  filesBody.append(fileList);
  filesDisclosure.append(filesSummary, filesBody);

  const viewerPanel = document.createElement('div');
  viewerPanel.className = 'site-bundle-viewer';

  const activeLabel = document.createElement('p');
  activeLabel.className = 'site-bundle-active-label';

  const codePane = document.createElement('div');
  codePane.className = 'site-bundle-pane site-bundle-code-panel';
  const codeViewport = document.createElement('div');
  codeViewport.className = 'code-artifact-codeview';
  codePane.append(codeViewport);

  const previewPane = document.createElement('div');
  previewPane.className = 'site-bundle-pane site-bundle-preview-panel';
  previewPane.hidden = true;

  viewerPanel.append(activeLabel, codePane, previewPane);

  let selectedPath = initialFile?.path || '';
  let activeMode = 'code';

  const renderSelection = () => {
    const selectedFile = findSiteBundleFile(bundle, selectedPath) || initialFile;
    const previewable = isSiteBundlePreviewableFile(selectedFile);

    filePicker.querySelectorAll('.site-bundle-file-button').forEach((button) => {
      const isActive = button.dataset.path === selectedFile?.path;
      button.classList.toggle('is-active', isActive);
      button.setAttribute('aria-pressed', String(isActive));
    });

    if (activeMode === 'preview' && !previewable) {
      activeMode = 'code';
    }

    codeButton.classList.toggle('is-active', activeMode === 'code');
    previewButton.classList.toggle('is-active', activeMode === 'preview');
    previewButton.disabled = !previewable;
    activeLabel.textContent = selectedFile ? `Selected file: ${selectedFile.path}` : 'Selected file: none';

    codeViewport.innerHTML = '';
    if (selectedFile) {
      codeViewport.append(renderArtifactCodeRowsFn(selectedFile.content, selectedFile.language));
    }

    previewPane.innerHTML = '';
    if (previewable && selectedFile) {
      const iframe = document.createElement('iframe');
      iframe.className = 'code-artifact-preview-frame';
      iframe.setAttribute('sandbox', 'allow-scripts');
      iframe.setAttribute('title', `${selectedFile.path} preview`);
      iframe.srcdoc = buildSiteBundlePreviewSrcdoc(bundle, selectedFile);
      previewPane.append(iframe);
    } else {
      const previewNote = document.createElement('p');
      previewNote.className = 'code-artifact-preview-note';
      previewNote.textContent = selectedFile
        ? 'Preview is available for HTML pages in this site bundle.'
        : 'Preview is unavailable for this bundle.';
      previewPane.append(previewNote);
    }

    codePane.hidden = activeMode !== 'code';
    previewPane.hidden = activeMode !== 'preview';
  };

  filePicker.addEventListener('click', (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest('.site-bundle-file-button') : null;
    if (!button) return;
    selectedPath = String(button.dataset.path || selectedPath);
    renderSelection();
  });

  codeButton.addEventListener('click', () => {
    activeMode = 'code';
    renderSelection();
  });

  previewButton.addEventListener('click', () => {
    activeMode = 'preview';
    renderSelection();
  });

  renderSelection();

  const notice = document.createElement('p');
  notice.className = 'site-bundle-notice';
  notice.textContent = `This artifact contains ${allFiles.length} file${allFiles.length !== 1 ? 's' : ''}. Use "generate a patch for this site" to prepare them for writing.`;

  card.append(header, controls, filesDisclosure, viewerPanel, notice);
  prepareResponseRevealSectionFn(card, 'artifact');
  article.append(card);

  if (typeof article.scrollIntoView === 'function') {
    article.scrollIntoView({ block: 'start', inline: 'nearest' });
  }
}

export function appendCodeArtifacts(article, messageMetadata, deps) {
  const {
    collectCodeArtifactsFn,
    createCodeArtifactCardFn,
    prepareResponseRevealSectionFn,
    appendRenderErrorNoticeFn,
    showAlertFn,
  } = deps;
  const artifacts = collectCodeArtifactsFn(messageMetadata);
  const renderErrors = [];

  if (!artifacts.length) return renderErrors;

  const artifactTray = document.createElement('div');
  artifactTray.className = 'code-artifact-tray';

  artifacts.forEach((artifact, index) => {
    if (!artifact || typeof artifact !== 'object') return;
    const filename = typeof artifact.filename === 'string' ? artifact.filename.trim() : '';
    const content = typeof artifact.content === 'string' ? artifact.content : '';
    if (!filename || !content) return;
    try {
      artifactTray.append(
        createCodeArtifactCardFn({
          ...artifact,
          filename,
          content,
          artifactIndex: index,
        }),
      );
    } catch (error) {
      renderErrors.push(error);
    }
  });

  if (artifactTray.childElementCount > 0) {
    prepareResponseRevealSectionFn(artifactTray, 'artifact');
    article.append(artifactTray);
  }

  if (renderErrors.length) {
    appendRenderErrorNoticeFn(
      article,
      renderErrors[0],
      'The assistant response rendered, but the code artifact card could not be displayed.',
    );
    showAlertFn('Recovered from assistant artifact rendering failure. You can retry the request.', true, 3000);
  }

  return renderErrors;
}

export function createCodeArtifactCard(artifact, deps) {
  const {
    normalizeArtifactLanguageFn,
    inferLanguageFromFilenameFn,
    isArtifactPreviewableFn,
    languageLabelFn,
    copyCodeArtifactFn,
    downloadCodeArtifactFn,
    toggleArtifactPreviewFn,
    renderArtifactCodeRowsFn,
    sendQuickPromptFn,
    switchArtifactTabFn,
    nextArtifactId,
  } = deps;

  const filename = String(artifact.filename || '').trim();
  const content = String(artifact.content || '');
  const language = normalizeArtifactLanguageFn(artifact.language || inferLanguageFromFilenameFn(filename));
  const previewable = isArtifactPreviewableFn(artifact, filename, language);
  const applied = artifact.applied === true;
  const artifactId = nextArtifactId();

  const card = document.createElement('section');
  card.className = 'code-artifact-card';
  card.dataset.artifactId = artifactId;
  card.dataset.filename = filename;
  card.dataset.language = language;

  const header = document.createElement('div');
  header.className = 'code-artifact-header';

  const chevron = document.createElement('button');
  chevron.type = 'button';
  chevron.className = 'code-artifact-chevron';
  chevron.setAttribute('aria-expanded', 'true');
  chevron.setAttribute('aria-label', 'Collapse code artifact');
  chevron.textContent = '▾';

  const identity = document.createElement('div');
  identity.className = 'code-artifact-identity';

  const fileNameEl = document.createElement('div');
  fileNameEl.className = 'code-artifact-filename';
  fileNameEl.textContent = filename;

  const badgeRow = document.createElement('div');
  badgeRow.className = 'code-artifact-badges';

  const languageBadge = document.createElement('span');
  languageBadge.className = 'code-artifact-badge code-artifact-badge-language';
  languageBadge.textContent = languageLabelFn(language);

  const statusBadge = document.createElement('span');
  statusBadge.className = 'code-artifact-badge code-artifact-badge-status';
  statusBadge.textContent = applied ? 'Applied' : 'Draft only';

  badgeRow.append(languageBadge, statusBadge);
  identity.append(fileNameEl, badgeRow);

  const toolbar = document.createElement('div');
  toolbar.className = 'code-artifact-toolbar';

  const copyButton = document.createElement('button');
  copyButton.type = 'button';
  copyButton.className = 'code-artifact-button';
  copyButton.textContent = 'Copy';
  copyButton.addEventListener('click', async () => {
    await copyCodeArtifactFn(card, artifact, copyButton);
  });

  const downloadButton = document.createElement('button');
  downloadButton.type = 'button';
  downloadButton.className = 'code-artifact-button';
  downloadButton.textContent = 'Download';
  downloadButton.addEventListener('click', () => {
    downloadCodeArtifactFn(artifact);
  });

  const previewButton = document.createElement('button');
  previewButton.type = 'button';
  previewButton.className = 'code-artifact-button';
  previewButton.textContent = 'Preview';
  previewButton.disabled = !previewable;
  previewButton.title = previewable ? 'Preview artifact locally.' : 'Preview is available for HTML artifacts.';
  previewButton.addEventListener('click', () => {
    toggleArtifactPreviewFn(card, artifact, previewButton);
  });

  toolbar.append(copyButton, downloadButton, previewButton);

  header.append(chevron, identity, toolbar);

  const tabs = document.createElement('div');
  tabs.className = 'code-artifact-tabs';

  const codeTab = document.createElement('button');
  codeTab.type = 'button';
  codeTab.className = 'code-artifact-tab is-active';
  codeTab.setAttribute('aria-selected', 'true');
  codeTab.textContent = 'Code';

  const previewTab = document.createElement('button');
  previewTab.type = 'button';
  previewTab.className = 'code-artifact-tab';
  previewTab.setAttribute('aria-selected', 'false');
  previewTab.textContent = 'Preview';
  previewTab.disabled = !previewable;
  previewTab.title = previewable ? 'Preview artifact locally.' : 'Preview is available for HTML artifacts.';

  tabs.append(codeTab, previewTab);

  const body = document.createElement('div');
  body.className = 'code-artifact-body';

  const codePane = document.createElement('div');
  codePane.className = 'code-artifact-pane code-artifact-code-panel code-artifact-pane-code';
  codePane.style.minHeight = '480px';

  const codeViewport = document.createElement('div');
  codeViewport.className = 'code-artifact-codeview';
  codeViewport.append(renderArtifactCodeRowsFn(content, language));
  codePane.append(codeViewport);

  const previewPane = document.createElement('div');
  previewPane.className = 'code-artifact-pane code-artifact-preview-panel code-artifact-pane-preview';
  previewPane.style.minHeight = '480px';
  previewPane.hidden = true;

  if (previewable) {
    if (language === 'html') {
      const iframe = document.createElement('iframe');
      iframe.className = 'code-artifact-preview-frame';
      iframe.setAttribute('sandbox', 'allow-scripts');
      iframe.setAttribute('title', `${filename} preview`);
      iframe.srcdoc = content;
      previewPane.append(iframe);
    } else {
      const previewText = document.createElement('pre');
      previewText.className = 'code-artifact-preview-text';
      previewText.textContent = content;
      previewPane.append(previewText);
    }
  } else {
    const previewNote = document.createElement('p');
    previewNote.className = 'code-artifact-preview-note';
    previewNote.textContent = 'Preview is available for HTML artifacts.';
    previewPane.append(previewNote);
  }

  const footer = document.createElement('div');
  footer.className = 'code-artifact-footer';
  footer.innerHTML = `
      <p class="code-artifact-footer-copy">This code has not been applied to the repo.</p>
      <p class="code-artifact-footer-next">
        Next step: Copy to VS Code or generate patch.
        <button type="button" class="code-artifact-footer-link" title="Patch generation is not enabled yet.">generate patch</button>
      </p>
    `;
  const generatePatchButton = footer.querySelector('.code-artifact-footer-link');
  if (generatePatchButton) {
    generatePatchButton.addEventListener('click', () => {
      void sendQuickPromptFn('generate patch');
    });
  }

  const collapseBody = () => {
    const collapsed = card.classList.toggle('is-collapsed');
    chevron.textContent = collapsed ? '▸' : '▾';
    chevron.setAttribute('aria-expanded', String(!collapsed));
    chevron.setAttribute('aria-label', collapsed ? 'Expand code artifact' : 'Collapse code artifact');
    body.hidden = collapsed;
    tabs.hidden = collapsed;
    footer.hidden = collapsed;
  };

  chevron.addEventListener('click', collapseBody);
  codeTab.addEventListener('click', () => switchArtifactTabFn(card, 'code'));
  previewTab.addEventListener('click', () => switchArtifactTabFn(card, 'preview'));

  body.append(codePane, previewPane);
  card.append(header, tabs, body, footer);

  if (artifact.applied === true) {
    statusBadge.textContent = 'Applied';
  }

  return card;
}

export function renderArtifactCodeRows(content, language, deps) {
  const { createArtifactHighlightStateFn, appendArtifactHighlightedLineFn } = deps;
  const fragment = document.createDocumentFragment();
  const source = String(content || '');
  const lines = source.endsWith('\n') ? source.slice(0, -1).split('\n') : source.split('\n');
  const highlightState = createArtifactHighlightStateFn(language);

  lines.forEach((line, index) => {
    const row = document.createElement('div');
    row.className = `code-artifact-line ${index % 2 === 0 ? 'is-odd' : 'is-even'}`;

    const lineNumber = document.createElement('span');
    lineNumber.className = 'code-artifact-line-number';
    lineNumber.textContent = String(index + 1);

    const lineCode = document.createElement('span');
    lineCode.className = 'code-artifact-line-code';
    appendArtifactHighlightedLineFn(lineCode, line, language, highlightState);

    row.append(lineNumber, lineCode);
    fragment.append(row);
  });

  return fragment;
}

export function createArtifactHighlightState(language, deps) {
  const { normalizeArtifactLanguageFn } = deps;
  const normalized = normalizeArtifactLanguageFn(language);
  return {
    language: normalized,
    inHtmlComment: false,
    inCssComment: false,
    inStyleBlock: false,
    inScriptBlock: false,
  };
}

export function appendArtifactHighlightedLine(container, line, language, state, deps) {
  const {
    normalizeArtifactLanguageFn,
    appendHtmlArtifactLineFn,
    appendCssArtifactLineFn,
    appendPythonArtifactLineFn,
    appendPlainArtifactLineFn,
  } = deps;
  const normalized = normalizeArtifactLanguageFn(language || state?.language || 'text');
  if (normalized === 'html') {
    appendHtmlArtifactLineFn(container, line, state);
    return;
  }
  if (normalized === 'css') {
    appendCssArtifactLineFn(container, line, state);
    return;
  }
  if (normalized === 'python') {
    appendPythonArtifactLineFn(container, line);
    return;
  }
  appendPlainArtifactLineFn(container, line);
}

export function appendPlainArtifactLine(container, line) {
  const text = document.createElement('span');
  text.className = 'code-token-plain';
  text.textContent = line;
  container.append(text);
}

export function appendHtmlArtifactLine(container, line, state, deps) {
  const { appendCssArtifactLineFn, appendArtifactTokenFn, appendHtmlTagTokensFn } = deps;

  if (state.inStyleBlock) {
    const closingIndex = line.toLowerCase().indexOf('</style');
    if (closingIndex === -1) {
      appendCssArtifactLineFn(container, line, state);
      return;
    }
    appendCssArtifactLineFn(container, line.slice(0, closingIndex), state);
    state.inStyleBlock = false;
    appendHtmlArtifactLine(container, line.slice(closingIndex), state, deps);
    return;
  }

  const commentOpen = '<!--';
  const commentClose = '-->';
  let index = 0;

  while (index < line.length) {
    if (state.inHtmlComment) {
      const commentEnd = line.indexOf(commentClose, index);
      if (commentEnd === -1) {
        appendArtifactTokenFn(container, 'code-token-html-comment', line.slice(index));
        return;
      }
      appendArtifactTokenFn(container, 'code-token-html-comment', line.slice(index, commentEnd + commentClose.length));
      state.inHtmlComment = false;
      index = commentEnd + commentClose.length;
      continue;
    }

    const commentStart = line.indexOf(commentOpen, index);
    const tagStart = line.indexOf('<', index);

    if (commentStart !== -1 && (tagStart === -1 || commentStart <= tagStart)) {
      if (commentStart > index) {
        appendArtifactTokenFn(container, 'code-token-html-text', line.slice(index, commentStart));
      }
      const commentEnd = line.indexOf(commentClose, commentStart + commentOpen.length);
      if (commentEnd === -1) {
        appendArtifactTokenFn(container, 'code-token-html-comment', line.slice(commentStart));
        state.inHtmlComment = true;
        return;
      }
      appendArtifactTokenFn(container, 'code-token-html-comment', line.slice(commentStart, commentEnd + commentClose.length));
      index = commentEnd + commentClose.length;
      continue;
    }

    if (tagStart === -1) {
      appendArtifactTokenFn(container, 'code-token-html-text', line.slice(index));
      return;
    }

    if (tagStart > index) {
      appendArtifactTokenFn(container, 'code-token-html-text', line.slice(index, tagStart));
    }

    const tagEnd = line.indexOf('>', tagStart + 1);
    const rawTag = tagEnd === -1 ? line.slice(tagStart) : line.slice(tagStart, tagEnd + 1);
    appendHtmlTagTokensFn(container, rawTag, state);
    index = tagEnd === -1 ? line.length : tagEnd + 1;
  }
}

export function appendHtmlTagTokens(container, rawTag, state, deps) {
  const { appendArtifactTokenFn } = deps;
  if (!rawTag) return;

  const isClosingTag = rawTag.startsWith('</');
  const isSelfClosing = /\/\>\s*$/.test(rawTag);
  const tagMatch = rawTag.match(/^<\/?\s*([A-Za-z][\w:-]*)/);
  let index = 0;

  if (isClosingTag) {
    appendArtifactTokenFn(container, 'code-token-html-bracket', '</');
    index = 2;
  } else {
    appendArtifactTokenFn(container, 'code-token-html-bracket', '<');
    index = 1;
  }

  if (tagMatch) {
    const tagName = tagMatch[1];
    appendArtifactTokenFn(container, 'code-token-html-tag', tagName);
    index = rawTag.indexOf(tagName, index) + tagName.length;
    if (tagName.toLowerCase() === 'style') {
      state.inStyleBlock = !isClosingTag;
    }
    if (tagName.toLowerCase() === 'script') {
      state.inScriptBlock = !isClosingTag;
    }
  }

  while (index < rawTag.length) {
    const ch = rawTag[index];
    if (ch === '>') {
      appendArtifactTokenFn(container, 'code-token-html-bracket', '>');
      return;
    }
    if (ch === '/' && rawTag[index + 1] === '>') {
      appendArtifactTokenFn(container, 'code-token-html-bracket', '/>');
      return;
    }
    if (/\s/.test(ch)) {
      appendArtifactTokenFn(container, 'code-token-html-text', ch);
      index += 1;
      continue;
    }
    if (ch === '=') {
      appendArtifactTokenFn(container, 'code-token-html-bracket', '=');
      index += 1;
      continue;
    }
    if (ch === '"' || ch === "'") {
      const quote = ch;
      let end = index + 1;
      while (end < rawTag.length && rawTag[end] !== quote) end += 1;
      const text = rawTag.slice(index, end < rawTag.length ? end + 1 : rawTag.length);
      appendArtifactTokenFn(container, 'code-token-html-string', text);
      index = end < rawTag.length ? end + 1 : rawTag.length;
      continue;
    }

    const attrMatch = rawTag.slice(index).match(/^[A-Za-z_:][\w:.-]*/);
    if (attrMatch) {
      appendArtifactTokenFn(container, 'code-token-html-attr', attrMatch[0]);
      index += attrMatch[0].length;
      continue;
    }

    appendArtifactTokenFn(container, 'code-token-html-text', ch);
    index += 1;
  }

  if (isSelfClosing) {
    state.inStyleBlock = false;
    state.inScriptBlock = false;
  }
}

export function appendCssArtifactLine(container, line, state, deps) {
  const { appendArtifactTokenFn, appendCssValueTokensFn, appendCssTokenizedLineFn } = deps;
  const commentOpen = '/*';
  const commentClose = '*/';
  let index = 0;

  while (index < line.length) {
    if (state.inCssComment) {
      const commentEnd = line.indexOf(commentClose, index);
      if (commentEnd === -1) {
        appendArtifactTokenFn(container, 'code-token-css-comment', line.slice(index));
        return;
      }
      appendArtifactTokenFn(container, 'code-token-css-comment', line.slice(index, commentEnd + commentClose.length));
      state.inCssComment = false;
      index = commentEnd + commentClose.length;
      continue;
    }

    const commentStart = line.indexOf(commentOpen, index);
    if (commentStart !== -1 && commentStart >= index) {
      if (commentStart > index) {
        appendCssValueTokensFn(container, line.slice(index, commentStart));
      }
      const commentEnd = line.indexOf(commentClose, commentStart + commentOpen.length);
      if (commentEnd === -1) {
        appendArtifactTokenFn(container, 'code-token-css-comment', line.slice(commentStart));
        state.inCssComment = true;
        return;
      }
      appendArtifactTokenFn(container, 'code-token-css-comment', line.slice(commentStart, commentEnd + commentClose.length));
      index = commentEnd + commentClose.length;
      continue;
    }

    appendCssTokenizedLineFn(container, line.slice(index));
    return;
  }
}

export function appendCssTokenizedLine(container, text, deps) {
  const { appendArtifactTokenFn } = deps;
  if (!text) return;
  const pattern = /(\/\*[\s\S]*?\*\/)|(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw|deg|ms|s)?\b)|(#[0-9a-fA-F]{3,8}\b)|(\b[A-Za-z_-][\w-]*\b)(?=\s*:)|([{}();:,])/g;
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      appendArtifactTokenFn(container, 'code-token-css-text', text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (match[1]) {
      appendArtifactTokenFn(container, 'code-token-css-comment', token);
    } else if (match[2]) {
      appendArtifactTokenFn(container, 'code-token-css-string', token);
    } else if (match[3] || match[4]) {
      appendArtifactTokenFn(container, 'code-token-css-number', token);
    } else if (match[5]) {
      appendArtifactTokenFn(container, 'code-token-css-property', token);
    } else {
      appendArtifactTokenFn(container, 'code-token-css-bracket', token);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    appendArtifactTokenFn(container, 'code-token-css-text', text.slice(lastIndex));
  }
}

export function appendPythonArtifactLine(container, line, deps) {
  const { appendArtifactTokenFn } = deps;
  const keywordPattern = /\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b/g;
  const tokenPattern = /(#[^\n]*|'''[\s\S]*?'''|"""[\s\S]*?"""|"(?:\\.|[^"])*"|'(?:\\.|[^'])*'|\b\d+(?:\.\d+)?\b|\b(?:and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b)/g;
  let lastIndex = 0;
  let match;

  while ((match = tokenPattern.exec(line)) !== null) {
    if (match.index > lastIndex) {
      appendArtifactTokenFn(container, 'code-token-plain', line.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('#')) {
      appendArtifactTokenFn(container, 'code-token-python-comment', token);
    } else if (token.startsWith('"') || token.startsWith("'") || token.startsWith('"""') || token.startsWith("'''")) {
      appendArtifactTokenFn(container, 'code-token-python-string', token);
    } else if (/^\d/.test(token)) {
      appendArtifactTokenFn(container, 'code-token-python-number', token);
    } else if (keywordPattern.test(token)) {
      keywordPattern.lastIndex = 0;
      appendArtifactTokenFn(container, 'code-token-python-keyword', token);
    } else {
      appendArtifactTokenFn(container, 'code-token-plain', token);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < line.length) {
    appendArtifactTokenFn(container, 'code-token-plain', line.slice(lastIndex));
  }
}

export function appendArtifactToken(container, className, text) {
  if (!text) return;
  const span = document.createElement('span');
  span.className = className;
  span.textContent = text;
  container.append(span);
}

export function switchArtifactTab(card, tabName) {
  if (!card) return;
  const codeTab = card.querySelector('.code-artifact-tab:nth-of-type(1)');
  const previewTab = card.querySelector('.code-artifact-tab:nth-of-type(2)');
  const codePane = card.querySelector('.code-artifact-code-panel');
  const previewPane = card.querySelector('.code-artifact-preview-panel');
  if (!codeTab || !previewTab || !codePane || !previewPane) return;

  const showPreview = tabName === 'preview' && !previewTab.disabled;
  codeTab.classList.toggle('is-active', !showPreview);
  previewTab.classList.toggle('is-active', showPreview);
  codeTab.setAttribute('aria-selected', String(!showPreview));
  previewTab.setAttribute('aria-selected', String(showPreview));
  codePane.hidden = showPreview;
  previewPane.hidden = !showPreview;
}

export function normalizeArtifactLanguage(language) {
  const normalized = String(language || '').trim().toLowerCase();
  if (!normalized) return 'text';
  if (normalized === 'py') return 'python';
  if (normalized === 'md') return 'markdown';
  return normalized;
}

export function inferLanguageFromFilename(filename) {
  const lower = String(filename || '').toLowerCase();
  if (lower.endsWith('.py')) return 'python';
  if (lower.endsWith('.js')) return 'javascript';
  if (lower.endsWith('.ts')) return 'typescript';
  if (lower.endsWith('.css')) return 'css';
  if (lower.endsWith('.html') || lower.endsWith('.htm')) return 'html';
  if (lower.endsWith('.md')) return 'markdown';
  return 'text';
}

export function languageLabel(language) {
  const normalized = normalizeArtifactLanguage(language);
  if (normalized === 'javascript') return 'JavaScript';
  if (normalized === 'python') return 'Python';
  if (normalized === 'typescript') return 'TypeScript';
  if (normalized === 'markdown') return 'Markdown';
  if (normalized === 'html') return 'HTML';
  if (normalized === 'css') return 'CSS';
  return normalized.toUpperCase();
}

export function isArtifactPreviewable(artifact, filename, language) {
  if (artifact && artifact.previewable === true) return true;
  const normalized = normalizeArtifactLanguage(language || inferLanguageFromFilename(filename));
  return normalized === 'html';
}

export async function copyCodeArtifact(card, artifact, button, deps) {
  const { copyToClipboardFn, artifactCopyState } = deps;
  const content = String(artifact?.content || '');
  if (!content) return;
  await copyToClipboardFn(content);
  if (!button) return;

  const original = button.textContent || 'Copy';
  button.textContent = 'Copied';
  button.classList.add('is-copied');
  window.clearTimeout(artifactCopyState.get(card)?.timer || 0);
  const timer = window.setTimeout(() => {
    button.textContent = original;
    button.classList.remove('is-copied');
  }, 1200);
  artifactCopyState.set(card, { copied: true, timer });
}

export function downloadCodeArtifact(artifact, deps) {
  const { sanitizeArtifactDownloadNameFn } = deps;
  const filename = sanitizeArtifactDownloadNameFn(artifact?.filename || 'artifact.txt');
  const content = String(artifact?.content || '');
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function sanitizeArtifactDownloadName(filename) {
  const name = String(filename || 'artifact.txt').trim().split(/[\\/]/).pop() || 'artifact.txt';
  return name;
}

export function toggleArtifactPreview(card, artifact, button, deps) {
  const { switchArtifactTabFn } = deps;
  if (!card) return;
  const previewPane = card.querySelector('.code-artifact-pane-preview');
  const codePane = card.querySelector('.code-artifact-pane-code');
  if (!previewPane || !codePane || button?.disabled) return;
  switchArtifactTabFn(card, 'preview');
}
