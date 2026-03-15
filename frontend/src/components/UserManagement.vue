<template>
  <!-- User table -->
  <div class="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
    <table class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Username</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Name</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Email</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Role</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Active</th>
          <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100">
        <tr v-for="u in users" :key="u.id">
          <td class="px-4 py-2.5 text-sm font-medium text-gray-900">{{ u.username }}</td>
          <td class="px-4 py-2.5 text-sm text-gray-500">{{ u.full_name || '\u2014' }}</td>
          <td class="px-4 py-2.5 text-sm text-gray-500">{{ u.email || '\u2014' }}</td>
          <td class="px-4 py-2.5">
            <span :class="u.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'"
                  class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
              {{ u.role }}
            </span>
          </td>
          <td class="px-4 py-2.5">
            <span v-if="u.is_active" class="text-green-600 text-xs font-medium">Active</span>
            <span v-else class="text-red-600 text-xs font-medium">Disabled</span>
          </td>
          <td class="px-4 py-2.5 text-right">
            <div class="flex items-center justify-end gap-1">
              <button @click="openEdit(u)" title="Edit"
                      class="rounded p-1 text-gray-400 hover:text-brand-600 hover:bg-gray-100">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
              </button>
              <button @click="deleteUser(u)" title="Delete"
                      class="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Add user modal -->
  <teleport to="body">
    <div v-if="showAddModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showAddModal = false">
      <div class="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Add user</h3>
        <div v-if="addError" class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 border border-red-200">{{ addError }}</div>
        <form @submit.prevent="addUser">
          <div class="space-y-3">
            <input v-model="newUser.username" type="text" required placeholder="Username"
                   class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            <div class="grid grid-cols-2 gap-3">
              <input v-model="newUser.first_name" type="text" placeholder="First name"
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
              <input v-model="newUser.last_name" type="text" placeholder="Last name"
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            </div>
            <input v-model="newUser.email" type="email" placeholder="Email"
                   class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            <input v-model="newUser.password" type="password" required placeholder="Password"
                   class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            <select v-model="newUser.role"
                    class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div class="flex justify-end gap-2 mt-4">
            <button type="button" @click="showAddModal = false"
                    class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
            <button type="submit"
                    class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Create</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Edit user modal -->
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showEditModal = false">
      <div class="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Edit &mdash; {{ editUser.username }}</h3>
        <div v-if="editError" class="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 border border-red-200">{{ editError }}</div>
        <form @submit.prevent="saveEdit">
          <div class="space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <input v-model="editUser.first_name" type="text" placeholder="First name"
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
              <input v-model="editUser.last_name" type="text" placeholder="Last name"
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            </div>
            <input v-model="editUser.email" type="email" placeholder="Email"
                   class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            <input v-model="editUser.password" type="password" placeholder="New password (leave blank to keep)"
                   class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            <select v-model="editUser.role"
                    class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <label class="flex items-center gap-2 text-sm text-gray-600">
              <input v-model="editUser.is_active" type="checkbox" class="rounded border-gray-300 text-brand-600 focus:ring-brand-500">
              Active
            </label>
          </div>
          <div class="flex justify-end gap-2 mt-4">
            <button type="button" @click="showEditModal = false"
                    class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
            <button type="submit"
                    class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Save</button>
          </div>
        </form>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  props: {
    csrfToken: String,
    initialUsers: { type: String, default: '[]' },
  },

  data() {
    return {
      users: JSON.parse(this.initialUsers),
      showAddModal: false,
      showEditModal: false,
      addError: '',
      editError: '',
      newUser: { username: '', first_name: '', last_name: '', email: '', password: '', role: 'user' },
      editUser: { id: null, username: '', first_name: '', last_name: '', email: '', password: '', role: 'user', is_active: true },
    };
  },

  methods: {
    openAdd() {
      this.newUser = { username: '', first_name: '', last_name: '', email: '', password: '', role: 'user' };
      this.addError = '';
      this.showAddModal = true;
    },

    addUser() {
      this.addError = '';
      fetch('/api/users/create/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify(this.newUser),
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) { this.addError = data.error; return; }
          this.showAddModal = false;
          this.loadUsers();
        });
    },

    openEdit(u) {
      this.editUser = { id: u.id, username: u.username, first_name: u.first_name, last_name: u.last_name, email: u.email, password: '', role: u.role, is_active: u.is_active };
      this.editError = '';
      this.showEditModal = true;
    },

    saveEdit() {
      this.editError = '';
      const payload = {
        first_name: this.editUser.first_name,
        last_name: this.editUser.last_name,
        email: this.editUser.email,
        role: this.editUser.role,
        is_active: this.editUser.is_active,
      };
      if (this.editUser.password) payload.password = this.editUser.password;

      fetch(`/api/users/${this.editUser.id}/update/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify(payload),
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) { this.editError = data.error; return; }
          this.showEditModal = false;
          this.loadUsers();
        });
    },

    deleteUser(u) {
      if (!confirm(`Delete user "${u.username}"? All their files will be deleted.`)) return;
      fetch(`/api/users/${u.id}/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': this.csrfToken },
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) { alert(data.error); return; }
          this.users = this.users.filter(x => x.id !== u.id);
        });
    },

    loadUsers() {
      fetch('/api/users/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => r.json())
        .then(data => { this.users = data.users; });
    },
  },
};
</script>
