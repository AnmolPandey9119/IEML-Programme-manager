import {
  api, S, acts, changes, html, icon, raw, val, field, fmtDate, plural, openPanel, confirmDialog, promptDialog,
  copyText, toast, mount, $, $$, esc,
} from './core.js';

export const STATUS_INFO = {
  draft: ['Draft', 'Visible to the team only. Nothing is published on the website.'],
  active: ['Active', 'Live. Published sessions and confirmed speakers appear on the website.'],
  archived: ['Archived', 'Read-only. The programme stays on the website but can no longer be edited.'],
};
const statusPill = (s) => html`<span class="pill ${s}">${STATUS_INFO[s]?.[0] || s}</span>`;

/* ================================================================ events list */
export async function viewEvents(go) {
  const list = await api('/events');
  const span = (e) => (e.start_date ? (e.start_date === e.end_date ? fmtDate(e.start_date) : `${fmtDate(e.start_date)} to ${fmtDate(e.end_date)}`) : 'Dates not set');
  return html`
    <div class="page-head"><div class="t"><h1>Your events</h1>
      <p>Each event is kept completely separate. Sessions, speakers and committees never mix between events.</p></div>
      <div class="actions"><button class="btn primary" data-act="newEvent">${icon('plus', 'sm')} New event</button></div></div>
    ${list.length ? html`<div class="tiles" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">${list.map((e) => html`
      <a class="tile" style="text-decoration:none;color:inherit" href="#/event/${e.id}">
        <div class="tx" style="padding:18px 18px 16px">
          <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start">
            <b style="font-size:18px">${e.name}${e.edition ? html` <span class="muted" style="font-weight:500">${e.edition}</span>` : ''}</b>${statusPill(e.status)}</div>
          <span class="r">${[e.venue_name, e.venue_city].filter(Boolean).join(', ') || 'Venue not set'}</span>
          <span class="s">${icon('calendar', 'sm')} ${span(e)}</span>
          <span class="s">${icon('user', 'sm')} Your role: ${e.my_role}</span>
        </div></a>`)}</div>`
      : html`<div class="panel"><div class="empty"><div class="art">${icon('calendar', 'lg')}</div><h3>Create your first event</h3>
          <p>Set up the event name, dates and halls once. Then add sessions and speakers.</p>
          <button class="btn primary" data-act="newEvent">${icon('plus', 'sm')} New event</button></div></div>`}`;
}

function newEventDialog() {
  const p = openPanel({
    title: 'New event', subtitle: 'You can change any of this later in Event Setup.', wide: true,
    body: html`<div class="grid2">
        ${field('Event name', html`<input id="n_name" placeholder="Bharat Sustainability Summit" data-autofocus>`)}
        ${field('Edition', html`<input id="n_edition" placeholder="2027">`, { optional: true })}
        ${field('Venue name', html`<input id="n_venue" placeholder="India Expo Mart">`, { optional: true })}
        ${field('City', html`<input id="n_city" placeholder="Greater Noida">`, { optional: true })}
        ${field('First day', html`<input id="n_start" type="date">`, { optional: true })}
        ${field('Last day', html`<input id="n_end" type="date">`, { optional: true })}
      </div>
      ${field('Theme line', html`<input id="n_theme" placeholder="A short tagline for the event">`, { optional: true })}
      ${field('Event website address', html`<input id="n_site" placeholder="https://www.example.com">`, { optional: true, hint: 'The public website that will show the live agenda.' })}`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn primary" id="n_ok">Create event</button>`,
  });
  $('#n_ok', p.el).addEventListener('click', async () => {
    try {
      const g = (id) => val(id, p.el);
      const body = { name: g('n_name'), edition: g('n_edition'), venue_name: g('n_venue'), venue_city: g('n_city'), theme_line: g('n_theme'), website_url: g('n_site') };
      if (g('n_start') || g('n_end')) { body.start_date = g('n_start') || null; body.end_date = g('n_end') || null; }
      const ev = await api('/events', 'POST', body);
      p.close(); location.hash = `#/event/${ev.id}/setup`;
    } catch (e) { toast(e.message, 'err'); }
  });
}

/* ================================================================ event setup */
export async function viewSetup({ event: ev }) {
  const admin = ev.my_role === 'admin';
  const dis = admin ? '' : 'disabled';
  const edit = admin && ev.status !== 'archived';
  return html`
  <div class="page-head"><div class="t"><h1>Event setup</h1><p>The basics every session builds on: where and when the event runs, and which halls are in use.</p></div></div>
  ${!admin ? html`<div class="note">${icon('lock', 'sm')}<span>Only an admin can change event setup. You can view everything here.</span></div>` : ''}

  <section class="section"><div class="lead"><h3>Event details</h3><p>These appear on exports and on the public website.</p></div>
    <div class="panel"><div class="pad">
      <div class="grid2">
        ${field('Event name', html`<input id="e_name" value="${ev.name}" ${dis}>`)}
        ${field('Edition', html`<input id="e_edition" value="${ev.edition}" placeholder="2027" ${dis}>`)}
        ${field('Venue name', html`<input id="e_venue" value="${ev.venue_name}" ${dis}>`)}
        ${field('City', html`<input id="e_city" value="${ev.venue_city}" ${dis}>`)}
      </div>
      ${field('Theme line', html`<input id="e_theme" value="${ev.theme_line}" placeholder="The event's tagline or theme" ${dis}>`)}
      ${field('Event website address', html`<input id="e_site" value="${ev.website_url}" placeholder="https://www.example.com" ${dis}>`, { hint: 'The public website where the live agenda is shown.' })}
      ${admin ? html`<button class="btn primary" data-act="saveEvent">Save details</button>` : ''}
    </div></div></section>

  <section class="section"><div class="lead"><h3>Event status</h3><p>Controls who can see the event and whether it can be edited.</p></div>
    <div class="panel"><div class="pad">
      <div class="seg status" id="statusSeg" role="radiogroup">${['draft', 'active', 'archived'].map((k) => html`
        <button type="button" role="radio" aria-checked="${ev.status === k}" class="${ev.status === k ? 'on' : ''}" data-act="pickStatus" data-v="${k}" ${dis}>${STATUS_INFO[k][0]}</button>`)}</div>
      <p class="soft" id="statusText" style="margin-top:12px">${STATUS_INFO[ev.status][1]}</p>
      ${admin ? html`<div style="margin-top:14px"><button class="btn primary" data-act="saveStatus">Save status</button></div>` : ''}
    </div></div></section>

  <section class="section"><div class="lead"><h3>Event days</h3><p>Single or multi-day. Each day is planned on its own, so Day 1 never has to look like Day 2.</p></div>
    <div class="panel"><div class="pad">
      <div class="rows">${ev.days.length ? ev.days.map((d) => html`<div class="row">
          <span class="pill teal num">${fmtDate(d.day_date)}</span><div class="grow"><b>${d.label}</b></div>
          ${edit ? html`<button class="btn sm" data-act="renameDay" data-id="${d.id}">Rename</button>
            <button class="btn sm danger" data-act="deleteDay" data-id="${d.id}">Delete</button>` : ''}</div>`)
        : html`<p class="muted">No days yet. Add the first day below.</p>`}</div>
      ${edit ? html`<div class="inline-form" style="margin-top:16px">
        ${field('Date', html`<input id="d_date" type="date">`)}${field('Label', html`<input id="d_label" placeholder="Leave blank to number it automatically">`)}
        <button class="btn primary" data-act="addDay">${icon('plus', 'sm')} Add day</button></div>` : ''}
    </div></div></section>

  <section class="section"><div class="lead"><h3>Halls and rooms</h3><p>Every hall in use. Sessions are assigned to a hall, or to all halls merged for plenary sessions.</p></div>
    <div class="panel"><div class="pad">
      <div class="rows">${ev.halls.length ? ev.halls.map((h, i) => html`<div class="row">
          <span class="av sm" style="background:var(--primary-soft);color:var(--primary)">${icon('pin', 'sm')}</span><div class="grow"><b>${h.name}</b></div>
          ${edit ? html`<button class="btn icon sm quiet" aria-label="Move up" ${i === 0 ? 'disabled' : ''} data-act="moveHall" data-i="${i}" data-dir="-1">${icon('up2', 'sm')}</button>
            <button class="btn icon sm quiet" aria-label="Move down" ${i === ev.halls.length - 1 ? 'disabled' : ''} data-act="moveHall" data-i="${i}" data-dir="1">${icon('down2', 'sm')}</button>
            <button class="btn sm" data-act="renameHall" data-id="${h.id}">Rename</button>
            <button class="btn sm danger" data-act="deleteHall" data-id="${h.id}">Delete</button>` : ''}</div>`)
        : html`<p class="muted">No halls yet. Add the halls or rooms used by the event.</p>`}</div>
      ${edit ? html`<div class="inline-form" style="margin-top:16px">${field('Hall name', html`<input id="h_name" placeholder="Hall 4" data-enter="addHall">`)}
        <button class="btn primary" data-act="addHall">${icon('plus', 'sm')} Add hall</button></div>` : ''}
    </div></div></section>

  ${admin ? html`<section class="section"><div class="lead"><h3>Delete event</h3><p>Removes the event with all of its sessions, speakers and lists.</p></div>
    <div class="panel"><div class="pad"><p class="soft" style="margin-bottom:12px">This cannot be undone. Consider archiving the event instead.</p>
      <button class="btn danger" data-act="deleteEvent">Delete this event</button></div></div></section>` : ''}`;
}

let pendingStatus = null;
const E = () => S.event;
const refreshNow = () => window.__refresh();
acts({
  newEvent: () => newEventDialog(),
  saveEvent: async () => {
    await api('/events/' + E().id, 'PATCH', { name: val('e_name'), edition: val('e_edition'), venue_name: val('e_venue'),
      venue_city: val('e_city'), website_url: val('e_site'), theme_line: val('e_theme') });
    toast('Event details saved'); await refreshNow();
  },
  pickStatus: (el) => {
    pendingStatus = el.dataset.v;
    $$('#statusSeg button').forEach((b) => { b.classList.toggle('on', b === el); b.setAttribute('aria-checked', b === el); });
    $('#statusText').textContent = STATUS_INFO[pendingStatus][1];
  },
  saveStatus: async () => {
    const st = pendingStatus || E().status;
    if (st === E().status) return toast('Status is already ' + STATUS_INFO[st][0]);
    if (st === 'archived' && !(await confirmDialog({ title: 'Archive this event?', message: 'The event becomes read-only. You can set it back to Active at any time.', confirmLabel: 'Archive event' }))) return;
    await api('/events/' + E().id, 'PATCH', { status: st });
    pendingStatus = null; toast('Status changed to ' + STATUS_INFO[st][0]); await refreshNow();
  },
  addDay: async () => {
    await api(`/events/${E().id}/days`, 'POST', { day_date: val('d_date'), label: val('d_label') || null });
    toast('Day added'); await refreshNow();
  },
  renameDay: async (el) => {
    const d = E().days.find((x) => x.id == el.dataset.id);
    const label = await promptDialog({ title: 'Rename day', label: 'Day label', value: d.label });
    if (label) { await api(`/events/${E().id}/days/${d.id}`, 'PATCH', { label }); await refreshNow(); }
  },
  deleteDay: async (el) => {
    const d = E().days.find((x) => x.id == el.dataset.id);
    if (await confirmDialog({ title: 'Delete this day?', message: `${d.label} will be removed. A day that still has sessions cannot be deleted.`, confirmLabel: 'Delete day', danger: true })) {
      await api(`/events/${E().id}/days/${d.id}`, 'DELETE'); toast('Day deleted'); await refreshNow();
    }
  },
  addHall: async () => { await api(`/events/${E().id}/halls`, 'POST', { name: val('h_name') }); toast('Hall added'); await refreshNow(); },
  renameHall: async (el) => {
    const h = E().halls.find((x) => x.id == el.dataset.id);
    const name = await promptDialog({ title: 'Rename hall', label: 'Hall name', value: h.name });
    if (name) { await api(`/events/${E().id}/halls/${h.id}`, 'PATCH', { name }); await refreshNow(); }
  },
  deleteHall: async (el) => {
    const h = E().halls.find((x) => x.id == el.dataset.id);
    if (await confirmDialog({ title: 'Delete this hall?', message: `${h.name} will be removed. A hall that still has sessions cannot be deleted.`, confirmLabel: 'Delete hall', danger: true })) {
      await api(`/events/${E().id}/halls/${h.id}`, 'DELETE'); toast('Hall deleted'); await refreshNow();
    }
  },
  moveHall: async (el) => {
    const i = +el.dataset.i, dir = +el.dataset.dir, ids = E().halls.map((h) => h.id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    await api(`/events/${E().id}/halls/order`, 'PUT', { ids }); await refreshNow();
  },
  deleteEvent: async () => {
    const name = await promptDialog({ title: 'Delete event', label: `Type the event name to confirm: ${E().name}`, confirmLabel: 'Delete permanently' });
    if (name === null) return;
    if (name !== E().name) return toast('The name did not match, so nothing was deleted.', 'err');
    await api('/events/' + E().id, 'DELETE'); toast('Event deleted'); location.hash = '#/events';
  },
});

/* ================================================================ team */
const NOTIF = {
  speaker_confirmed: ['Speaker confirmed', 'Email the team the moment a speaker’s status changes to Confirmed.'],
  late_change: ['Late change alert', 'Email the team when a session’s time, hall or speakers change within 48 hours of the event day.'],
};
const ROLE_INFO = { admin: 'Full access, including team and settings', editor: 'Creates and edits sessions and speakers', viewer: 'Read-only, can export' };

export async function viewTeam({ event: ev }) {
  const admin = ev.my_role === 'admin';
  const [members, notif] = await Promise.all([api(`/events/${ev.id}/members`), api(`/events/${ev.id}/notification-settings`)]);
  const invites = admin ? await api(`/events/${ev.id}/invitations`) : [];
  return html`
  <div class="page-head"><div class="t"><h1>Team</h1><p>People join by email invitation only. Choose what each person can do and who receives email alerts.</p></div></div>
  <section class="section"><div class="lead"><h3>Members</h3><p>${plural(members.length, 'person', 'people')} on this event.</p></div>
    <div class="panel"><div class="table-wrap"><table class="t"><thead><tr><th>Name</th><th>Role</th><th>Email alerts</th><th></th></tr></thead><tbody>
      ${members.map((m) => html`<tr><td><b>${m.full_name || '—'}</b><div class="muted small">${m.email}</div></td>
        <td>${admin ? html`<select data-change="setRole" data-id="${m.id}" style="width:auto">${['admin', 'editor', 'viewer'].map((r) => html`<option value="${r}" ${m.role === r ? 'selected' : ''}>${r[0].toUpperCase() + r.slice(1)}</option>`)}</select>` : html`<span class="pill">${m.role}</span>`}</td>
        <td><label class="switch"><input type="checkbox" ${m.receive_notifications ? 'checked' : ''} ${admin ? '' : 'disabled'} data-change="setNotify" data-id="${m.id}" aria-label="Email alerts for ${m.full_name}"><i></i></label></td>
        <td class="right">${admin ? html`<button class="btn sm danger" data-act="removeMember" data-id="${m.id}">Remove</button>` : ''}</td></tr>`)}
    </tbody></table></div>
    <div class="pad small muted" style="border-top:1px solid var(--rule-2)">${Object.entries(ROLE_INFO).map(([r, d]) => `${r[0].toUpperCase() + r.slice(1)}: ${d}.`).join('  ')}</div></div></section>

  ${admin ? html`
  <section class="section"><div class="lead"><h3>Invite someone</h3><p>Approve an email address here. That person can then sign in on the login page with that email and a password of their own choice, and joins this event automatically. You can also copy the link and share it manually.</p></div>
    <div class="panel"><div class="pad">
      <div class="inline-form">${field('Email address', html`<input id="i_email" type="email" placeholder="name@organisation.com" data-enter="invite">`)}
        ${field('Role', html`<select id="i_role"><option value="editor">Editor</option><option value="viewer">Viewer</option><option value="admin">Admin</option></select>`)}
        <button class="btn primary" data-act="invite">${icon('mail', 'sm')} Approve email</button></div>
      ${invites.length ? html`<h3 style="margin:22px 0 4px">Pending invitations</h3><div class="rows">${invites.map((i) => html`<div class="row">
          <div class="grow"><b>${i.email}</b> <span class="pill">${i.role}</span><div class="linkrow">${inviteLink(i)}</div></div>
          <button class="btn sm" data-act="copyTeamInvite" data-link="${inviteLink(i)}">${icon('copy', 'sm')} Copy link</button>
          <button class="btn sm danger" data-act="revokeInvite" data-id="${i.id}">Revoke</button></div>`)}</div>` : ''}
    </div></div></section>` : ''}

  <section class="section"><div class="lead"><h3>Email alerts</h3><p>${admin ? 'Switch a type of alert on or off for this event.' : 'Set by an admin.'}</p></div>
    <div class="panel"><div class="pad">${notif.map((n) => html`<div class="switch-row"><div><b>${NOTIF[n.type]?.[0] || n.type}</b><span class="d">${NOTIF[n.type]?.[1] || ''}</span></div>
      <label class="switch"><input type="checkbox" ${n.enabled ? 'checked' : ''} ${admin ? '' : 'disabled'} data-change="setNotifType" data-type="${n.type}" aria-label="${NOTIF[n.type]?.[0]}"><i></i></label></div>`)}
      <p class="small muted" style="margin-top:12px">A schedule conflict is shown on screen when a session is saved. It is never sent by email.</p></div></div></section>`;
}

changes({
  setRole: async (el) => { await api(`/events/${E().id}/members/${el.dataset.id}`, 'PATCH', { role: el.value }); toast('Role updated'); await refreshNow(); },
  setNotify: async (el) => { await api(`/events/${E().id}/members/${el.dataset.id}`, 'PATCH', { receive_notifications: el.checked }); toast(el.checked ? 'Email alerts on' : 'Email alerts off'); },
  setNotifType: async (el) => { await api(`/events/${E().id}/notification-settings`, 'PUT', { type: el.dataset.type, enabled: el.checked }); toast('Alert setting saved'); },
});
// Link hamesha current site ke origin se banta hai (server ke FRONTEND_URL pe depend nahi)
const inviteLink = (i) => { const t = (i.link || '').split('/#/invite/')[1]; return t ? `${location.origin}/#/invite/${t}` : i.link; };

acts({
  removeMember: async (el) => {
    if (await confirmDialog({ title: 'Remove this person?', message: 'They lose access to this event immediately.', confirmLabel: 'Remove', danger: true })) {
      await api(`/events/${E().id}/members/${el.dataset.id}`, 'DELETE'); toast('Person removed'); await refreshNow();
    }
  },
  invite: async () => {
    const r = await api(`/events/${E().id}/invitations`, 'POST', { email: val('i_email'), role: $('#i_role').value });
    toast(r.email_sent ? 'Invitation emailed' : 'Email approved. They can now sign in with this email, or you can copy the link below.', r.email_sent ? 'ok' : 'info');
    await refreshNow();
  },
  copyTeamInvite: (el) => copyText(el.dataset.link, 'Invitation link copied'),
  revokeInvite: async (el) => { await api(`/events/${E().id}/invitations/${el.dataset.id}`, 'DELETE'); toast('Invitation revoked'); await refreshNow(); },
});