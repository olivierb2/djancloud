import { createApp } from 'vue';
import UserManagement from '../components/UserManagement.vue';

const el = document.getElementById('users-app');
if (el) {
  const app = createApp(UserManagement, {
    csrfToken: el.dataset.csrfToken,
    initialUsers: el.dataset.users || '[]',
  });

  // Expose openAdd method so the Django template button can trigger it
  const vm = app.mount(el);
  window.openAddUserModal = () => vm.openAdd();
}
