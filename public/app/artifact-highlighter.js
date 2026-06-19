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

