// Read Django context
var pageData = JSON.parse(document.getElementById('page-data').textContent);
var currentFolderId = pageData.currentFolderId;
var itemToMoveId = pageData.itemToMoveId;

function navigateToFolder(folderId) {
    if (itemToMoveId && folderId === itemToMoveId) { alert('Cannot move folder into itself.'); return; }
    fetch('/api/folders/' + folderId + '/')
        .then(r => r.json())
        .then(data => { updateFolderView(data); currentFolderId = folderId; document.getElementById('destination-folder-id').value = folderId; });
}
window.navigateToFolder = navigateToFolder;

function navigateToRoot() {
    fetch('/api/folders/')
        .then(r => r.json())
        .then(data => { updateFolderView(data); currentFolderId = data.folder.id; document.getElementById('destination-folder-id').value = data.folder.id; });
}
window.navigateToRoot = navigateToRoot;

function updateFolderView(data) {
    document.getElementById('current-location').textContent = data.folder.name;
    const bc = document.getElementById('breadcrumb-container');
    bc.innerHTML = '';
    for (let i = 1; i < data.breadcrumbs.length; i++) {
        const b = data.breadcrumbs[i];
        const sep = document.createElement('span');
        sep.innerHTML = '<svg class="inline w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>';
        bc.appendChild(sep);
        const a = document.createElement('a');
        a.href = '#'; a.className = 'hover:text-brand-600'; a.textContent = b.name;
        a.onclick = (e) => { e.preventDefault(); navigateToFolder(b.id); };
        bc.appendChild(a);
    }
    const fl = document.getElementById('folder-list');
    fl.innerHTML = '';
    if (data.subfolders.length === 0) {
        fl.innerHTML = '<div class="px-4 py-8 text-center text-sm text-gray-400">No subfolders</div>';
    } else {
        data.subfolders.forEach(f => {
            if (itemToMoveId && f.id === itemToMoveId) return;
            const div = document.createElement('div');
            div.className = 'flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800';
            div.onclick = () => navigateToFolder(f.id);
            div.innerHTML = '<svg class="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 24 24"><path d="M10 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2h-8l-2-2z"/></svg>' +
                f.name + '<svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>';
            fl.appendChild(div);
        });
    }

    // Shared folders section
    const sharedSection = document.getElementById('shared-section');
    if (data.shared_folders && data.shared_folders.length > 0) {
        let html = '<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Shared</h3>';
        html += '<div class="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">';
        data.shared_folders.forEach(sf => {
            html += '<div onclick="navigateToFolder(' + sf.id + ')" class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800">' +
                '<svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>' +
                sf.name +
                '<svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg></div>';
        });
        html += '</div>';
        sharedSection.innerHTML = html;
    } else {
        sharedSection.innerHTML = '';
    }

    // Contact folders section
    const contactsSection = document.getElementById('contacts-section');
    if (data.contact_folders && data.contact_folders.length > 0) {
        let html = '<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Shared with contact</h3>';
        html += '<div class="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">';
        data.contact_folders.forEach(cf => {
            html += '<div onclick="navigateToFolder(' + cf.id + ')" class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800">' +
                '<svg class="w-5 h-5 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>' +
                cf.name +
                '<svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg></div>';
        });
        html += '</div>';
        contactsSection.innerHTML = html;
    } else {
        contactsSection.innerHTML = '';
    }
}

document.addEventListener('DOMContentLoaded', () => { document.getElementById('destination-folder-id').value = currentFolderId; });
