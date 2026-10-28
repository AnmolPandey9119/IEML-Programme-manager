import {
  api, S, acts, changes, inputs, html, raw, icon, mount, val, raw_val, field, avatar, fmtTime, fmtDate, plural, parseTime, to12, timeOptions,
  openPanel, confirmDialog, toast, topPanel, copyText, $, $$,
} from './core.js';

const GTYPES = ['OC', 'Advisory Council', 'Sub-committee', 'Working Group', 'Custom'];
const ATT = { unmarked: 'Not marked', attended: 'Attended', absent: 'Absent', apologies: 'Sent apologies' };
const L = { ev: null, groups: [], archived: [], sel: null, tab: 'members', showArchived: false, eventId: null };
const canEdit = () => ['admin', 'editor'].includes(L.ev.my_role) && L.ev.status !== 'archived';
const isAdmin = () => L.ev.my_role === 'admin' && L.ev.status !== 'archived';
const base = () => `/events/${L.ev.id}`;
const hhmm = (t) => (t ? String(t).slice(0, 5) : '');

export async function viewLists({ event, param }) {
  L.ev = event;
  if (L.eventId !== event.id) { L.eventId = event.id; L.sel = null; L.showArchived = false; L.tab = 'members'; }
  await loadGroups();
  const want = param ? +param : L.sel?.id;
  const pool = [...L.groups, ...L.archived];
  const first = pool.find((g) => g.id === want) || L.groups[0] || null;
  L.sel = first ? await api(`${base()}/groups/${first.id}`) : null;
  return html`
  <div class="page-head"><div class="t"><h1>Lists & Meetings</h1>
    <p>Committees, councils and working groups, with their members, meetings and minutes. This section is internal and is never published on the website.</p></div>
    <div class="actions">${canEdit() ? html`<button class="btn primary" data-act="newGroup">${icon('plus', 'sm')} New group</button>` : ''}</div></div>
  <div id="listsBody">${layout()}</div>`;
}
async function loadGroups() {
  [L.groups, L.archived] = await Promise.all([api(`${base()}/groups`), api(`${base()}/groups?archived=true`)]);
}
async function reloadSel(detail) {
  await loadGroups();
  L.sel = detail || (L.sel ? await api(`${base()}/groups/${L.sel.id}`) : null);
  mount($('#listsBody'), layout());
}

function layout() {
  if (!L.groups.length && !L.archived.length) {
    return html`<div class="panel"><div class="empty"><div class="art">${icon('clipboard', 'lg')}</div><h3>No groups yet</h3>
      <p>Create a group such as the Organising Committee or Advisory Council, then add its members and plan meetings.</p>
      ${canEdit() ? html`<button class="btn primary" data-act="newGroup">${icon('plus', 'sm')} Create the first group</button>` : ''}</div></div>`;
  }
  const item = (g) => html`<button class="gitem ${L.sel?.id === g.id ? 'on' : ''}" data-act="pickGroup" data-id="${g.id}"><b>${g.name}</b>
    <span>${g.group_type}, ${plural(g.member_count, 'member')}, ${plural(g.meeting_count, 'meeting')}</span></button>`;
  return html`<div class="split"><div>
      <div class="glist">${L.groups.map(item)}</div>
      ${L.archived.length ? html`<button class="btn quiet sm" style="margin-top:12px" data-act="toggleArchived">${icon('archive', 'sm')} ${L.showArchived ? 'Hide' : 'Show'} archived (${L.archived.length})</button>
        ${L.showArchived ? html`<div class="glist" style="margin-top:8px">${L.archived.map(item)}</div>` : ''}` : ''}</div>
    <div>${L.sel ? detail() : html`<div class="panel"><div class="empty"><p>Select a group to see its members and meetings.</p></div></div>`}</div></div>`;
}

function detail() {
  const g = L.sel, ro = g.archived || !canEdit();
  return html`<div class="ghead"><div class="t"><h2>${g.name}</h2>
      <div class="tag-row" style="margin-top:6px"><span class="pill teal">${g.group_type}</span>${g.archived ? html`<span class="pill archived">Archived, read-only</span>` : ''}
        ${g.share.enabled ? html`<span class="pill">${icon('link', 'sm')} Shared by link</span>` : ''}</div></div>
    <div class="actions" style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn sm" data-act="exportGroup" data-id="${g.id}" data-name="${g.name}">${icon('download', 'sm')} Export</button>
      ${canEdit() && !g.archived ? html`<button class="btn sm" data-act="editGroup">${icon('edit', 'sm')} Rename</button>` : ''}
      ${isAdmin() && !g.archived ? html`<button class="btn sm" data-act="shareGroup">${icon('link', 'sm')} Share link</button>` : ''}
      ${canEdit() ? html`<button class="btn sm" data-act="archiveGroup">${icon('archive', 'sm')} ${g.archived ? 'Restore' : 'Archive'}</button>` : ''}
      ${isAdmin() ? html`<button class="btn sm danger" data-act="deleteGroup">${icon('trash', 'sm')} Delete</button>` : ''}</div></div>
    <div class="toolbar"><div class="seg"><button class="${L.tab === 'members' ? 'on' : ''}" data-act="gTab" data-v="members">${icon('users', 'sm')} Members <span class="n">${g.members.length}</span></button>
      <button class="${L.tab === 'meetings' ? 'on' : ''}" data-act="gTab" data-v="meetings">${icon('calendar', 'sm')} Meetings <span class="n">${g.meetings.length}</span></button></div><span class="sp"></span>
      ${!ro ? (L.tab === 'members' ? html`<button class="btn primary sm" data-act="newMember">${icon('plus', 'sm')} Add member</button>` : html`<button class="btn primary sm" data-act="newMeeting">${icon('plus', 'sm')} Schedule meeting</button>`) : ''}</div>
    ${L.tab === 'members' ? members(g, ro) : meetings(g)}`;
}

function members(g, ro) {
  if (!g.members.length) return html`<div class="panel"><div class="empty"><div class="art">${icon('users', 'lg')}</div><h3>No members yet</h3><p>Add each member with their designation, organisation, role in this group and contact details.</p>
    ${!ro ? html`<button class="btn primary" data-act="newMember">${icon('plus', 'sm')} Add the first member</button>` : ''}</div></div>`;
  return html`<div class="panel">${g.members.map((m, i) => html`<div class="mrow">${avatar(m.name)}
    <div class="who"><b>${m.name}</b><span>${[m.designation, m.organisation].filter(Boolean).join(', ') || 'No designation added'}</span></div>
    ${m.role_in_group ? html`<span class="pill teal">${m.role_in_group}</span>` : ''}
    <div class="contact">${m.email ? html`<div>${icon('mail', 'sm')} ${m.email}</div>` : ''}${m.phone ? html`<div>${icon('phone', 'sm')} ${m.phone}</div>` : ''}</div>
    ${!ro ? html`<button class="btn icon sm quiet" aria-label="Move up" data-act="mMove" data-i="${i}" data-d="-1" ${i === 0 ? 'disabled' : ''}>${icon('up2', 'sm')}</button>
      <button class="btn icon sm quiet" aria-label="Move down" data-act="mMove" data-i="${i}" data-d="1" ${i === g.members.length - 1 ? 'disabled' : ''}>${icon('down2', 'sm')}</button>
      <button class="btn sm" data-act="editMember" data-id="${m.id}">Edit</button>
      ${isAdmin() ? html`<button class="btn icon sm quiet danger" aria-label="Remove" data-act="delMember" data-id="${m.id}">${icon('trash', 'sm')}</button>` : ''}` : ''}</div>`)}</div>`;
}

function meetings(g) {
  if (!g.meetings.length) return html`<div class="panel"><div class="empty"><div class="art">${icon('calendar', 'lg')}</div><h3>No meetings yet</h3><p>Schedule a meeting to prepare the agenda, mark attendance and record the minutes.</p>
    ${canEdit() && !g.archived ? html`<button class="btn primary" data-act="newMeeting">${icon('plus', 'sm')} Schedule a meeting</button>` : ''}</div></div>`;
  return html`<div class="panel">${g.meetings.map((m) => {
    const d = new Date(...m.meeting_date.split('-').map((x, i) => (i === 1 ? x - 1 : +x)));
    const c = (s) => m.attendance.filter((a) => a.status === s).length;
    const summary = m.attendance.length && (c('attended') + c('absent') + c('apologies')) ? `${c('attended')} attended, ${c('absent')} absent, ${c('apologies')} apologies` : '';
    return html`<button class="mtg" data-act="openMeeting" data-id="${m.id}"><div class="d"><b>${d.getDate()}</b><span>${d.toLocaleDateString('en-IN', { month: 'short' })}</span></div>
      <div><h3>${m.title}</h3><div class="sub">${[m.start_time ? `${fmtTime(m.start_time)} to ${m.end_time ? fmtTime(m.end_time) : ''}`.replace(/ to $/, '') : 'Time to be confirmed', m.location].filter(Boolean).join(', ')}</div>
        ${summary ? html`<div class="sub muted">${summary}</div>` : ''}</div>
      <span class="pill ${m.status === 'Completed' ? 'green' : m.status === 'Cancelled' ? 'brick' : 'blue'}">${m.status}</span></button>`;
  })}</div>`;
}

/* ---------------------------------------------------------------- actions */
acts({
  pickGroup: async (el) => { L.sel = await api(`${base()}/groups/${el.dataset.id}`); L.tab = 'members'; history.replaceState(null, '', `#/event/${L.ev.id}/lists/${L.sel.id}`); mount($('#listsBody'), layout()); },
  toggleArchived: () => { L.showArchived = !L.showArchived; mount($('#listsBody'), layout()); },
  gTab: (el) => { L.tab = el.dataset.v; mount($('#listsBody'), layout()); },
  newGroup: () => groupDialog(null),
  editGroup: () => groupDialog(L.sel),
  archiveGroup: async () => {
    const g = L.sel;
    if (!g.archived && !(await confirmDialog({ title: 'Archive this group?', message: 'It becomes read-only and is hidden from the main list. You can restore it at any time.', confirmLabel: 'Archive group' }))) return;
    const d = await api(`${base()}/groups/${g.id}`, 'PATCH', { archived: !g.archived });
    toast(d.archived ? 'Group archived' : 'Group restored'); L.showArchived = d.archived; await reloadSel(d);
  },
  deleteGroup: async () => {
    const g = L.sel;
    if (!(await confirmDialog({ title: `Delete ${g.name}?`, message: `This removes the group with its ${plural(g.members.length, 'member')} and ${plural(g.meetings.length, 'meeting')}. This cannot be undone. Archiving keeps the record.`, confirmLabel: 'Delete group', danger: true }))) return;
    await api(`${base()}/groups/${g.id}`, 'DELETE'); L.sel = null; toast('Group deleted'); window.__refresh();
  },
  newMember: () => memberDialog(null),
  editMember: (el) => memberDialog(L.sel.members.find((m) => m.id == el.dataset.id)),
  delMember: async (el) => {
    const m = L.sel.members.find((x) => x.id == el.dataset.id);
    if (!(await confirmDialog({ title: `Remove ${m.name}?`, message: 'They are removed from this group and from its meeting attendance records.', confirmLabel: 'Remove member', danger: true }))) return;
    await reloadSel(await api(`${base()}/groups/${L.sel.id}/members/${m.id}`, 'DELETE')); toast('Member removed');
  },
  mMove: async (el) => {
    const ids = L.sel.members.map((m) => m.id), i = +el.dataset.i, d = +el.dataset.d;
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    await reloadSel(await api(`${base()}/groups/${L.sel.id}/members/order`, 'PUT', { ids }));
  },
  newMeeting: () => meetingDrawer(null),
  openMeeting: (el) => meetingDrawer(L.sel.meetings.find((m) => m.id == el.dataset.id)),
  shareGroup: () => shareDialog(),
});

function groupDialog(g) {
  const p = openPanel({
    title: g ? 'Rename group' : 'New group', subtitle: g ? '' : 'For example the Organising Committee or an Advisory Council.',
    body: html`${field('Group name', html`<input id="g_name" value="${g?.name || ''}" placeholder="Organising Committee" data-enter="gSave" data-autofocus>`)}
      ${field('Type', html`<select id="g_type">${GTYPES.map((t) => html`<option ${g?.group_type === t ? 'selected' : ''}>${t}</option>`)}</select>`)}`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn primary" data-act="gSave">${g ? 'Save' : 'Create group'}</button>`,
  });
  p.group = g;
}
acts({
  gSave: async () => {
    const g = topPanel().group, body = { name: val('g_name'), group_type: $('#g_type').value };
    if (!body.name) throw new Error('Enter a group name.');
    const d = g ? await api(`${base()}/groups/${g.id}`, 'PATCH', body) : await api(`${base()}/groups`, 'POST', body);
    topPanel().close(); toast(g ? 'Group saved' : 'Group created'); L.tab = 'members'; await reloadSel(d);
    history.replaceState(null, '', `#/event/${L.ev.id}/lists/${d.id}`);
  },
});

/* ---- member dialog with "pick an existing person" */
function memberDialog(m) {
  const p = openPanel({
    title: m ? 'Edit member' : 'Add member', subtitle: m ? m.name : 'A person can belong to several groups with a different role in each.', wide: true,
    body: html`${!m ? html`<div class="combo" style="margin-bottom:16px">${field('Find someone already in this event', html`<input id="m_find" placeholder="Search by name or organisation" data-input="findPerson" autocomplete="off">`, { optional: true })}<div class="combo-list hide" id="m_list" style="top:62px"></div></div>` : ''}
      <div class="grid2">${field('Full name', html`<input id="m_name" value="${m?.name || ''}" placeholder="Dr. Sunita Verma">`)}
        ${field('Role in this group', html`<input id="m_role" value="${m?.role_in_group || ''}" placeholder="Chair, Member, Secretary">`, { optional: true })}
        ${field('Designation', html`<input id="m_desig" value="${m?.designation || ''}">`, { optional: true })}${field('Organisation', html`<input id="m_org" value="${m?.organisation || ''}">`, { optional: true })}
        ${field('Email', html`<input id="m_email" type="email" value="${m?.email || ''}">`, { optional: true })}${field('Phone', html`<input id="m_phone" type="tel" value="${m?.phone || ''}">`, { optional: true })}</div>
      ${field('Notes', html`<textarea id="m_notes" rows="3" placeholder="Visible to the team only.">${m?.notes || ''}</textarea>`, { optional: true })}`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn primary" data-act="mSave">${m ? 'Save changes' : 'Add member'}</button>`,
  });
  p.member = m;
}
let findTimer;
inputs({
  findPerson: (el) => {
    clearTimeout(findTimer);
    findTimer = setTimeout(async () => {
      const list = $('#m_list'); if (!list) return;
      const q = el.value.trim(); if (!q) { list.classList.add('hide'); return; }
      const rows = await api(`${base()}/people?q=${encodeURIComponent(q)}`);
      list.classList.toggle('hide', !rows.length);
      mount(list, html`${rows.map((r, i) => html`<button type="button" data-act="usePerson" data-i="${i}">${avatar(r.name, '', 'sm')}<span><b>${r.name}</b><small>${[r.designation, r.organisation].filter(Boolean).join(', ') || r.source}, from ${r.source}</small></span></button>`)}`);
      list.__rows = rows;
    }, 200);
  },
});
acts({
  usePerson: (el) => {
    const r = $('#m_list').__rows[+el.dataset.i];
    Object.entries({ m_name: r.name, m_desig: r.designation, m_org: r.organisation, m_email: r.email, m_phone: r.phone }).forEach(([id, v]) => { $('#' + id).value = v || ''; });
    $('#m_list').classList.add('hide'); $('#m_find').value = ''; $('#m_role').focus();
  },
  mSave: async () => {
    const m = topPanel().member;
    const body = { name: val('m_name'), role_in_group: val('m_role'), designation: val('m_desig'), organisation: val('m_org'), email: val('m_email'), phone: val('m_phone'), notes: val('m_notes') };
    if (!body.name) { $('#m_name').focus(); throw new Error('Enter the member’s full name.'); }
    const d = m ? await api(`${base()}/groups/${L.sel.id}/members/${m.id}`, 'PATCH', body) : await api(`${base()}/groups/${L.sel.id}/members`, 'POST', body);
    topPanel().close(); toast(m ? 'Member saved' : 'Member added'); await reloadSel(d);
  },
});

/* ---- meeting drawer */
function meetingDrawer(m) {
  const g = L.sel, ro = g.archived || !canEdit(), dis = ro ? 'disabled' : '';
  const x = m || { title: '', meeting_date: '', start_time: null, duration_minutes: 60, location: '', agenda: '', minutes: '', status: 'Scheduled', attendance: g.members.map((mem) => ({ member_id: mem.id, name: mem.name, role_in_group: mem.role_in_group, status: 'unmarked' })) };
  const p = openPanel({
    kind: 'drawer', title: m ? m.title : 'Schedule a meeting', subtitle: m ? `${g.name}` : `For ${g.name}`,
    body: html`<datalist id="times">${timeOptions()}</datalist>
      ${field('Meeting title', html`<input id="t_title" value="${x.title}" placeholder="Committee kick-off meeting" ${dis}>`)}
      <div class="grid3">${field('Date', html`<input id="t_date" type="date" value="${x.meeting_date}" ${dis}>`)}
        ${field('Starts', html`<input id="t_start" list="times" value="${to12(hhmm(x.start_time))}" placeholder="3:00 PM" autocomplete="off" data-change="mtgTime" ${dis}>`)}
        ${field('Duration (minutes)', html`<input id="t_dur" type="number" min="5" max="720" step="5" value="${x.duration_minutes}" ${dis}>`)}</div>
      ${field('Location', html`<input id="t_loc" value="${x.location}" placeholder="Conference Room 2, Expo Mart" ${dis}>`, { hint: 'Plain text. Video call links are not part of this system.' })}
      <div class="form-section">Status</div>
      <div class="seg" id="t_status">${['Scheduled', 'Completed', 'Cancelled'].map((s) => html`<button type="button" class="${x.status === s ? 'on' : ''}" data-act="mStatus" data-v="${s}" ${dis}>${s}</button>`)}</div>
      <div class="form-section">Agenda</div>
      ${field('Agenda items', html`<textarea id="t_agenda" rows="5" placeholder="One item per line" ${dis}>${x.agenda}</textarea>`, { hint: 'Write one point per line. Fill this in before the meeting.' })}
      <div class="form-section" style="display:flex;align-items:center;gap:10px">Attendance ${!ro && x.attendance.length ? html`<button type="button" class="btn sm" data-act="allAttended" style="margin-left:auto;font-family:var(--body)">Mark all attended</button>` : ''}</div>
      ${x.attendance.length ? x.attendance.map((a) => html`<div class="att"><div><b>${a.name}</b>${a.role_in_group ? html` <span class="small muted">${a.role_in_group}</span>` : ''}</div>
        <select data-att="${a.member_id}" ${dis} aria-label="Attendance for ${a.name}">${Object.entries(ATT).map(([k, v]) => html`<option value="${k}" ${a.status === k ? 'selected' : ''}>${v}</option>`)}</select></div>`)
        : html`<p class="muted small">Add members to the group to record attendance.</p>`}
      <div class="form-section">Minutes</div>
      ${field('What was discussed and decided', html`<textarea id="t_min" rows="7" placeholder="Fill this in after the meeting." ${dis}>${x.minutes}</textarea>`)}`,
    footer: html`${m && isAdmin() ? html`<button class="btn danger" data-act="delMeeting">${icon('trash', 'sm')} Delete</button>` : ''}${m ? html`<button class="btn" data-act="dlMeeting" data-gid="${g.id}" data-id="${m.id}">${icon('download', 'sm')} Record PDF</button>` : ''}<span class="sp"></span>
      <button class="btn" data-close>${ro ? 'Close' : 'Cancel'}</button>${!ro ? html`<button class="btn primary" data-act="saveMeeting">${m ? 'Save changes' : 'Schedule meeting'}</button>` : ''}`,
  });
  p.meeting = m; p.status = x.status;
}
changes({ mtgTime: (el) => { const t = parseTime(el.value); if (t) el.value = to12(t); } });
acts({
  mStatus: (el) => { topPanel().status = el.dataset.v; $$('#t_status button').forEach((b) => b.classList.toggle('on', b === el)); },
  allAttended: () => $$('[data-att]').forEach((s) => { s.value = 'attended'; }),
  saveMeeting: async () => {
    const p = topPanel(), m = p.meeting;
    const start = raw_val('t_start').trim() ? parseTime(raw_val('t_start')) : null;
    if (raw_val('t_start').trim() && !start) { $('#t_start').focus(); throw new Error('Enter the start time like 3:00 PM.'); }
    const body = { title: val('t_title'), meeting_date: raw_val('t_date'), start_time: start, duration_minutes: +raw_val('t_dur') || 60,
      location: val('t_loc'), agenda: raw_val('t_agenda').trim(), minutes: raw_val('t_min').trim(), status: p.status };
    if (!body.title) { $('#t_title').focus(); throw new Error('Enter a meeting title.'); }
    if (!body.meeting_date) { $('#t_date').focus(); throw new Error('Choose the meeting date.'); }
    const marks = {}; $$('[data-att]').forEach((s) => { marks[s.dataset.att] = s.value; });
    let d = m ? await api(`${base()}/groups/${L.sel.id}/meetings/${m.id}`, 'PATCH', body) : await api(`${base()}/groups/${L.sel.id}/meetings`, 'POST', body);
    if (Object.values(marks).some((v) => v !== 'unmarked')) {
      const id = m ? m.id : d.meetings.find((x) => x.title === body.title && x.meeting_date === body.meeting_date)?.id;
      if (id) d = await api(`${base()}/groups/${L.sel.id}/meetings/${id}/attendance`, 'PUT', { marks });
    }
    p.close(); toast(m ? 'Meeting saved' : 'Meeting scheduled'); L.tab = 'meetings'; await reloadSel(d);
  },
  delMeeting: async () => {
    const m = topPanel().meeting;
    if (!(await confirmDialog({ title: 'Delete this meeting?', message: `“${m.title}” with its agenda, attendance and minutes will be removed.`, confirmLabel: 'Delete meeting', danger: true }))) return;
    const d = await api(`${base()}/groups/${L.sel.id}/meetings/${m.id}`, 'DELETE'); topPanel().close(); toast('Meeting deleted'); await reloadSel(d);
  },
});

/* ---- share dialog */
const shareUrl = (t) => `${location.origin}/#/shared/${t}`;
function shareDialog() {
  const render = () => {
    const s = L.sel.share;
    return html`<p class="soft" style="margin-bottom:14px">Anyone with the link can view this group’s member list without signing in. They cannot edit anything and cannot see meetings, minutes or notes.</p>
      <div class="switch-row"><div><b>Link sharing</b><span class="d">${s.enabled ? 'The link below is active.' : 'Switched off. Nobody can open the list.'}</span></div>
        <label class="switch"><input type="checkbox" ${s.enabled ? 'checked' : ''} data-change="shEnable" aria-label="Link sharing"><i></i></label></div>
      ${s.enabled ? html`<div class="switch-row"><div><b>Include email and phone</b><span class="d">Off by default. Names, designations, organisations and roles are always shown.</span></div>
        <label class="switch"><input type="checkbox" ${s.include_contacts ? 'checked' : ''} data-change="shContacts" aria-label="Include contact details"><i></i></label></div>
        <div class="copybox" style="margin-top:14px"><input readonly value="${shareUrl(s.token)}" id="shUrl" aria-label="Share link"><button class="btn" data-act="shCopy">${icon('copy', 'sm')} Copy</button></div>
        <button class="btn sm quiet" style="margin-top:10px" data-act="shRenew">${icon('refresh', 'sm')} Create a new link and disable the old one</button>` : ''}`;
  };
  const p = openPanel({ title: 'Share member list', subtitle: L.sel.name, body: render(), footer: html`<span class="sp"></span><button class="btn primary" data-close>Done</button>` });
  p.render = () => p.setBody(render());
}
const putShare = async (enabled, include_contacts) => {
  L.sel.share = await api(`${base()}/groups/${L.sel.id}/share`, 'PUT', { enabled, include_contacts }); topPanel().render(); mount($('#listsBody'), layout());
};
changes({
  shEnable: (el) => putShare(el.checked, L.sel.share.include_contacts),
  shContacts: (el) => putShare(true, el.checked),
});
acts({
  shCopy: () => copyText($('#shUrl').value, 'Link copied'),
  shRenew: async () => {
    if (!(await confirmDialog({ title: 'Create a new link?', message: 'The old link stops working immediately.', confirmLabel: 'Create new link' }))) return;
    L.sel.share = await api(`${base()}/groups/${L.sel.id}/share/renew`, 'POST'); topPanel().render(); toast('New link created');
  },
});
