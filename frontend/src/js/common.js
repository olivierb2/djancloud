import '../css/main.css';

// CSRF helper
export function getCsrfToken() {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
}

// Modal helpers
export function openModal(id) {
    const m = document.getElementById(id);
    m.classList.remove('hidden');
    m.classList.add('flex');
    var newMenu = document.getElementById('new-menu');
    if (newMenu) newMenu.classList.add('hidden');
    const input = m.querySelector('input[type="text"]');
    if (input) { input.focus(); input.select(); }
}

export function closeModal(id) {
    const m = document.getElementById(id);
    m.classList.add('hidden');
    m.classList.remove('flex');
}

// Global modal close handlers
document.querySelectorAll('[id$="-modal"]').forEach(m => {
    m.addEventListener('click', e => { if (e.target === m) closeModal(m.id); });
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('[id$="-modal"].flex').forEach(m => closeModal(m.id));
});

// Expose globally for inline onclick handlers in HTML
window.openModal = openModal;
window.closeModal = closeModal;
