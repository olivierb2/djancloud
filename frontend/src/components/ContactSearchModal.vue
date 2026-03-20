<template>
  <teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="close">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Add a contact</h3>
        <div class="relative mb-4">
          <input
            ref="searchInput"
            v-model="query"
            type="text"
            placeholder="Search by name or email..."
            class="block w-full rounded-lg border border-gray-300 pl-9 pr-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
            @input="onSearch"
            @keydown.esc="close"
          >
          <svg class="w-4 h-4 absolute left-3 top-2.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>
        <div class="max-h-64 overflow-y-auto divide-y divide-gray-100 rounded-lg border border-gray-200">
          <div v-if="results === null" />
          <div v-else-if="results.length === 0" class="px-4 py-3 text-sm text-gray-400 text-center">No contacts found</div>
          <button
            v-for="c in results"
            :key="c.id"
            type="button"
            class="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-50 transition-colors"
            @click="selectContact(c.id)"
          >
            <svg class="w-5 h-5 text-teal-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 truncate">{{ c.name || c.email }}</div>
              <div v-if="c.email" class="text-xs text-gray-500 truncate">{{ c.email }}</div>
            </div>
          </button>
        </div>
        <div class="flex justify-end mt-4">
          <button type="button" @click="close"
                  class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
import { defineComponent, ref, nextTick } from 'vue';

export default defineComponent({
  name: 'ContactSearchModal',
  setup() {
    const visible = ref(false);
    const query = ref('');
    const results = ref(null);
    const searchInput = ref(null);
    let searchTimer = null;

    function open() {
      visible.value = true;
      query.value = '';
      results.value = null;
      nextTick(() => {
        if (searchInput.value) searchInput.value.focus();
      });
    }

    function close() {
      visible.value = false;
    }

    function onSearch() {
      clearTimeout(searchTimer);
      const q = query.value.trim();
      if (q.length < 1) { results.value = null; return; }
      searchTimer = setTimeout(() => {
        fetch(`/api/contacts/search/?q=${encodeURIComponent(q)}`)
          .then(r => r.json())
          .then(data => { results.value = data; });
      }, 300);
    }

    function selectContact(contactId) {
      const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
      const csrfToken = csrfEl ? csrfEl.value : '';
      fetch('/api/contact-folders/create/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ contact_id: contactId }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) {
            alert(data.error);
          } else {
            close();
            window.location.href = '/browse/' + data.url_path;
          }
        })
        .catch(err => console.error('Error creating contact folder:', err));
    }

    return { visible, query, results, searchInput, open, close, onSearch, selectContact };
  },
});
</script>
