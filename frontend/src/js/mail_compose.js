import '../css/mail_compose.css';

document.addEventListener('DOMContentLoaded', function () {
  const editor = document.getElementById('editor');
  if (!editor) return;

  // ── WYSIWYG Toolbar ──
  document.querySelectorAll('.toolbar-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      editor.focus();
      const cmd = btn.dataset.cmd;
      if (cmd === 'createLink') {
        const url = prompt('Enter URL:');
        if (url) document.execCommand(cmd, false, url);
      } else {
        document.execCommand(cmd, false, null);
      }
    });
  });

  const formatBlock = document.getElementById('format-block');
  if (formatBlock) {
    formatBlock.addEventListener('change', () => {
      editor.focus();
      document.execCommand('formatBlock', false, formatBlock.value);
    });
  }

  const fontSize = document.getElementById('font-size');
  if (fontSize) {
    fontSize.addEventListener('change', () => {
      editor.focus();
      document.execCommand('fontSize', false, fontSize.value);
    });
  }

  const textColor = document.getElementById('text-color');
  if (textColor) {
    textColor.addEventListener('input', () => {
      editor.focus();
      document.execCommand('foreColor', false, textColor.value);
    });
  }

  // ── Placeholder ──
  function updatePlaceholder() {
    if (
      editor.textContent.trim() === '' &&
      !editor.querySelector('img, blockquote')
    ) {
      editor.classList.add('is-empty');
    } else {
      editor.classList.remove('is-empty');
    }
  }
  editor.addEventListener('input', updatePlaceholder);
  updatePlaceholder();

  // ── Contact autocomplete ──
  function setupAutocomplete(inputId, suggestionsId, hiddenId, tagsId) {
    const input = document.getElementById(inputId);
    const suggestions = document.getElementById(suggestionsId);
    const hidden = document.getElementById(hiddenId);
    const tagsContainer = document.getElementById(tagsId);
    if (!input || !suggestions || !hidden) return;

    let emails = hidden.value
      ? hidden.value
          .split(',')
          .map((e) => e.trim())
          .filter(Boolean)
      : [];
    let debounceTimer = null;

    function renderTags() {
      tagsContainer
        .querySelectorAll('.email-tag')
        .forEach((t) => t.remove());
      emails.forEach((email, i) => {
        const tag = document.createElement('span');
        tag.className =
          'email-tag inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700';
        tag.innerHTML = `${email}<button type="button" data-idx="${i}" class="ml-0.5 text-brand-500 hover:text-brand-700">&times;</button>`;
        tagsContainer.insertBefore(tag, input);
      });
      hidden.value = emails.join(', ');
    }

    function addEmail(email) {
      email = email.trim();
      if (email && !emails.includes(email)) {
        emails.push(email);
        renderTags();
      }
      input.value = '';
      suggestions.classList.add('hidden');
    }

    tagsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-idx]');
      if (btn) {
        const idx = parseInt(btn.dataset.idx);
        emails.splice(idx, 1);
        renderTags();
      }
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
        e.preventDefault();
        if (input.value.trim()) {
          addEmail(input.value);
        }
      }
      if (
        e.key === 'Backspace' &&
        !input.value &&
        emails.length > 0
      ) {
        emails.pop();
        renderTags();
      }
    });

    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 1) {
        suggestions.classList.add('hidden');
        return;
      }
      debounceTimer = setTimeout(() => {
        fetch(`/api/contacts/search/?q=${encodeURIComponent(q)}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.length === 0) {
              suggestions.classList.add('hidden');
              return;
            }
            suggestions.innerHTML = data
              .map(
                (c) =>
                  `<div class="suggestion-item px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 cursor-pointer" data-email="${c.email}">${c.label}</div>`,
              )
              .join('');
            suggestions.classList.remove('hidden');
          });
      }, 200);
    });

    suggestions.addEventListener('click', (e) => {
      const item = e.target.closest('.suggestion-item');
      if (item) {
        addEmail(item.dataset.email);
      }
    });

    document.addEventListener('click', (e) => {
      if (!suggestions.contains(e.target) && e.target !== input) {
        suggestions.classList.add('hidden');
      }
    });

    if (emails.length > 0) renderTags();
  }

  setupAutocomplete(
    'to-input',
    'to-suggestions',
    'to-hidden',
    'to-tags',
  );
  setupAutocomplete(
    'cc-input',
    'cc-suggestions',
    'cc-hidden',
    'cc-tags',
  );

  // ── Signature loading ──
  const sigSelect = document.getElementById('signature-select');
  const sigPreview = document.getElementById('signature-preview');

  if (sigSelect) {
    sigSelect.addEventListener('change', () => {
      const sigId = sigSelect.value;
      if (!sigId) {
        sigPreview.innerHTML = '';
        return;
      }
      fetch(`/mail/signatures/${sigId}/content/`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((r) => r.json())
        .then((data) => {
          sigPreview.innerHTML = `<div class="border-t border-gray-100 pt-2 text-sm text-gray-500">${data.html}</div>`;
        });
    });
  }

  // ── Attachments ──
  const attachmentList = document.getElementById('attachment-list');
  const localFileInput = document.getElementById('local-file-input');
  const djancloudBtn = document.getElementById('djancloud-attach-btn');

  // Track attachments: { type: 'local'|'djancloud', file?, fileId?, name, size }
  let attachments = [];

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  }

  function renderAttachments() {
    attachmentList.innerHTML = '';
    attachments.forEach((att, i) => {
      const el = document.createElement('div');
      el.className =
        'inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-700';
      const icon =
        att.type === 'djancloud'
          ? '<svg class="w-3.5 h-3.5 text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>'
          : '<svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>';
      el.innerHTML = `${icon} ${att.name} <span class="text-xs text-gray-400">(${formatSize(att.size)})</span><button type="button" data-rm="${i}" class="ml-1 text-gray-400 hover:text-red-500">&times;</button>`;
      attachmentList.appendChild(el);
    });
  }

  attachmentList.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-rm]');
    if (btn) {
      attachments.splice(parseInt(btn.dataset.rm), 1);
      renderAttachments();
    }
  });

  // Local file upload
  if (localFileInput) {
    localFileInput.addEventListener('change', () => {
      for (const f of localFileInput.files) {
        attachments.push({
          type: 'local',
          file: f,
          name: f.name,
          size: f.size,
        });
      }
      localFileInput.value = '';
      renderAttachments();
    });
  }

  // ── Djancloud file picker ──
  const pickerModal = document.getElementById('file-picker-modal');
  const pickerBreadcrumb = document.getElementById('picker-breadcrumb');
  const pickerContents = document.getElementById('picker-contents');
  const pickerAttachBtn = document.getElementById('file-picker-attach');
  let selectedFiles = []; // { id, name, size }

  function openPicker() {
    selectedFiles = [];
    pickerAttachBtn.disabled = true;
    pickerModal.classList.remove('hidden');
    pickerModal.classList.add('flex');
    navigatePicker(null);
  }

  function closePicker() {
    pickerModal.classList.remove('flex');
    pickerModal.classList.add('hidden');
  }

  function navigatePicker(folderId) {
    const url = folderId
      ? `/api/filepicker/${folderId}/`
      : '/api/filepicker/';
    fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then((r) => r.json())
      .then((data) => renderPicker(data));
  }

  function renderPicker(data) {
    // Breadcrumb
    pickerBreadcrumb.innerHTML = data.breadcrumbs
      .map(
        (bc, i) =>
          `${i > 0 ? '<svg class="w-3 h-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>' : ''}<button type="button" class="picker-nav text-sm hover:text-brand-600" data-folder-id="${bc.id}">${bc.name}</button>`,
      )
      .join('');

    let html = '';

    // Shared folders (only at root)
    if (data.shared) {
      data.shared.forEach((s) => {
        html += `<div class="picker-nav flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer" data-folder-id="${s.id}">
          <svg class="w-5 h-5 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
          <span class="text-sm font-medium text-gray-700">${s.name}</span>
          <span class="text-xs text-gray-400 ml-auto">Shared</span>
        </div>`;
      });
    }

    // Items
    data.items.forEach((item) => {
      if (item.type === 'folder') {
        html += `<div class="picker-nav flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer" data-folder-id="${item.id}">
          <svg class="w-5 h-5 text-yellow-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
          </svg>
          <span class="text-sm text-gray-700">${item.name}</span>
        </div>`;
      } else {
        const isSelected = selectedFiles.some((f) => f.id === item.id);
        html += `<div class="picker-file flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer ${isSelected ? 'bg-brand-50 ring-1 ring-brand-200' : ''}" data-file-id="${item.id}" data-file-name="${item.name}" data-file-size="${item.size}">
          <svg class="w-5 h-5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/>
          </svg>
          <span class="text-sm text-gray-700 flex-1">${item.name}</span>
          <span class="text-xs text-gray-400">${formatSize(item.size)}</span>
          ${isSelected ? '<svg class="w-4 h-4 text-brand-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' : ''}
        </div>`;
      }
    });

    if (!html) {
      html =
        '<div class="px-4 py-8 text-center text-sm text-gray-400">Empty folder</div>';
    }

    pickerContents.innerHTML = html;
  }

  // Event delegation for picker
  if (pickerModal) {
    pickerContents.addEventListener('click', (e) => {
      // Navigate into folder
      const folderEl = e.target.closest('.picker-nav');
      if (folderEl) {
        navigatePicker(folderEl.dataset.folderId);
        return;
      }
      // Select/deselect file
      const fileEl = e.target.closest('.picker-file');
      if (fileEl) {
        const fid = parseInt(fileEl.dataset.fileId);
        const idx = selectedFiles.findIndex((f) => f.id === fid);
        if (idx >= 0) {
          selectedFiles.splice(idx, 1);
        } else {
          selectedFiles.push({
            id: fid,
            name: fileEl.dataset.fileName,
            size: parseInt(fileEl.dataset.fileSize),
          });
        }
        pickerAttachBtn.disabled = selectedFiles.length === 0;
        // Re-render selection state
        pickerContents
          .querySelectorAll('.picker-file')
          .forEach((el) => {
            const id = parseInt(el.dataset.fileId);
            const sel = selectedFiles.some((f) => f.id === id);
            el.classList.toggle('bg-brand-50', sel);
            el.classList.toggle('ring-1', sel);
            el.classList.toggle('ring-brand-200', sel);
            const check = el.querySelector('svg[fill="currentColor"]');
            if (sel && !check) {
              el.insertAdjacentHTML(
                'beforeend',
                '<svg class="w-4 h-4 text-brand-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>',
              );
            } else if (!sel && check) {
              check.remove();
            }
          });
      }
    });

    pickerBreadcrumb.addEventListener('click', (e) => {
      const nav = e.target.closest('.picker-nav');
      if (nav) navigatePicker(nav.dataset.folderId);
    });

    djancloudBtn.addEventListener('click', openPicker);
    document
      .getElementById('file-picker-close')
      .addEventListener('click', closePicker);
    document
      .getElementById('file-picker-cancel')
      .addEventListener('click', closePicker);
    pickerModal.addEventListener('click', (e) => {
      if (e.target === pickerModal) closePicker();
    });

    pickerAttachBtn.addEventListener('click', () => {
      selectedFiles.forEach((sf) => {
        if (!attachments.some((a) => a.type === 'djancloud' && a.fileId === sf.id)) {
          attachments.push({
            type: 'djancloud',
            fileId: sf.id,
            name: sf.name,
            size: sf.size,
          });
        }
      });
      renderAttachments();
      closePicker();
    });
  }

  // ── Form submission ──
  const form = document.getElementById('compose-form');
  form.setAttribute('enctype', 'multipart/form-data');

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    // Collect editor HTML + signature into hidden field
    let html = editor.innerHTML;
    if (sigPreview && sigPreview.innerHTML.trim()) {
      html += '<br>' + sigPreview.innerHTML;
    }
    document.getElementById('body-html-hidden').value = html;

    // Ensure to field has current input value
    const toInput = document.getElementById('to-input');
    const toHidden = document.getElementById('to-hidden');
    if (toInput.value.trim()) {
      const current = toHidden.value ? toHidden.value + ', ' : '';
      toHidden.value = current + toInput.value.trim();
    }

    const ccInput = document.getElementById('cc-input');
    const ccHidden = document.getElementById('cc-hidden');
    if (ccInput && ccInput.value.trim()) {
      const current = ccHidden.value ? ccHidden.value + ', ' : '';
      ccHidden.value = current + ccInput.value.trim();
    }

    // Build FormData with attachments
    const formData = new FormData(form);

    // Remove the file input from formData (it's empty), add actual files
    formData.delete('attachments');
    attachments.forEach((att) => {
      if (att.type === 'local' && att.file) {
        formData.append('attachments', att.file);
      }
    });

    // Djancloud file IDs
    const djIds = attachments
      .filter((a) => a.type === 'djancloud')
      .map((a) => a.fileId)
      .join(',');
    formData.set('djancloud_file_ids', djIds);

    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) {
          window.location.href = '/mail/?mailbox=Sent';
        } else {
          sendBtn.disabled = false;
          sendBtn.textContent = 'Send';
          alert(data.error || 'Failed to send email.');
        }
      })
      .catch(() => {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
        alert('Failed to send email.');
      });
  });
});
