/**
 * voice-controller.js
 * Pure helpers and rendering helpers for voice input/output extracted from app.js.
 * No imports from app.js — avoids circular dependency.
 */

// ── Pure helpers ────────────────────────────────────────────────────────────

export function stripReasoningTokens(text) {
  return text.replace(/<\|think\|>[\s\S]*?<\/\|think\|>/g, '').trim();
}

export function normalizeSpeechText(text) {
  const raw = stripReasoningTokens(String(text || ''));
  if (!raw) return '';

  const blockedPrefixes = [
    'operator receipt:',
    'context receipt:',
    'memory receipt:',
    'model receipt:',
    'receipt:',
    'receipts:',
    'system:',
    'memory:',
    'knowledge:',
    'focus:',
    'verified:',
    'model:',
    'sources:',
    'diagnostics:',
    'metadata:',
  ];

  const withoutFences = raw
    .replace(/```[a-z0-9_-]*\s*/gi, '\n')
    .replace(/```/g, '\n');

  const spokenLines = withoutFences
    .split('\n')
    .map((line) => line.trim())
    .map((line) => line.replace(/^#{1,6}\s+/, ''))
    .map((line) => line.replace(/`([^`]*)`/g, '$1'))
    .map((line) => line.replace(/\*\*|__|\*|_/g, ''))
    .map((line) => {
      const bullet = line.match(/^[-*•]\s+(.+)$/);
      if (!bullet) return line;
      const content = bullet[1].trim();
      if (!content) return '';
      return /[.!?;:]$/.test(content) ? content : `${content}.`;
    })
    .filter((line) => {
      if (!line) return false;
      const lowered = line.toLowerCase();
      if (blockedPrefixes.some((prefix) => lowered.startsWith(prefix))) return false;
      if (/\bxv7-(system|memory|knowledge|focus|verified)-\d+\b/i.test(line)) return false;
      if (/\bqwen\d*:[a-z0-9_.-]+\b/i.test(line)) return false;
      return true;
    });

  const normalized = spokenLines
    .join(' ')
    .replace(/^\s*Xoduz\s+is\s+pronounced\s+Exodus\.?\s*$/i, 'Exodus.')
    .replace(/\bX-O-D-U-Z\b/g, 'X O D U Z')
    .replace(/\bXoduz\b/gi, 'Exodus')
    .replace(/\bXV\s*-?\s*7\b/gi, 'X V Seven')
    .replace(/\s+/g, ' ')
    .trim();

  return normalized;
}

export function clampVoiceNumber(value, min, max, fallback) {
  const parsed = Number.parseFloat(String(value));
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

export function mergeTranscript(existingValue, transcript) {
  const current = String(existingValue || '').trim();
  const next = String(transcript || '').trim();
  if (!current) return next;
  if (!next) return current;
  const joiner = /[\n\s]$/.test(existingValue || '') ? '' : ' ';
  return `${existingValue}${joiner}${next}`.trim();
}

export function isFemaleLikeVoice(voice) {
  if (!voice) return false;
  const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
  return ['female', 'woman', 'jenny', 'aria', 'sonia', 'zira', 'susan', 'samantha', 'victoria', 'google us english', 'microsoft zira', 'microsoft jenny', 'microsoft aria']
    .some((hint) => haystack.includes(hint));
}

export function choosePreferredVoice(voices) {
  if (!Array.isArray(voices) || !voices.length) return null;

  const googleUsFemaleVoice = voices.find((voice) => {
    const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
    const isFemale = ['female', 'woman', 'google us english'].some((hint) => haystack.includes(hint)) ||
                    voice.lang === 'en-US';
    return (haystack.includes('google') && haystack.includes('us') && isFemale) ||
           (haystack.includes('google us english'));
  });
  if (googleUsFemaleVoice) return googleUsFemaleVoice;

  const enUsFemaleVoice = voices.find((voice) => {
    const lang = String(voice.lang || '').toLowerCase();
    const isFemale = voice.lang === 'en-US' || lang === 'en-us' || lang === 'en_us';
    const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
    const hasFemaleHint = ['female', 'woman', 'jenny', 'aria', 'sonia', 'zira', 'samantha', 'victoria',
                          'microsoft zira', 'microsoft jenny', 'microsoft aria'].some((hint) => haystack.includes(hint));
    return isFemale && hasFemaleHint;
  });
  if (enUsFemaleVoice) return enUsFemaleVoice;

  const femaleHints = ['female', 'woman', 'jenny', 'aria', 'sonia', 'zira', 'samantha', 'victoria', 'microsoft zira', 'microsoft jenny', 'microsoft aria'];
  const femaleVoice = voices.find((voice) => {
    const haystack = `${voice.name || ''} ${voice.lang || ''}`.toLowerCase();
    if (haystack.includes('susan') && !haystack.includes('en-us')) return false;
    return femaleHints.some((hint) => haystack.includes(hint));
  });
  if (femaleVoice) return femaleVoice;

  const englishVoice = voices.find((voice) => String(voice.lang || '').toLowerCase().startsWith('en'));
  if (englishVoice) return englishVoice;

  return voices.find((voice) => voice.default) || voices[0] || null;
}

export function dispatchVoiceEvent(name, detail = {}) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

// ── Persistence helpers ──────────────────────────────────────────────────────

export function loadVoicePreferences(voiceSettings) {
  try {
    const voiceName = window.localStorage.getItem('xv7.voice.voiceName');
    const volume = window.localStorage.getItem('xv7.voice.volume');
    const rate = window.localStorage.getItem('xv7.voice.rate');
    const pitch = window.localStorage.getItem('xv7.voice.pitch');
    const muted = window.localStorage.getItem('xv7.voice.muted');

    voiceSettings.voiceName = typeof voiceName === 'string' ? voiceName : '';
    voiceSettings.volume = clampVoiceNumber(volume, 0, 1, 1);
    voiceSettings.rate = clampVoiceNumber(rate, 0.5, 2, 1);
    voiceSettings.pitch = clampVoiceNumber(pitch, 0.5, 2, 1.1);
    voiceSettings.muted = muted === 'true';
  } catch {
    voiceSettings.voiceName = '';
    voiceSettings.volume = 1;
    voiceSettings.rate = 1;
    voiceSettings.pitch = 1.1;
    voiceSettings.muted = false;
  }
}

export function saveVoicePreferences(voiceSettings) {
  try {
    window.localStorage.setItem('xv7.voice.voiceName', voiceSettings.voiceName || '');
    window.localStorage.setItem('xv7.voice.volume', String(voiceSettings.volume));
    window.localStorage.setItem('xv7.voice.rate', String(voiceSettings.rate));
    window.localStorage.setItem('xv7.voice.pitch', String(voiceSettings.pitch));
    window.localStorage.setItem('xv7.voice.muted', String(voiceSettings.muted));
  } catch {
    // Best-effort only.
  }
}

// ── DOM rendering helpers ────────────────────────────────────────────────────

export function setVoiceStatus(els, message) {
  if (!els.voiceStatus) return;
  els.voiceStatus.textContent = message || '';
}

export function renderVoiceSelectOptions(els, voiceSettings, availableVoices) {
  if (!els.voiceSelect) return;

  const currentValue = voiceSettings.voiceName || '';
  const voices = [...availableVoices].sort((left, right) => {
    const leftLabel = `${left.lang || ''} ${left.name || ''}`.toLowerCase();
    const rightLabel = `${right.lang || ''} ${right.name || ''}`.toLowerCase();
    return leftLabel.localeCompare(rightLabel);
  });

  els.voiceSelect.innerHTML = '';

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Browser default';
  els.voiceSelect.append(defaultOption);

  voices.forEach((voice) => {
    const option = document.createElement('option');
    option.value = voice.name || '';
    option.textContent = `${voice.name || 'Unnamed voice'} (${voice.lang || 'unknown'})`;
    els.voiceSelect.append(option);
  });

  els.voiceSelect.value = voices.some((voice) => voice.name === currentValue) ? currentValue : '';
}

export function syncVoiceSettingsToControls(els, voiceSettings, availableVoices) {
  if (els.voiceSelect) els.voiceSelect.value = voiceSettings.voiceName || '';
  if (els.voiceVolume) els.voiceVolume.value = String(voiceSettings.volume);
  if (els.sidebarVoiceVolume) els.sidebarVoiceVolume.value = String(voiceSettings.volume);
  if (els.sidebarVoiceVolumeValue) els.sidebarVoiceVolumeValue.textContent = `${Math.round(voiceSettings.volume * 100)}%`;
  if (els.voiceRate) els.voiceRate.value = String(voiceSettings.rate);
  if (els.voicePitch) els.voicePitch.value = String(voiceSettings.pitch);
  if (els.voiceMute) els.voiceMute.checked = Boolean(voiceSettings.muted);
  if (els.sidebarVoiceMuteButton) {
    const isMuted = Boolean(voiceSettings.muted);
    els.sidebarVoiceMuteButton.setAttribute('aria-pressed', String(isMuted));
    els.sidebarVoiceMuteButton.setAttribute('aria-label', isMuted ? 'Unmute voice output' : 'Mute voice output');
  }
  if (els.sidebarVoiceMuteIconOn) {
    els.sidebarVoiceMuteIconOn.classList.toggle('hidden', Boolean(voiceSettings.muted));
  }
  if (els.sidebarVoiceMuteIconOff) {
    els.sidebarVoiceMuteIconOff.classList.toggle('hidden', !Boolean(voiceSettings.muted));
  }
  if (els.sidebarVoiceMuteLabel) {
    els.sidebarVoiceMuteLabel.textContent = voiceSettings.muted ? 'Unmute output' : 'Mute output';
  }
  if (els.sidebarVoiceMuteState) {
    els.sidebarVoiceMuteState.textContent = voiceSettings.muted ? 'Muted' : 'On';
  }
  if (els.avatarVoiceLabel) {
    const selected = availableVoices.find((voice) => voice.name === voiceSettings.voiceName) || choosePreferredVoice(availableVoices);
    els.avatarVoiceLabel.textContent = `Voice: ${selected?.name || 'Browser default'}`;
  }
}

export function renderReadAloudButton(button, messageId, speaking, speakingMessageId, speechOutputSupported) {
  if (!button) return;
  if (!speechOutputSupported) {
    button.disabled = true;
    button.textContent = 'Read';
    button.setAttribute('aria-label', 'Read assistant response aloud');
    button.title = 'Read aloud is not supported in this browser.';
    return;
  }

  const isActive = speaking && speakingMessageId === messageId;
  button.disabled = false;
  button.classList.toggle('speaking', isActive);
  button.textContent = isActive ? 'Stop' : 'Read';
  button.setAttribute('aria-label', isActive ? 'Stop reading aloud' : 'Read assistant response aloud');
  button.title = isActive ? 'Stop reading aloud.' : 'Read assistant response aloud.';
}

export function updateReadAloudButtons(els, speaking, speakingMessageId, speechOutputSupported) {
  const buttons = els.chatTimeline?.querySelectorAll('.message-audio-button') || [];
  buttons.forEach((button) => {
    renderReadAloudButton(button, button.dataset.messageId || '', speaking, speakingMessageId, speechOutputSupported);
  });
}

export function renderVoiceDiagnostics(els, voiceState, voiceSettings, availableVoices, voiceAvailabilityNote, deps) {
  const { syncVoiceSettingsToControlsFn, renderAvatarDiagnosticsFn } = deps;
  if (els.voiceDiagInput) {
    els.voiceDiagInput.textContent = voiceState.inputSupported ? 'supported' : 'unsupported';
  }
  if (els.voiceDiagMicState) {
    let micState = 'idle';
    if (!voiceState.inputSupported) {
      micState = 'unsupported';
    } else if (voiceState.permissionDenied) {
      micState = 'denied';
    } else if (voiceState.listening) {
      micState = 'listening';
    }
    els.voiceDiagMicState.textContent = micState;
  }
  if (els.voiceDiagOutput) {
    els.voiceDiagOutput.textContent = voiceState.outputSupported ? 'yes' : 'no';
  }
  if (els.voiceDiagVoiceCount) {
    els.voiceDiagVoiceCount.textContent = String(availableVoices.length);
  }
  if (els.voiceDiagSelected) {
    const selected = availableVoices.find((voice) => voice.name === voiceSettings.voiceName) || choosePreferredVoice(availableVoices);
    els.voiceDiagSelected.textContent = selected?.name || 'Browser default';
  }
  if (els.voiceDiagVolume) {
    els.voiceDiagVolume.textContent = voiceSettings.volume.toFixed(1);
  }
  if (els.voiceDiagRate) {
    els.voiceDiagRate.textContent = voiceSettings.rate.toFixed(1);
  }
  if (els.voiceDiagPitch) {
    els.voiceDiagPitch.textContent = voiceSettings.pitch.toFixed(1);
  }
  if (els.voiceDiagSpeaking) {
    els.voiceDiagSpeaking.textContent = voiceState.speaking ? 'yes' : 'no';
  }
  if (els.voiceSettingsStatus) {
    els.voiceSettingsStatus.textContent = availableVoices.length
      ? voiceAvailabilityNote
      : 'No browser voices are available.';
  }
  syncVoiceSettingsToControlsFn();
  renderAvatarDiagnosticsFn();
}

// ── Speech output helpers ────────────────────────────────────────────────────

export function buildSpeechUtterance(text, voiceSettings, availableVoices) {
  if (!window.SpeechSynthesisUtterance) return null;

  const spokenText = normalizeSpeechText(text);
  if (!spokenText) return null;

  const utterance = new window.SpeechSynthesisUtterance(spokenText);
  const selectedVoice = availableVoices.find((voice) => voice.name === voiceSettings.voiceName) || choosePreferredVoice(availableVoices);
  if (selectedVoice) {
    utterance.voice = selectedVoice;
    if (selectedVoice.lang) {
      utterance.lang = selectedVoice.lang;
    }
  }
  utterance.volume = voiceSettings.muted ? 0 : voiceSettings.volume;
  utterance.rate = voiceSettings.rate;
  utterance.pitch = voiceSettings.pitch;
  return utterance;
}

export function startSpeechPlayback(text, options = {}, deps) {
  const {
    speechOutputSupported, voiceState,
    buildSpeechUtteranceFn,
    setSpeaking, setSpeakingMessageId, setActiveUtterance,
    getCurrentSpeaking, getCurrentSpeakingMessageId,
    dispatchVoiceEventFn, setVoiceStatusFn,
    renderVoiceDiagnosticsFn, updateReadAloudButtonsFn, showAlertFn,
  } = deps;

  if (!speechOutputSupported || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    return false;
  }

  const utterance = buildSpeechUtteranceFn(text);
  if (!utterance) return false;

  const messageId = options.messageId || null;
  const startStatus = options.startStatus || 'Reading response aloud...';
  const stopStatus = options.stopStatus || 'Read-aloud stopped.';
  const failStatus = options.failStatus || 'Browser blocked voice playback. Try clicking Test Voice again.';

  window.speechSynthesis.cancel();
  if (getCurrentSpeaking() && getCurrentSpeakingMessageId()) {
    dispatchVoiceEventFn('xv7:voice-speaking-stop', { messageId: getCurrentSpeakingMessageId() });
  }

  utterance.onend = () => {
    setSpeaking(false);
    setSpeakingMessageId(null);
    setActiveUtterance(null);
    voiceState.speaking = false;
    voiceState.speakingMessageId = null;
    setVoiceStatusFn(stopStatus);
    dispatchVoiceEventFn('xv7:voice-speaking-stop', { messageId });
    renderVoiceDiagnosticsFn();
    updateReadAloudButtonsFn();
  };
  utterance.onerror = () => {
    setSpeaking(false);
    setSpeakingMessageId(null);
    setActiveUtterance(null);
    voiceState.speaking = false;
    voiceState.speakingMessageId = null;
    voiceState.lastVoiceError = failStatus;
    setVoiceStatusFn(failStatus);
    dispatchVoiceEventFn('xv7:voice-error', { error: 'speech_output_error', messageId });
    dispatchVoiceEventFn('xv7:voice-speaking-stop', { messageId });
    renderVoiceDiagnosticsFn();
    updateReadAloudButtonsFn();
    showAlertFn(failStatus, true, 1800);
  };

  setSpeaking(true);
  setSpeakingMessageId(messageId);
  setActiveUtterance(utterance);
  voiceState.speaking = true;
  voiceState.speakingMessageId = messageId;
  setVoiceStatusFn(startStatus);
  dispatchVoiceEventFn('xv7:voice-speaking-start', { messageId, text });
  renderVoiceDiagnosticsFn();
  updateReadAloudButtonsFn();

  try {
    window.speechSynthesis.speak(utterance);
  } catch {
    setSpeaking(false);
    setSpeakingMessageId(null);
    setActiveUtterance(null);
    voiceState.speaking = false;
    voiceState.speakingMessageId = null;
    voiceState.lastVoiceError = failStatus;
    setVoiceStatusFn(failStatus);
    renderVoiceDiagnosticsFn();
    updateReadAloudButtonsFn();
    showAlertFn(failStatus, true, 1800);
    return false;
  }

  return true;
}

export function stopVoicePlayback(deps) {
  const {
    speechOutputSupported, voiceState,
    setSpeaking, setSpeakingMessageId, setActiveUtterance,
    setVoiceStatusFn, dispatchVoiceEventFn,
    renderVoiceDiagnosticsFn, updateReadAloudButtonsFn,
  } = deps;

  if (!speechOutputSupported || !window.speechSynthesis) return;

  window.speechSynthesis.cancel();
  setSpeaking(false);
  setSpeakingMessageId(null);
  setActiveUtterance(null);
  voiceState.speaking = false;
  voiceState.speakingMessageId = null;
  setVoiceStatusFn('Voice playback stopped.');
  dispatchVoiceEventFn('xv7:voice-speaking-stop', {});
  renderVoiceDiagnosticsFn();
  updateReadAloudButtonsFn();
}

export function playVoiceSample(deps) {
  const { startSpeechPlaybackFn, voiceSettings, setVoiceStatusFn } = deps;
  const success = startSpeechPlaybackFn('Hello Otis. I am Xoduz. This is my selected voice.', {
    startStatus: 'Testing voice output...',
    stopStatus: 'Test voice finished.',
    failStatus: 'Browser blocked voice playback. Try clicking Test Voice again.',
    messageId: 'test-voice',
  });

  if (!success && voiceSettings.muted) {
    setVoiceStatusFn('Voice output is muted.');
  }
}

export function toggleReadAloud(article, deps) {
  const {
    speechOutputSupported, speaking, speakingMessageId,
    stopVoicePlaybackFn, startSpeechPlaybackFn, showAlertFn,
  } = deps;

  const messageId = article?.dataset?.messageId || '';
  const visibleText = article?.querySelector('.chat-visible-text')?.textContent?.trim() || '';
  if (!visibleText) return;

  if (!speechOutputSupported || !window.speechSynthesis || !window.SpeechSynthesisUtterance) {
    showAlertFn('Read aloud is not supported in this browser.', true, 1800);
    return;
  }

  if (speaking && speakingMessageId === messageId) {
    stopVoicePlaybackFn();
    return;
  }

  startSpeechPlaybackFn(visibleText, {
    messageId,
    startStatus: 'Reading response aloud...',
    stopStatus: 'Read-aloud stopped.',
    failStatus: 'Browser blocked voice playback. Try clicking Test Voice again.',
  });
}

// ── Voice setup helpers ──────────────────────────────────────────────────────

export function setupVoiceOutput(deps) {
  const {
    voiceState, setSpeechOutputSupported, setAvailableVoices, setVoiceAvailabilityNote,
    renderVoiceDiagnosticsFn, refreshVoiceVoicesFn,
  } = deps;

  const supported = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
  setSpeechOutputSupported(supported);
  voiceState.outputSupported = supported;

  if (!supported) {
    setAvailableVoices([]);
    setVoiceAvailabilityNote('No browser voices are available.');
    renderVoiceDiagnosticsFn();
    return;
  }

  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      refreshVoiceVoicesFn();
    };
  }

  renderVoiceDiagnosticsFn();
}

export function refreshVoiceVoices(deps) {
  const {
    speechOutputSupported, setAvailableVoices,
    renderVoiceSelectOptionsFn, applyPreferredVoiceIfNeededFn, renderVoiceDiagnosticsFn,
  } = deps;

  if (!speechOutputSupported || !window.speechSynthesis) {
    setAvailableVoices([]);
    renderVoiceDiagnosticsFn();
    return;
  }

  const voices = typeof window.speechSynthesis.getVoices === 'function' ? window.speechSynthesis.getVoices() : [];
  setAvailableVoices(Array.isArray(voices) ? voices.filter((voice) => voice && typeof voice.name === 'string') : []);

  renderVoiceSelectOptionsFn();
  applyPreferredVoiceIfNeededFn();
  renderVoiceDiagnosticsFn();
}

export function applyPreferredVoiceIfNeeded(voiceSettings, availableVoices, deps) {
  const { setVoiceAvailabilityNote, saveVoicePreferencesFn, syncVoiceSettingsToControlsFn } = deps;

  if (!availableVoices.length) {
    setVoiceAvailabilityNote('No browser voices are available.');
    voiceSettings.voiceName = '';
    syncVoiceSettingsToControlsFn();
    return;
  }

  const currentVoice = availableVoices.find((voice) => voice.name === voiceSettings.voiceName);
  if (currentVoice) {
    setVoiceAvailabilityNote(isFemaleLikeVoice(currentVoice)
      ? `Using ${currentVoice.name}.`
      : 'Using browser default voice. Select a different voice if needed.');
    syncVoiceSettingsToControlsFn();
    return;
  }

  const preferredVoice = choosePreferredVoice(availableVoices);
  voiceSettings.voiceName = preferredVoice?.name || '';
  setVoiceAvailabilityNote(preferredVoice && isFemaleLikeVoice(preferredVoice)
    ? `Using ${preferredVoice.name}.`
    : 'Using browser default voice. Select a different voice if needed.');
  saveVoicePreferencesFn();
  syncVoiceSettingsToControlsFn();
}
