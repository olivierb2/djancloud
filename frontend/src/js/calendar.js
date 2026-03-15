import { createApp } from 'vue';
import CalendarApp from '../components/CalendarApp.vue';
import '../css/calendar.css';

const el = document.getElementById('calendar-app');
if (el) {
  const app = createApp(CalendarApp, {
    eventsUrl: el.dataset.eventsUrl,
    createUrl: el.dataset.createUrl || '',
    canWrite: el.dataset.canWrite === 'true',
    calendarColor: el.dataset.calendarColor || '#3498db',
    csrfToken: el.dataset.csrfToken,
  });
  app.mount(el);
}
