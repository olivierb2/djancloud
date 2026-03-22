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
                 class="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none mb-3">

          <!-- Invitees -->
          <div class="mb-4">
            <label class="block text-xs text-gray-500 mb-1">Invite people</label>
            <div class="flex flex-wrap items-center gap-1 rounded-lg border border-gray-300 px-2 py-1.5 min-h-[2.25rem]">
              <span v-for="(inv, i) in newEvent.invitees" :key="i"
                    class="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">
                {{ inv.name || inv.email }}
                <button type="button" @click="newEvent.invitees.splice(i, 1)" class="text-brand-500 hover:text-brand-700">&times;</button>
              </span>
              <input type="text" v-model="inviteeQuery" placeholder="Type name or email..."
                     class="flex-1 min-w-[150px] border-0 p-0 text-sm outline-none focus:ring-0"
                     @input="searchInvitees" @keydown.enter.prevent="addInviteeFromQuery"
                     @keydown.comma.prevent="addInviteeFromQuery">
            </div>
            <div v-if="inviteeSuggestions.length" class="mt-1 max-h-32 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg z-50">
              <button v-for="c in inviteeSuggestions" :key="c.email" type="button"
                      @click="addInvitee(c)"
                      class="block w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100">
                {{ c.label }}
              </button>
            </div>
          </div>

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

        <!-- Invitees -->
        <div v-if="selectedEvent.invitees && selectedEvent.invitees.length" class="mb-4 border-t border-gray-100 pt-3">
          <h4 class="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Invitees</h4>
          <div class="space-y-1">
            <div v-for="inv in selectedEvent.invitees" :key="inv.id" class="flex items-center justify-between text-sm">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full flex-shrink-0"
                      :class="{
                        'bg-green-500': inv.status === 'accepted',
                        'bg-red-500': inv.status === 'declined',
                        'bg-yellow-500': inv.status === 'tentative',
                        'bg-gray-400': inv.status === 'needs-action',
                      }"></span>
                <span class="text-gray-700">{{ inv.name || inv.email }}</span>
                <span v-if="inv.name" class="text-gray-400 text-xs">{{ inv.email }}</span>
              </div>
              <button v-if="canWrite" type="button" @click="removeInvitee(inv.id)"
                      class="text-xs text-red-500 hover:text-red-700">Remove</button>
            </div>
          </div>
        </div>

        <!-- Add invitee to existing event -->
        <div v-if="canWrite" class="mb-4 border-t border-gray-100 pt-3">
          <div class="flex gap-2">
            <div class="relative flex-1">
              <input type="text" v-model="detailInviteeQuery" placeholder="Add invitee..."
                     class="block w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
                     @input="searchDetailInvitees" @keydown.enter.prevent="addDetailInviteeFromQuery">
              <div v-if="detailInviteeSuggestions.length" class="absolute left-0 top-full mt-1 w-full max-h-32 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg z-50">
                <button v-for="c in detailInviteeSuggestions" :key="c.email" type="button"
                        @click="addDetailInvitee(c)"
                        class="block w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100">
                  {{ c.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Move to another calendar -->
        <div v-if="otherCalendars.length > 0 && canWrite" class="flex items-center gap-2 mb-4 border-t border-gray-100 pt-3">
          <label class="text-sm text-gray-500 flex-shrink-0">Move to</label>
          <select v-model="moveToCalendarId" class="flex-1 rounded-lg border border-gray-300 px-2 py-1.5 text-sm">
            <option value="">Select calendar...</option>
            <option v-for="c in otherCalendars" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <button type="button" @click="moveEvent" :disabled="!moveToCalendarId"
                  class="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50">Move</button>
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
    calendarsJson: { type: String, default: '[]' },
    currentCalendarId: { type: [String, Number], default: '' },
  },

  data() {
    return {
      calendar: null,
      showCreateModal: false,
      showDetailModal: false,
      newEvent: { summary: '', allDay: false, dtstart: '', dtend: '', description: '', location: '', invitees: [] },
      inviteeQuery: '',
      inviteeSuggestions: [],
      selectedEvent: { title: '', startStr: '', endStr: '', location: '', description: '', deleteUrl: '', eventId: '', invitees: [] },
      detailInviteeQuery: '',
      detailInviteeSuggestions: [],
      moveToCalendarId: '',
    };
  },

  computed: {
    otherCalendars() {
      try {
        const all = JSON.parse(this.calendarsJson);
        return all.filter(c => String(c.id) !== String(this.currentCalendarId));
      } catch { return []; }
    },
  },

  mounted() {
    this.calendar = new Calendar(this.$refs.calendarEl, {
      plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
      initialView: 'timeGridWeek',
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
        this.newEvent = { summary: '', description: '', location: '', allDay: info.allDay, dtstart: '', dtend: '', invitees: [] };
        this.inviteeQuery = '';
        this.inviteeSuggestions = [];
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
          eventId: ev.id,
          invitees: ev.extendedProps.invitees || [],
        };
        this.moveToCalendarId = '';
        this.detailInviteeQuery = '';
        this.detailInviteeSuggestions = [];
        this.showDetailModal = true;
      },
    });
    this.calendar.render();
  },

  methods: {
    // --- Invitee helpers ---
    searchInvitees() {
      clearTimeout(this._invTimer);
      const q = this.inviteeQuery.trim();
      if (q.length < 1) { this.inviteeSuggestions = []; return; }
      this._invTimer = setTimeout(() => {
        fetch(`/api/contacts/search/?q=${encodeURIComponent(q)}`)
          .then(r => r.json())
          .then(data => { this.inviteeSuggestions = data; });
      }, 200);
    },

    addInvitee(contact) {
      if (!this.newEvent.invitees.some(i => i.email === contact.email)) {
        this.newEvent.invitees.push({ name: contact.name, email: contact.email });
      }
      this.inviteeQuery = '';
      this.inviteeSuggestions = [];
    },

    addInviteeFromQuery() {
      const q = this.inviteeQuery.trim();
      if (q && q.includes('@')) {
        this.addInvitee({ name: '', email: q });
      }
    },

    searchDetailInvitees() {
      clearTimeout(this._detInvTimer);
      const q = this.detailInviteeQuery.trim();
      if (q.length < 1) { this.detailInviteeSuggestions = []; return; }
      this._detInvTimer = setTimeout(() => {
        fetch(`/api/contacts/search/?q=${encodeURIComponent(q)}`)
          .then(r => r.json())
          .then(data => { this.detailInviteeSuggestions = data; });
      }, 200);
    },

    addDetailInvitee(contact) {
      this.detailInviteeQuery = '';
      this.detailInviteeSuggestions = [];
      fetch(`/api/events/${this.selectedEvent.eventId}/invitees/add/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
        body: JSON.stringify({ email: contact.email, name: contact.name || '' }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) { alert(data.error); return; }
          this.selectedEvent.invitees.push(data);
          this.calendar.refetchEvents();
        });
    },

    addDetailInviteeFromQuery() {
      const q = this.detailInviteeQuery.trim();
      if (q && q.includes('@')) {
        this.addDetailInvitee({ name: '', email: q });
      }
    },

    removeInvitee(inviteeId) {
      fetch(`/api/events/${this.selectedEvent.eventId}/invitees/${inviteeId}/remove/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': this.csrfToken },
      })
        .then(r => r.json())
        .then(data => {
          if (data.ok) {
            this.selectedEvent.invitees = this.selectedEvent.invitees.filter(i => i.id !== inviteeId);
            this.calendar.refetchEvents();
          }
        });
    },

    createEvent() {
      const form = new FormData();
      form.append('csrfmiddlewaretoken', this.csrfToken);
      form.append('summary', this.newEvent.summary);
      form.append('description', this.newEvent.description);
      form.append('location', this.newEvent.location);
      form.append('dtstart', this.newEvent.dtstart);
      form.append('dtend', this.newEvent.dtend);
      if (this.newEvent.allDay) form.append('all_day', 'on');
      const inviteeStrs = this.newEvent.invitees.map(i => i.name ? `${i.name} <${i.email}>` : i.email);
      form.append('invitees', inviteeStrs.join(', '));

      fetch(this.createUrl, {
        method: 'POST',
        body: form,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(() => {
        this.showCreateModal = false;
        this.calendar.refetchEvents();
      });
    },

    moveEvent() {
      if (!this.moveToCalendarId || !this.selectedEvent.eventId) return;
      fetch('/api/events/' + this.selectedEvent.eventId + '/move/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
        },
        body: JSON.stringify({ calendar_id: parseInt(this.moveToCalendarId) }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) { alert(data.error); return; }
          this.showDetailModal = false;
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
