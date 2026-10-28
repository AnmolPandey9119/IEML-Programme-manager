import {
  api, acts, changes, inputs, html, raw, icon, mount, val, raw_val, field, avatar, fmtTime, fmtDur, fmtDate, plural, TYPES, typeVars,
  parseTime, to12, toMin, timeOptions, openPanel, confirmDialog, toast, topPanel, store, $, $$, S,
} from './core.js';

const TYPE_LIST = Object.keys(TYPES);
const V = { ev: null, sessions: [], speakers: [], day: null, hall: '', status: '', view: 'list', eventId: null };
const canEdit = () => ['admin', 'editor'].includes(V.ev.my_role) && V.ev.status !== 'archived';
const isAdmin = () => V.ev.my_role === 'admin' && V.ev.status !== 'archived';
const dayShort = (d) => (d.label.includes(' — ') ? d.label.split(' — ')[0] : d.label);
const dayDate = (d) => new Date(...d.day_date.split('-').map((x, i) => (i === 1 ? x - 1 : +x))).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
const hhmm = (t) => String(t).slice(0, 5);
const issues = (s) => s.warnings.filter((w) => w.level === 'warning');
const dayIssueCount = (dayId) => V.sessions.filter((s) => s.day_id === dayId && issues(s).length).length;

export async function loadSessionData(ev) {
  [V.sessions, V.speakers] = await Promise.all([api(`/events/${ev.id}/sessions`), api(`/events/${ev.id}/speakers`)]);
}

/* ================================================================ page */
export async function viewSessions({ event }) {
  V.ev = event;
  await loadSessionData(event);
  if (V.eventId !== event.id) { V.eventId = event.id; V.hall = ''; V.status = ''; V.day = null; V.view = store.get('sessView') || 'list'; }
  const jump = store.get('sessDay'); if (jump) { store.set('sessDay', null); V.day = +jump; }
  if (!event.days.find((d) => d.id === V.day)) V.day = event.days[0]?.id ?? null;
  const pending = store.get('openSession'); // set by the overview to jump straight into an editor
  if (pending) { store.set('openSession', null); setTimeout(() => (pending === 'new' ? openEditor(null) : openEditor(V.sessions.find((s) => s.id == pending))), 50); }
  return html`
  <div class="page-head"><div class="t"><h1>Sessions</h1>
    <p>Build the agenda day by day. Warnings appear when something looks wrong, but nothing is ever blocked.</p></div>
    <div class="actions"><button class="btn" data-act="exportAgenda">${icon('download', 'sm')} Export</button>${canEdit() ? html`<button class="btn primary" data-act="newSession">${icon('plus', 'sm')} Add session</button>` : ''}</div></div>
  <div id="sessBody">${body()}</div>`;
}

function body() {
  const ev = V.ev;
  if (!ev.days.length) return empty('calendar', 'Add the event days first', 'Sessions are organised by day. Add the days in Event setup.');
  const day = ev.days.find((d) => d.id === V.day);
  const inDay = V.sessions.filter((s) => s.day_id === V.day);
  const shown = inDay.filter((s) => (!V.hall || (V.hall === 'none' ? !s.hall_id && !s.is_merged : s.is_merged || String(s.hall_id) === V.hall)) && (!V.status || s.status === V.status));
  const noHall = inDay.some((s) => !s.hall_id && !s.is_merged);
  return html`
    <div class="daytabs" role="tablist">${ev.days.map((d) => html`<button class="daytab ${d.id === V.day ? 'on' : ''}" role="tab" data-act="pickDay" data-id="${d.id}">
      ${dayIssueCount(d.id) ? html`<i class="flag" title="Needs attention"></i>` : ''}<b>${dayShort(d)}</b><span>${dayDate(d)}, ${plural(V.sessions.filter((s) => s.day_id === d.id).length, 'session')}</span></button>`)}</div>
    <div class="toolbar">
      <div class="chips"><button class="chipb ${!V.hall ? 'on' : ''}" data-act="pickHall" data-v="">All halls</button>
        ${ev.halls.map((h) => html`<button class="chipb ${V.hall === String(h.id) ? 'on' : ''}" data-act="pickHall" data-v="${h.id}">${h.name}</button>`)}
        ${noHall ? html`<button class="chipb ${V.hall === 'none' ? 'on' : ''}" data-act="pickHall" data-v="none">No hall yet</button>` : ''}</div>
      <select data-change="pickStatus" style="width:auto" aria-label="Filter by status"><option value="">All statuses</option>
        <option value="published" ${V.status === 'published' ? 'selected' : ''}>Published</option><option value="draft" ${V.status === 'draft' ? 'selected' : ''}>Draft</option></select>
      <div class="seg view-seg"><button class="${V.view === 'list' ? 'on' : ''}" data-act="pickView" data-v="list">${icon('agenda', 'sm')} List</button>
        <button class="${V.view === 'grid' ? 'on' : ''}" data-act="pickView" data-v="grid">${icon('grid', 'sm')} Hall grid</button></div></div>
    ${!inDay.length ? empty('agenda', `Nothing scheduled for ${dayShort(day)} yet`, 'Each day is planned on its own. Add the first session for this day.', canEdit())
      : !shown.length ? empty('search', 'No sessions match these filters', 'Choose another hall or status.')
      : V.view === 'grid' ? grid(shown) : timetable(shown)}`;
}
const empty = (ic, t, p, cta) => html`<div class="panel"><div class="empty"><div class="art">${icon(ic, 'lg')}</div><h3>${t}</h3><p>${p}</p>
  ${cta ? html`<button class="btn primary" data-act="newSession">${icon('plus', 'sm')} Add a session</button>` : ''}</div></div>`;

function timetable(rows) {
  return html`<div class="timetable">${rows.map((s) => {
    const w = s.warnings;
    const mods = s.people.filter((p) => p.role === 'moderator'), sp = s.people.filter((p) => p.role !== 'moderator');
    return html`<button class="srow ${issues(s).length ? 'has-warn' : ''}" style="${typeVars(s.session_type === 'Custom' ? 'Custom' : s.session_type)}" data-act="openSession" data-id="${s.id}">
      <div class="tm"><b>${fmtTime(s.start_time)}</b><span>to ${fmtTime(s.end_time)}</span><span>${s.duration_minutes ? fmtDur(s.duration_minutes) : ''}</span></div>
      <div><div class="ti"><h3>${s.title}</h3><span class="pill ${s.status}">${s.status === 'published' ? 'Published' : 'Draft'}</span></div>
        <div class="meta"><span class="tchip">${s.type_label}</span>
          <span class="hchip">${icon('pin', 'sm')} ${s.is_merged ? 'All halls merged' : s.hall_name || 'Hall to be confirmed'}</span></div>
        ${s.people.length ? html`<div class="ppl"><span class="stack">${s.people.slice(0, 5).map((p) => avatar(p.full_name, p.photo_url, 'sm'))}</span>
          <span>${mods.length ? html`<span class="mod">Moderator</span> ${mods.map((m) => m.full_name).join(', ')}${sp.length ? '; ' : ''}` : ''}${sp.slice(0, 3).map((p) => p.full_name).join(', ')}${sp.length > 3 ? ` and ${sp.length - 3} more` : ''}</span></div>` : ''}
        ${w.slice(0, 2).map((x) => html`<div class="warnline ${x.level}">${icon('warning', 'sm')}<span>${x.message}</span></div>`)}
        ${w.length > 2 ? html`<div class="warnline ${w.some((x) => x.level === 'warning') ? '' : 'notice'}">${icon('warning', 'sm')}<span>and ${w.length - 2} more to review</span></div>` : ''}
      </div></button>`;
  })}</div>`;
}

/* ---------------------------------------------------------------- hall grid */
function lanes(items) {
  const sorted = [...items].sort((a, b) => a.a - b.a);
  const cols = [];
  sorted.forEach((it) => {
    let c = cols.findIndex((end) => end <= it.a);
    if (c < 0) { c = cols.length; cols.push(0); }
    cols[c] = it.b; it.lane = c;
  });
  sorted.forEach((it) => { it.of = cols.length; });
  return sorted;
}
function grid(rows) {
  const halls = V.hall && V.hall !== 'none' ? V.ev.halls.filter((h) => String(h.id) === V.hall) : V.ev.halls;
  if (!halls.length) return empty('pin', 'No halls set up', 'Add the halls in Event setup to use the hall grid.');
  const ext = (s) => { const a = toMin(hhmm(s.start_time)); let b = toMin(hhmm(s.end_time)); if (b <= a) b = a + 30; return [a, b]; };
  const all = rows.map((s) => ext(s));
  const lo = Math.floor(Math.min(...all.map((x) => x[0])) / 60) * 60, hi = Math.ceil(Math.max(...all.map((x) => x[1])) / 60) * 60;
  const K = 1.15, H = (hi - lo) * K;
  const block = (s, extra = '') => { const [a, b] = ext(s);
    return html`<button class="blk ${extra} ${issues(s).length ? 'warn' : ''} ${s.status}" data-act="openSession" data-id="${s.id}" style="${typeVars(s.session_type)};top:${(a - lo) * K}px;height:${Math.max((b - a) * K, 26)}px;{{POS}}"><b>${s.title}</b><span>${fmtTime(s.start_time)} to ${fmtTime(s.end_time)}</span></button>`.s; };
  const hours = []; for (let m = lo; m <= hi; m += 60) hours.push(m);
  const merged = rows.filter((s) => s.is_merged);
  const cell = (h) => {
    const items = lanes(rows.filter((s) => !s.is_merged && s.hall_id === h.id).map((s) => ({ s, a: ext(s)[0], b: ext(s)[1] })));
    return `<div class="tg-col" style="height:${H}px;--hr:${60 * K}px">${items.map((it) => block(it.s).replace('{{POS}}', `left:${(it.lane / it.of) * 100 + 1}%;width:${100 / it.of - 2}%`)).join('')}</div>`;
  };
  return raw(`<div class="tg"><div class="tg-in" style="--n:${halls.length}">
    <div class="tg-head"><div></div>${halls.map((h) => `<div>${esc2(h.name)}</div>`).join('')}</div>
    <div class="tg-body"><div class="tg-axis" style="height:${H}px">${hours.map((m) => `<span style="top:${(m - lo) * K}px">${to12(`${String(Math.floor(m / 60) % 24).padStart(2, '0')}:00`)}</span>`).join('')}</div>
      ${halls.map(cell).join('')}
      ${merged.map((s) => block(s, 'merged').replace('{{POS}}', '')).join('')}</div></div></div>`);
}
const esc2 = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const repaint = () => mount($('#sessBody'), body());
acts({
  pickDay: (el) => { V.day = +el.dataset.id; repaint(); },
  pickHall: (el) => { V.hall = el.dataset.v; repaint(); },
  pickView: (el) => { V.view = el.dataset.v; store.set('sessView', V.view); repaint(); },
  newSession: () => openEditor(null),
  openSession: (el) => openEditor(V.sessions.find((s) => s.id == el.dataset.id)),
});
changes({ pickStatus: (el) => { V.status = el.value; repaint(); } });

/* ================================================================ editor */
let ed = null; // working copy of the session being edited
let checkTimer = null;
const defaultRole = () => (['Panel Discussion', 'Roundtable'].includes(ed.type) ? 'panelist' : 'speaker');

function fresh() {
  const prev = V.sessions.filter((s) => s.day_id === V.day).sort((a, b) => String(a.end_time).localeCompare(String(b.end_time))).pop();
  const start = prev ? hhmm(prev.end_time) : '09:00';
  const end = (() => { const m = Math.min(toMin(start) + 60, 23 * 60 + 59); return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`; })();
  return { id: null, day_id: V.day, hall: V.hall && V.hall !== 'none' ? V.hall : '', type: 'Panel Discussion', custom: '', title: '', writeup: '', subtopics: [],
    start, end, status: 'draft', notes: '', mods: [], speakers: [] };
}
function fromSession(s) {
  return { id: s.id, day_id: s.day_id, hall: s.is_merged ? 'merged' : s.hall_id ? String(s.hall_id) : '', type: s.session_type, custom: s.custom_type_label,
    title: s.title, writeup: s.writeup, subtopics: [...s.subtopics], start: hhmm(s.start_time), end: hhmm(s.end_time), status: s.status, notes: s.internal_notes,
    mods: s.people.filter((p) => p.role === 'moderator').map((p) => p.speaker_id),
    speakers: s.people.filter((p) => p.role !== 'moderator').map((p) => ({ id: p.speaker_id, role: p.role })) };
}
const spk = (id) => V.speakers.find((s) => s.id === id);

function openEditor(s) {
  ed = s ? fromSession(s) : fresh();
  const ro = !canEdit(), d = ro ? 'disabled' : '';
  const p = openPanel({
    kind: 'drawer', title: s ? 'Edit session' : 'Add session', subtitle: s ? `${s.day_label}, ${fmtTime(s.start_time)} to ${fmtTime(s.end_time)}` : 'Fill in the essentials. You can refine the rest later.',
    body: html`<datalist id="times">${timeOptions()}</datalist>
      <div id="liveWarn" class="livewarn"></div>
      ${field('Session title', html`<input id="x_title" value="${ed.title}" placeholder="Opening address" data-input="edChanged" ${d}>`)}
      <div class="grid2">
        ${field('Session type', html`<select id="x_type" data-change="edType" ${d}>${TYPE_LIST.map((t) => html`<option ${t === ed.type ? 'selected' : ''}>${t}</option>`)}</select>`)}
        <div id="customWrap" class="${ed.type === 'Custom' ? '' : 'hide'}">${field('Name this type', html`<input id="x_custom" value="${ed.custom}" placeholder="Cultural Programme" data-input="edChanged" ${d}>`)}</div>
      </div>
      <div class="grid2">
        ${field('Day', html`<select id="x_day" data-change="edChanged" ${d}>${V.ev.days.map((x) => html`<option value="${x.id}" ${x.id === ed.day_id ? 'selected' : ''}>${x.label}</option>`)}</select>`)}
        ${field('Hall', html`<select id="x_hall" data-change="edHall" ${d}><option value="">Hall to be confirmed</option>
          ${V.ev.halls.map((h) => html`<option value="${h.id}" ${ed.hall === String(h.id) ? 'selected' : ''}>${h.name}</option>`)}
          <option value="merged" ${ed.hall === 'merged' ? 'selected' : ''}>All halls merged (plenary)</option></select>`)}
      </div>
      <div id="mergedNote" class="${ed.hall === 'merged' ? '' : 'hide'}"><div class="note">${icon('info', 'sm')}<span>This session uses the whole venue. No other session should run in any hall during this time. The public agenda shows the venue name.</span></div></div>
      <div class="grid2">
        ${field('Starts', html`<input id="x_start" class="timein" list="times" value="${to12(ed.start)}" placeholder="9:30 AM" data-change="edTime" data-input="edTimeLive" autocomplete="off" ${d}>`)}
        ${field('Ends', html`<input id="x_end" class="timein" list="times" value="${to12(ed.end)}" placeholder="10:30 AM" data-change="edTime" data-input="edTimeLive" autocomplete="off" ${d}>`)}
      </div><div class="dur" id="dur"></div>

      <div class="form-section">Status</div>
      <div class="seg" id="stSeg"><button type="button" class="${ed.status === 'draft' ? 'on' : ''}" data-act="edStatus" data-v="draft" ${d}>Draft</button><button type="button" class="${ed.status === 'published' ? 'on' : ''}" data-act="edStatus" data-v="published" ${d}>Published</button></div>
      <p class="form-note" id="stNote" style="margin-top:8px">${statusNote(ed.status)}</p>

      <div class="form-section">Moderator</div><p class="form-note">Chosen from the speaker directory.</p>
      <div id="modList"></div><div class="combo" id="cbMod">${ro ? '' : html`<input id="cb_mod" placeholder="Search speakers to add a moderator" data-input="cbSearch" data-kind="mod" autocomplete="off"><div class="combo-list hide" id="cbl_mod"></div>`}</div>
      <div class="form-section">Speakers and panelists</div><p class="form-note">Add as many as you need. Use “Add as new speaker” for someone who is not in the directory yet.</p>
      <div id="spkList"></div><div class="combo" id="cbSpk">${ro ? '' : html`<input id="cb_spk" placeholder="Search speakers to add" data-input="cbSearch" data-kind="spk" autocomplete="off"><div class="combo-list hide" id="cbl_spk"></div>`}</div>

      <div class="form-section">Writeup</div>
      ${field('About this session', html`<textarea id="x_write" rows="4" placeholder="A short paragraph about what the session covers." data-input="edChanged" ${d}>${ed.writeup}</textarea>`, { hint: 'Appears on the public website.' })}
      <div class="form-section">Sub-topics</div><p class="form-note">Specific discussion points or questions. Reorder them with the arrows.</p>
      <div class="subs" id="subList"></div>${ro ? '' : html`<button class="btn sm" data-act="addSub">${icon('plus', 'sm')} Add sub-topic</button>`}
      <div class="form-section">Internal notes</div>
      ${field('Private notes', html`<textarea id="x_notes" rows="3" placeholder="Visible to the team only. Never shown on the website or in public exports." ${d}>${ed.notes}</textarea>`)}`,
    footer: html`${s && isAdmin() ? html`<button class="btn danger" data-act="delSession">${icon('trash', 'sm')} Delete</button>` : ''}
      ${s && canEdit() ? html`<button class="btn" data-act="dupSession">${icon('copy', 'sm')} Duplicate</button>` : ''}<span class="sp"></span>
      <button class="btn" data-close>${ro ? 'Close' : 'Cancel'}</button>${!ro ? html`<button class="btn primary" id="saveSess" data-act="saveSession">${s ? 'Save changes' : 'Add session'}</button>` : ''}`,
  });
  ed.panel = p;
  paintSubs(); paintPeople(); paintDur(); scheduleCheck(0);
}
const statusNote = (st) => (st === 'published' ? 'Published sessions appear on the website within 30 seconds of saving.' : 'Draft sessions are saved for the team but are not shown on the website.');

function collect() {
  if (!$('#x_title')) return;
  Object.assign(ed, { title: raw_val('x_title'), custom: raw_val('x_custom'), writeup: raw_val('x_write'), notes: raw_val('x_notes'), day_id: +raw_val('x_day'), type: raw_val('x_type'), hall: raw_val('x_hall') });
  ed.subtopics = $$('#subList input').map((i) => i.value);
}
function paintSubs() {
  const ro = !canEdit();
  mount($('#subList'), html`${ed.subtopics.map((t, i) => html`<div class="sub"><input value="${t}" placeholder="Discussion point" data-enter="subEnter" ${ro ? 'disabled' : ''}>
    ${ro ? '' : html`<button class="btn icon sm quiet" aria-label="Move up" data-act="subMove" data-i="${i}" data-d="-1" ${i === 0 ? 'disabled' : ''}>${icon('up2', 'sm')}</button>
    <button class="btn icon sm quiet" aria-label="Move down" data-act="subMove" data-i="${i}" data-d="1" ${i === ed.subtopics.length - 1 ? 'disabled' : ''}>${icon('down2', 'sm')}</button>
    <button class="btn icon sm quiet" aria-label="Remove" data-act="subDel" data-i="${i}">${icon('x', 'sm')}</button>`}</div>`)}`);
}
function paintPeople() {
  const ro = !canEdit();
  const chip = (id, role, kind, i) => { const p = spk(id); if (!p) return '';
    return html`<div class="pchip">${avatar(p.full_name, p.photo_url, 'sm')}<div class="who"><b>${p.full_name}</b><span>${[p.designation, p.organisation].filter(Boolean).join(', ') || 'No designation added'}</span></div>
      <span class="pill ${p.status.toLowerCase()}" title="Only Confirmed speakers show on the website"><span class="dot"></span>${p.status}</span>
      ${kind === 'spk' && !ro ? html`<select data-change="pRole" data-i="${i}" aria-label="Role"><option value="speaker" ${role === 'speaker' ? 'selected' : ''}>Speaker</option><option value="panelist" ${role === 'panelist' ? 'selected' : ''}>Panelist</option></select>` : ''}
      ${ro ? '' : html`<button class="btn icon sm quiet" aria-label="Remove" data-act="pDel" data-kind="${kind}" data-i="${i}">${icon('x', 'sm')}</button>`}</div>`; };
  mount($('#modList'), html`${ed.mods.map((id, i) => chip(id, 'moderator', 'mod', i))}`);
  mount($('#spkList'), html`${ed.speakers.map((x, i) => chip(x.id, x.role, 'spk', i))}`);
}
function paintDur() {
  const a = parseTime(raw_val('x_start')), b = parseTime(raw_val('x_end')), el = $('#dur'); if (!el) return;
  el.className = 'dur';
  if (!a || !b) { el.textContent = (raw_val('x_start') || raw_val('x_end')) ? 'Enter a time such as 9:30 AM.' : ''; return; }
  const m = toMin(b) - toMin(a);
  if (m > 0) el.textContent = `Duration ${fmtDur(m)}`; else { el.textContent = 'The end time is not after the start time.'; el.classList.add('bad'); }
}
function payload() {
  collect();
  const start = parseTime(raw_val('x_start')), end = parseTime(raw_val('x_end'));
  const merged = ed.hall === 'merged';
  return {
    start, end, body: {
      id: ed.id, day_id: ed.day_id, hall_id: merged || !ed.hall ? null : +ed.hall, is_merged: merged, title: ed.title.trim(), session_type: ed.type,
      custom_type_label: ed.custom.trim(), writeup: ed.writeup.trim(), subtopics: ed.subtopics.map((x) => x.trim()).filter(Boolean),
      start_time: start, end_time: end, status: ed.status, internal_notes: ed.notes.trim(),
      people: [...ed.mods.map((id) => ({ speaker_id: id, role: 'moderator' })), ...ed.speakers.map((x) => ({ speaker_id: x.id, role: x.role }))],
    },
  };
}
function scheduleCheck(delay = 450) {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(async () => {
    if (!ed || ed.panel.closed) return;
    const { body } = payload();
    if (!body.start_time || !body.end_time || !body.title) { mount($('#liveWarn'), ''); return; }
    try { paintWarnings(await api(`/events/${V.ev.id}/sessions/check`, 'POST', body)); } catch { /* the check is advisory */ }
  }, delay);
}
const warnBox = (w) => html`<div class="wbox ${w.level}">${icon('warning', 'sm')}<span>${w.message}</span></div>`;
function paintWarnings(list) { const el = $('#liveWarn'); if (el) mount(el, list.length ? html`${list.map(warnBox)}` : ''); }

inputs({
  edChanged: () => scheduleCheck(),
  edTimeLive: () => { paintDur(); scheduleCheck(); },
  cbSearch: (el) => comboSearch(el.dataset.kind, el.value),
});
changes({
  edChanged: () => scheduleCheck(),
  edType: (el) => { ed.type = el.value; $('#customWrap').classList.toggle('hide', ed.type !== 'Custom'); scheduleCheck(); },
  edHall: (el) => { ed.hall = el.value; $('#mergedNote').classList.toggle('hide', ed.hall !== 'merged'); scheduleCheck(); },
  edTime: (el) => { const t = parseTime(el.value); if (t) el.value = to12(t); paintDur(); scheduleCheck(); },
  pRole: (el) => { ed.speakers[+el.dataset.i].role = el.value; scheduleCheck(); },
});

/* ---- speaker combobox */
function comboSearch(kind, q) {
  const list = $('#cbl_' + kind), taken = new Set([...ed.mods, ...ed.speakers.map((x) => x.id)]);
  const needle = q.trim().toLowerCase();
  const hits = V.speakers.filter((s) => !taken.has(s.id) && (!needle || `${s.full_name} ${s.organisation} ${s.designation}`.toLowerCase().includes(needle))).slice(0, 8);
  const exact = V.speakers.some((s) => s.full_name.toLowerCase() === needle);
  list.classList.toggle('hide', !hits.length && !needle);
  mount(list, html`${hits.map((s) => html`<button type="button" data-act="pAdd" data-kind="${kind}" data-id="${s.id}">${avatar(s.full_name, s.photo_url, 'sm')}<span><b>${s.full_name}</b><small>${[s.designation, s.organisation].filter(Boolean).join(', ') || s.status}</small></span></button>`)}
    ${needle && !exact && canEdit() ? html`<button type="button" data-act="pNew" data-kind="${kind}" data-name="${q.trim()}"><span class="av sm" style="background:var(--primary-soft);color:var(--primary)">${icon('plus', 'sm')}</span><span><b>Add “${q.trim()}” as new speaker</b><small>Creates a speaker with status Invited</small></span></button>` : ''}
    ${!hits.length && !needle ? html`<div class="pad small muted" style="padding:10px 12px">Everyone in the directory is already added.</div>` : ''}`);
}
document.addEventListener('mousedown', (e) => { if (e.target.closest('.combo-list')) e.preventDefault(); });
document.addEventListener('focusin', (e) => { if (e.target.matches?.('#cb_mod,#cb_spk')) comboSearch(e.target.dataset.kind, e.target.value); });
document.addEventListener('focusout', (e) => { if (e.target.matches?.('#cb_mod,#cb_spk')) setTimeout(() => $('#cbl_' + e.target.dataset.kind)?.classList.add('hide'), 120); });

function addPerson(kind, id) {
  collect();
  if (kind === 'mod') ed.mods.push(id); else ed.speakers.push({ id, role: defaultRole() });
  const inp = $('#cb_' + kind); if (inp) inp.value = '';
  $('#cbl_' + kind)?.classList.add('hide'); paintPeople(); scheduleCheck(0);
}
acts({
  pAdd: (el) => addPerson(el.dataset.kind, +el.dataset.id),
  pNew: async (el) => {
    const sp = await api(`/events/${V.ev.id}/speakers`, 'POST', { full_name: el.dataset.name });
    V.speakers.push(sp); toast(`${sp.full_name} added to the speaker directory`); addPerson(el.dataset.kind, sp.id);
  },
  pDel: (el) => { collect(); (el.dataset.kind === 'mod' ? ed.mods : ed.speakers).splice(+el.dataset.i, 1); paintPeople(); scheduleCheck(0); },
  addSub: () => { collect(); ed.subtopics.push(''); paintSubs(); $$('#subList input').at(-1)?.focus(); },
  subEnter: () => { collect(); ed.subtopics.push(''); paintSubs(); $$('#subList input').at(-1)?.focus(); },
  subDel: (el) => { collect(); ed.subtopics.splice(+el.dataset.i, 1); paintSubs(); },
  subMove: (el) => { collect(); const i = +el.dataset.i, d = +el.dataset.d; [ed.subtopics[i], ed.subtopics[i + d]] = [ed.subtopics[i + d], ed.subtopics[i]]; paintSubs(); },
  edStatus: (el) => { ed.status = el.dataset.v; $$('#stSeg button').forEach((b) => b.classList.toggle('on', b === el)); $('#stNote').textContent = statusNote(ed.status); },
  saveSession: async (btn) => {
    const { start, end, body } = payload();
    if (!body.title) { $('#x_title').focus(); throw new Error('Enter a session title.'); }
    if (!start || !end) { ($('#x_start') && !start ? $('#x_start') : $('#x_end')).focus(); throw new Error('Enter the start and end time, for example 9:30 AM.'); }
    btn.disabled = true;
    try {
      const warnings = await api(`/events/${V.ev.id}/sessions/check`, 'POST', body);
      if (warnings.length && !(await warningPrompt(warnings))) return;
      const saved = ed.id ? await api(`/events/${V.ev.id}/sessions/${ed.id}`, 'PUT', body) : await api(`/events/${V.ev.id}/sessions`, 'POST', body);
      V.day = saved.day_id; topPanel()?.close();
      toast(ed.id ? 'Session saved' : 'Session added'); window.__refresh();
    } finally { btn.disabled = false; }
  },
  delSession: async () => {
    const s = V.sessions.find((x) => x.id === ed.id);
    if (!(await confirmDialog({ title: 'Delete this session?', message: `“${s.title}” will be removed from the agenda and the website. This cannot be undone.`, confirmLabel: 'Delete session', danger: true }))) return;
    await api(`/events/${V.ev.id}/sessions/${s.id}`, 'DELETE'); topPanel()?.close(); toast('Session deleted'); window.__refresh();
  },
  dupSession: async () => {
    const n = await api(`/events/${V.ev.id}/sessions/${ed.id}/duplicate`, 'POST');
    topPanel()?.close(); store.set('openSession', String(n.id)); V.day = n.day_id; toast('Duplicate created as a draft. Adjust the day or time and save.'); window.__refresh();
  },
});

/** The on-screen prompt required by Section 4.5: proceed or fix. */
function warningPrompt(list) {
  return new Promise((resolve) => {
    let go = false;
    const hard = list.filter((w) => w.level === 'warning').length;
    const p = openPanel({
      title: hard ? 'Please review before saving' : 'A small note before saving', subtitle: 'The session can still be saved as it is.',
      body: html`${list.map(warnBox)}`,
      footer: html`<span class="sp"></span><button class="btn" data-close data-autofocus>Go back and fix</button><button class="btn primary" id="goAnyway">Save anyway</button>`,
      onClose: () => resolve(go),
    });
    $('#goAnyway', p.el).addEventListener('click', () => { go = true; p.close(); });
  });
}

export { openEditor as openSessionEditor, V as sessionState };
