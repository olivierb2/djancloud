<template>
  <div>
    <!-- Breadcrumbs -->
    <div class="flex items-center gap-1 text-sm text-gray-500 mb-4 flex-wrap">
      <a href="#" class="hover:text-brand-600" @click.prevent="navigateToFolder(null)">Home</a>
      <template v-for="crumb in breadcrumbs" :key="crumb.id">
        <svg class="inline w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
        </svg>
        <a href="#" class="hover:text-brand-600" @click.prevent="navigateToFolder(crumb.id)">{{ crumb.name }}</a>
      </template>
    </div>

    <!-- Current location label -->
    <p class="text-sm text-gray-600 mb-3">
      Select destination: <span class="font-semibold text-gray-900">{{ currentFolder?.name ?? 'Home' }}</span>
    </p>

    <!-- Folder list -->
    <div class="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">
      <template v-if="subfolders.length > 0">
        <div
          v-for="folder in subfolders"
          :key="folder.id"
          class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800"
          @click="navigateToFolder(folder.id)"
        >
          <svg class="w-5 h-5 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M10 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2h-8l-2-2z"/>
          </svg>
          {{ folder.name }}
          <svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </div>
      </template>
      <div v-else class="px-4 py-8 text-center text-sm text-gray-400">
        No subfolders
      </div>
    </div>

    <!-- Shared folders section (only at root) -->
    <template v-if="sharedFolders.length > 0">
      <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Shared</h3>
      <div class="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">
        <div
          v-for="folder in sharedFolders"
          :key="folder.id"
          class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800"
          @click="navigateToFolder(folder.id)"
        >
          <svg class="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
          {{ folder.name }}
          <svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </div>
      </div>
    </template>

    <!-- Contact folders section (only at root) -->
    <template v-if="contactFolders.length > 0">
      <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Shared with contact</h3>
      <div class="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden mb-6">
        <div
          v-for="folder in contactFolders"
          :key="folder.id"
          class="flex items-center gap-2 px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 text-sm text-gray-800"
          @click="navigateToFolder(folder.id)"
        >
          <svg class="w-5 h-5 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
          </svg>
          {{ folder.name }}
          <svg class="w-4 h-4 text-gray-300 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </div>
      </div>
    </template>

    <!-- Action buttons -->
    <div class="flex items-center gap-3 mt-6">
      <form method="post">
        <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
        <input type="hidden" name="destination_folder_id" :value="destinationFolderId">
        <button type="submit" class="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700">
          Move here
        </button>
      </form>
      <button type="button" class="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50" @click="cancel">
        Cancel
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  initialFolderId: {
    type: Number,
    required: true,
  },
  itemToMoveId: {
    type: Number,
    default: null,
  },
  csrfToken: {
    type: String,
    required: true,
  },
})

const currentFolder = ref(null)
const breadcrumbs = ref([])
const subfolders = ref([])
const sharedFolders = ref([])
const contactFolders = ref([])
const destinationFolderId = ref(null)

/**
 * Navigate to a folder by ID, or to root if folderId is null.
 * Fetches folder data from the API and updates the component state.
 */
async function navigateToFolder(folderId) {
  // Prevent moving a folder into itself
  if (props.itemToMoveId && folderId === props.itemToMoveId) {
    alert('Cannot move folder into itself.')
    return
  }

  const url = folderId ? `/api/folders/${folderId}/` : '/api/folders/'

  try {
    const response = await fetch(url)
    const data = await response.json()

    currentFolder.value = data.folder
    destinationFolderId.value = data.folder.id

    // Build breadcrumbs (skip the first entry which is root/home)
    breadcrumbs.value = data.breadcrumbs ? data.breadcrumbs.slice(1) : []

    // Filter out the item being moved from subfolders
    subfolders.value = (data.subfolders || []).filter(
      (f) => !props.itemToMoveId || f.id !== props.itemToMoveId
    )

    // Shared and contact folders are only present at root level
    sharedFolders.value = data.shared_folders || []
    contactFolders.value = data.contact_folders || []
  } catch (error) {
    console.error('Failed to load folder:', error)
  }
}

/** Go back to the previous page */
function cancel() {
  window.history.back()
}

onMounted(() => {
  destinationFolderId.value = props.initialFolderId
  navigateToFolder(null)
})
</script>
