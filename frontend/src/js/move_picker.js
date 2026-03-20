import { createApp } from 'vue';
import MovePickerApp from '../components/MovePickerApp.vue';

const el = document.getElementById('move-picker-app');
if (el) {
  createApp(MovePickerApp, {
    initialFolderId: parseInt(el.dataset.initialFolderId),
    itemToMoveId: el.dataset.itemToMoveId ? parseInt(el.dataset.itemToMoveId) : null,
    csrfToken: el.dataset.csrfToken,
  }).mount(el);
}
