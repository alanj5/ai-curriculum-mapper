import { api } from '../api.js';

let _pendingAlignmentId = null;
let _onDone = null;

export function initValidationWidget(kaOptions) {
  const modal = document.getElementById('reassign-modal');
  const kaSelect = document.getElementById('reassign-ka-select');
  const confirmBtn = document.getElementById('reassign-confirm');
  const cancelBtn = document.getElementById('reassign-cancel');

  // Populate KA options
  kaSelect.innerHTML = kaOptions.map(ka => `<option value="${ka.code}">${ka.code} — ${ka.name}</option>`).join('');

  confirmBtn.addEventListener('click', async () => {
    const newKa = kaSelect.value;
    const comment = document.getElementById('reassign-comment').value.trim();
    if (!newKa || !_pendingAlignmentId) return;
    confirmBtn.disabled = true;
    try {
      await api.validate(_pendingAlignmentId, { action: 'reassign', new_ka_code: newKa, comment: comment || null });
      closeModal();
      if (_onDone) _onDone();
    } catch (e) {
      alert(`Reassign failed: ${e.message}`);
    } finally {
      confirmBtn.disabled = false;
    }
  });

  cancelBtn.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
}

export function openReassignModal(alignmentId, onDone) {
  _pendingAlignmentId = alignmentId;
  _onDone = onDone;
  document.getElementById('reassign-comment').value = '';
  document.getElementById('reassign-modal').classList.remove('hidden');
}

function closeModal() {
  _pendingAlignmentId = null;
  document.getElementById('reassign-modal').classList.add('hidden');
}

export async function acceptAlignment(id, onDone) {
  try {
    await api.validate(id, { action: 'accept' });
    if (onDone) onDone();
    return true;
  } catch (e) {
    alert(`Accept failed: ${e.message}`);
    return false;
  }
}

export async function rejectAlignment(id, onDone) {
  try {
    await api.validate(id, { action: 'reject' });
    if (onDone) onDone();
    return true;
  } catch (e) {
    alert(`Reject failed: ${e.message}`);
    return false;
  }
}

// Undo a prior accept/reject — returns the alignment to unvalidated.
export async function resetAlignment(id, onDone) {
  try {
    await api.validate(id, { action: 'reset' });
    if (onDone) onDone();
    return true;
  } catch (e) {
    alert(`Undo failed: ${e.message}`);
    return false;
  }
}
