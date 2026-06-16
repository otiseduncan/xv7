/**
 * avatar-controller.js
 * Pure helpers and rendering helpers for avatar state/diagnostics extracted from app.js.
 * No imports from app.js — avoids circular dependency.
 */

// ── Pure helpers ────────────────────────────────────────────────────────────

export function resolveAvatarMediaEnabled() {
  const bodyValue = String(document.body?.dataset?.avatarMedia || '').toLowerCase();
  if (bodyValue === 'off' || bodyValue === 'disabled') return false;

  const storedValue = String(window.localStorage?.getItem('xv7-avatar-media') || '').toLowerCase();
  if (storedValue === 'off' || storedValue === 'disabled') return false;
  if (storedValue === 'on' || storedValue === 'enabled') return true;

  const runtimeValue = window.XV7_ENABLE_AVATAR_MEDIA;
  if (runtimeValue === false) return false;
  if (runtimeValue === true) return true;

  return true;
}

export function avatarStateLabel(stateName) {
  const labels = {
    idle: 'Idle',
    listening: 'Listening',
    captured: 'Captured',
    thinking: 'Thinking',
    speaking: 'Speaking',
    error: 'Voice error',
  };
  return labels[stateName] || 'Idle';
}

// ── DOM rendering helpers ────────────────────────────────────────────────────

export function renderAvatarStateUI(els, avatarState) {
  if (els.avatarShell) {
    els.avatarShell.classList.remove('state-idle', 'state-listening', 'state-captured', 'state-thinking', 'state-speaking', 'state-error');
    els.avatarShell.classList.add(`state-${avatarState}`);
    els.avatarShell.setAttribute('aria-label', `Xoduz avatar state ${avatarStateLabel(avatarState)}`);
  }
  if (els.avatarStateText) {
    els.avatarStateText.textContent = avatarStateLabel(avatarState);
  }
}

export function renderAvatarDiagnostics(els, avatarState, avatarClips, avatarMediaEnabled, avatarClipLoaded, avatarLastEvent) {
  const clipPath = avatarClips[avatarState] || avatarClips.idle || '';
  const clipName = avatarMediaEnabled
    ? (clipPath.split('/').pop() || 'fallback')
    : ((clipPath.split('/').pop() || 'fallback') + ' (disabled)');
  const visible = els.avatarCard ? !els.avatarCard.classList.contains('collapsed') : false;

  if (els.avatarDiagState) els.avatarDiagState.textContent = avatarState;
  if (els.avatarDiagClip) els.avatarDiagClip.textContent = clipName;
  if (els.avatarDiagLoaded) els.avatarDiagLoaded.textContent = avatarClipLoaded ? 'yes' : 'no';
  if (els.avatarDiagVisible) els.avatarDiagVisible.textContent = visible ? 'yes' : 'no';
  if (els.avatarDiagEvent) els.avatarDiagEvent.textContent = avatarLastEvent || 'init';

  if (els.avatarFallback) {
    els.avatarFallback.classList.toggle('hidden', avatarClipLoaded);
  }
}
