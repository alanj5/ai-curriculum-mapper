/** Transient bottom toast, optionally with a one-click Undo action.
 * A single toast element is reused; a new toast replaces the previous one. */

let _toastEl = null;
let _timer = null;

function _ensure() {
  if (_toastEl) return _toastEl;
  _toastEl = document.createElement('div');
  _toastEl.className = 'toast hidden';
  _toastEl.setAttribute('role', 'status');
  document.body.appendChild(_toastEl);
  return _toastEl;
}

function _dismiss() {
  if (_toastEl) _toastEl.classList.add('hidden');
  clearTimeout(_timer);
}

/** Show `message` with an "Undo" button; `onUndo` runs if the user clicks it. */
export function showUndoToast(message, onUndo, ms = 5000) {
  const el = _ensure();
  clearTimeout(_timer);
  el.innerHTML = '<span class="toast-msg"></span><button class="toast-undo" type="button">Undo</button>';
  el.querySelector('.toast-msg').textContent = message;
  el.classList.remove('hidden');
  el.querySelector('.toast-undo').addEventListener('click', async () => {
    _dismiss();
    try { await onUndo(); } catch (e) { showToast(`Undo failed: ${e.message}`); }
  });
  _timer = setTimeout(_dismiss, ms);
}

/** Show a plain transient message (no action). */
export function showToast(message, ms = 3000) {
  const el = _ensure();
  clearTimeout(_timer);
  el.innerHTML = '<span class="toast-msg"></span>';
  el.querySelector('.toast-msg').textContent = message;
  el.classList.remove('hidden');
  _timer = setTimeout(_dismiss, ms);
}
