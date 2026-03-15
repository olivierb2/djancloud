<template>
  <div ref="calendarEl" id="fullcalendar"></div>

  <!-- Event create modal -->
  <teleport to="body">
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showCreateModal = false">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-4">New event</h3>
        <form @submit.prevent="createEvent">
          <input v-model="newEvent.summary" type="text" required placeholder="Event title" autofocus
                 class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none mb-3">
          <label class="flex items-center gap-2 mb-3 text-sm text-gray-600">
            <input v-model="newEvent.allDay" type="checkbox" class="rounded border-gray-300 text-brand-600 focus:ring-brand-500">
            All day
          </label>
          <div class="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label class="block text-xs text-gray-500 mb-1">Start</label>
              <input v-model="newEvent.dtstart" :type="newEvent.allDay ? 'date' : 'datetime-local'" required
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1">End</label>
              <input v-model="newEvent.dtend" :type="newEvent.allDay ? 'date' : 'datetime-local'"
                     class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none">
            </div>
          </div>
          <input v-model="newEvent.description" type="text" placeholder="Description (optional)"
                 class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none mb-3">
          <input v-model="newEvent.location" type="text" placeholder="Location (optional)"
                 class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none mb-4">
          <div class="flex justify-end gap-2">
            <button type="button" @click="showCreateModal = false"
                    class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
            <button type="submit"
                    class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">Create</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Event detail modal -->
    <div v-if="showDetailModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showDetailModal = false">
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
        <h3 class="text-lg font-semibold text-gray-900 mb-2">{{ selectedEvent.title || '(No title)' }}</h3>
        <div class="space-y-1 text-sm text-gray-600 mb-4">
          <p><span class="font-medium text-gray-500">Start:</span> {{ selectedEvent.startStr }}</p>
          <p v-if="selectedEvent.endStr"><span class="font-medium text-gray-500">End:</span> {{ selectedEvent.endStr }}</p>
          <p v-if="selectedEvent.location"><span class="font-medium text-gray-500">Location:</span> {{ selectedEvent.location }}</p>
          <p v-if="selectedEvent.description" class="mt-2 text-gray-700">{{ selectedEvent.description }}</p>
        </div>
        <div class="flex justify-between">
          <button v-if="selectedEvent.deleteUrl" type="button" @click="deleteEvent"
                  class="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
            Delete
          </button>
          <button type="button" @click="showDetailModal = false"
                  class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 ml-auto">Close</button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
import { Calendar } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';

export default {
  props: {
    eventsUrl: String,
    createUrl: String,
    canWrite: Boolean,
    calendarColor: { type: String, default: '#3498db' },
    csrfToken: String,
  },

  data() {
    return {
      calendar: null,
      showCreateModal: false,
      showDetailModal: false,
      newEvent: { summary: '', allDay: false, dtstart: '', dtend: '', description: '', location: '' },
      selectedEvent: { title: '', startStr: '', endStr: '', location: '', description: '', deleteUrl: '' },
    };
  },

  mounted() {
    this.calendar = new Calendar(this.$refs.calendarEl, {
      plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
      initialView: 'dayGridMonth',
      headerToolbar: {
        left: 'prev,today,next',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
      },
      locale: document.documentElement.lang || 'en',
      height: 'auto',
      navLinks: true,
      editable: false,
      selectable: this.canWrite,
      nowIndicator: true,
      eventColor: this.calendarColor,

      events: (info, success, failure) => {
        const params = new URLSearchParams({ start: info.startStr, end: info.endStr });
        fetch(this.eventsUrl + '?' + params, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(r => r.json()).then(success).catch(failure);
      },

      select: (info) => {
        if (!this.canWrite) return;
        this.newEvent = { summary: '', description: '', location: '', allDay: info.allDay, dtstart: '', dtend: '' };
        if (info.allDay) {
          this.newEvent.dtstart = info.startStr;
          const end = new Date(info.end);
          end.setDate(end.getDate() - 1);
          this.newEvent.dtend = end.toISOString().split('T')[0];
        } else {
          this.newEvent.dtstart = info.startStr.slice(0, 16);
          this.newEvent.dtend = info.endStr.slice(0, 16);
        }
        this.showCreateModal = true;
        this.calendar.unselect();
      },

      eventClick: (info) => {
        const ev = info.event;
        this.selectedEvent = {
          title: ev.title,
          startStr: ev.allDay ? ev.start.toLocaleDateString() : ev.start.toLocaleString(),
          endStr: ev.end ? (ev.allDay ? ev.end.toLocaleDateString() : ev.end.toLocaleString()) : '',
          location: ev.extendedProps.location || '',
          description: ev.extendedProps.description || '',
          deleteUrl: ev.extendedProps.deleteUrl || '',
        };
        this.showDetailModal = true;
      },
    });
    this.calendar.render();
  },

  methods: {
    createEvent() {
      const form = new FormData();
      form.append('csrfmiddlewaretoken', this.csrfToken);
      form.append('summary', this.newEvent.summary);
      form.append('description', this.newEvent.description);
      form.append('location', this.newEvent.location);
      form.append('dtstart', this.newEvent.dtstart);
      form.append('dtend', this.newEvent.dtend);
      if (this.newEvent.allDay) form.append('all_day', 'on');

      fetch(this.createUrl, {
        method: 'POST',
        body: form,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(() => {
        this.showCreateModal = false;
        this.calendar.refetchEvents();
      });
    },

    deleteEvent() {
      if (!confirm('Delete this event?')) return;
      const form = new FormData();
      form.append('csrfmiddlewaretoken', this.csrfToken);
      fetch(this.selectedEvent.deleteUrl, {
        method: 'POST',
        body: form,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(() => {
        this.showDetailModal = false;
        this.calendar.refetchEvents();
      });
    },
  },
};
</script>
