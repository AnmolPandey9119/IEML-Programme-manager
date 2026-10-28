import {
  api, S, acts, inputs, html, icon, raw, val, field, avatar, initials, avatarStyle, fmtTime, fmtDate, plural, statusPill,
  openPanel, confirmDialog, toast, mount, $, $$, topPanel,
} from './core.js';

const STATUSES = ['Invited', 'Confirmed', 'Tentative', 'Declined'];
const REMARK_HINT = {
  Invited: 'Optional note, for example who invited them or when you last followed up.',
  Confirmed: 'Optional note, for example travel or accommodation arrangements.',
  Tentative: 'Say what is pending, for example “Awaiting travel approval”.',
  Declined: 'Record the reason, for example “Prior commitment on the event dates”.',
};
const V = { list: [], filter: 'All', q: '', ev: null };
const canEdit = () => ['admin', 'editor'].includes(V.ev.my_role) && V.ev.status !== 'archived';

export async function viewSpeakers({ event }) {
  V.ev = event; V.list = await api(`/events/${event.id}/speakers`);
  V.filter = 'All'; V.q = '';
  return html`
  <div class="page-head"><div class="t"><h1>Speakers</h1>
    <p>Everyone who speaks, moderates or joins a panel. Add a person once and link them to any number of sessions.</p></div>
    <div class="actions" id="spActions">${actions()}</div></div>
  <div class="toolbar"><label class="search">${icon('search', 'sm')}<input type="search" id="spSearch" placeholder="Search speakers" data-input="spSearch" aria-label="Search speakers"></label>
    <div class="seg status" id="spFilter">${filterButtons()}</div></div>
  <div id="spGrid">${grid()}</div>`;
}

function actions() {
  return html`<button class="btn" data-act="exportSpeakers">${icon('download', 'sm')} Export</button>${canEdit() ? html`<button class="btn primary" data-act="newSpeaker">${icon('plus', 'sm')} Add speaker</button>` : ''}`;
}
function counts() {
  const c = { All: V.list.length }; STATUSES.forEach((s) => (c[s] = V.list.filter((x) => x.status === s).length)); return c;
}
function filterButtons() {
  const c = counts();
  return ['All', ...STATUSES].map((s) => html`<button class="${V.filter === s ? 'on' : ''}" data-act="spFilter" data-v="${s}">
    ${s !== 'All' ? html`<span class="dot ${s.toLowerCase()}"></span>` : ''}${s} <span class="n">${c[s]}</span></button>`);
}
function visible() {
  const q = V.q.trim().toLowerCase();
  return V.list.filter((s) => (V.filter === 'All' || s.status === V.filter)
    && (!q || `${s.full_name} ${s.organisation} ${s.designation}`.toLowerCase().includes(q)));
}
function grid() {
  const rows = visible();
  if (!V.list.length) {
    return html`<div class="panel"><div class="empty"><div class="art">${icon('mic', 'lg')}</div><h3>No speakers yet</h3>
      <p>Add the people you plan to invite. You can track whether they are invited, confirmed, tentative or declined.</p>
      ${canEdit() ? html`<button class="btn primary" data-act="newSpeaker">${icon('plus', 'sm')} Add the first speaker</button>` : ''}</div></div>`;
  }
  if (!rows.length) return html`<div class="panel"><div class="empty"><div class="art">${icon('search', 'lg')}</div><h3>No matching speakers</h3><p>Try a different name or clear the status filter.</p></div></div>`;
  return html`<div class="tiles">${rows.map((s) => html`<button class="tile" data-act="openSpeaker" data-id="${s.id}">
    <div class="ph" style="${s.photo_url ? '' : avatarStyle(s.full_name)}">${s.photo_url ? html`<img src="${s.photo_url}" alt="" loading="lazy">` : html`<span class="ini">${initials(s.full_name)}</span>`}
      ${statusPill(s.status)}</div>
    <div class="tx"><b>${s.full_name}</b><span class="r">${[s.designation, s.organisation].filter(Boolean).join(', ') || 'Designation not added'}</span>
      <span class="s">${icon('agenda', 'sm')} ${s.sessions.length ? plural(s.sessions.length, 'session') : 'Not in a session yet'}</span></div></button>`)}</div>`;
}
const repaint = () => {
  mount($('#spGrid'), grid()); mount($('#spFilter'), filterButtons());
};
async function reload() {
  V.list = await api(`/events/${V.ev.id}/speakers`); repaint();
  if (V.ev.__onSpeakersChanged) V.ev.__onSpeakersChanged();
}

inputs({ spSearch: (el) => { V.q = el.value; mount($('#spGrid'), grid()); } });

/* ---------------------------------------------------------------- drawer */
let draft = null; // { sp, photoFile, removePhoto, status }

function openSpeaker(sp) {
  draft = { sp, photoFile: null, removePhoto: false, status: sp?.status || 'Invited' };
  const ro = !canEdit();
  const d = ro ? 'disabled' : '';
  const x = sp || { full_name: '', designation: '', organisation: '', bio: '', email: '', phone: '', linkedin_url: '', website_url: '', status_remark: '', internal_notes: '', photo_url: '', sessions: [] };
  const admin = V.ev.my_role === 'admin' && V.ev.status !== 'archived';
  const p = openPanel({
    kind: 'drawer', title: sp ? sp.full_name : 'Add speaker',
    subtitle: sp ? [sp.designation, sp.organisation].filter(Boolean).join(', ') : 'Start with the name. Everything else can be added later.',
    body: html`
      <div class="photo-edit"><span id="photoPrev">${avatar(x.full_name || 'New', x.photo_url, 'lg')}</span>
        <div><div class="btns">${!ro ? html`<button class="btn sm" data-act="pickPhoto">${icon('camera', 'sm')} ${x.photo_url ? 'Change photo' : 'Upload photo'}</button>
          <button class="btn sm quiet danger ${x.photo_url ? '' : 'hide'}" id="rmPhoto" data-act="removePhoto">Remove</button>` : ''}</div>
          <p class="small muted" style="margin-top:6px">JPG or PNG, up to 5 MB. Shown on the website and in exports.</p>
          <input type="file" id="photoFile" accept="image/jpeg,image/png" class="hide" data-change-native></div></div>

      <div class="form-section">Profile</div>
      ${field('Full name', html`<input id="s_name" value="${x.full_name}" placeholder="Dr. Ananya Rao" data-input="spNameCheck" ${d}>`)}
      <div id="dupNote"></div>
      <div class="grid2">${field('Designation', html`<input id="s_desig" value="${x.designation}" placeholder="Managing Director" ${d}>`)}
        ${field('Organisation', html`<input id="s_org" value="${x.organisation}" placeholder="Company or institution" ${d}>`)}</div>
      ${field('Bio', html`<textarea id="s_bio" rows="4" placeholder="A short paragraph about the speaker." ${d}>${x.bio}</textarea>`, { hint: 'Shown on the website once the speaker is confirmed.' })}

      <div class="form-section">Status</div>
      <div class="seg status" id="spStatusSeg" style="margin-bottom:12px">${STATUSES.map((s) => html`<button type="button" class="${draft.status === s ? 'on' : ''}" data-act="pickSpStatus" data-v="${s}" ${d}><span class="dot ${s.toLowerCase()}"></span>${s}</button>`)}</div>
      ${field('Remark', html`<input id="s_remark" value="${x.status_remark}" placeholder="Add a short remark" ${d}>`, { hint: REMARK_HINT[draft.status] })}
      <div id="statusNote">${statusNote(draft.status)}</div>

      <div class="form-section">Contact</div><p class="form-note">Internal only. These details are never shown publicly.</p>
      <div class="grid2">${field('Email', html`<input id="s_email" type="email" value="${x.email}" placeholder="name@organisation.com" ${d}>`)}
        ${field('Phone', html`<input id="s_phone" type="tel" value="${x.phone}" placeholder="+91 98xxx xxxxx" ${d}>`)}</div>

      <div class="form-section">Online profiles</div><p class="form-note">Optional. Shown publicly when filled in.</p>
      <div class="grid2">${field('LinkedIn', html`<input id="s_li" value="${x.linkedin_url}" placeholder="linkedin.com/in/…" ${d}>`)}
        ${field('Website', html`<input id="s_web" value="${x.website_url}" placeholder="www.example.com" ${d}>`)}</div>

      <div class="form-section">Sessions</div>
      ${x.sessions.length ? x.sessions.map((r) => html`<div class="sess-ref"><b>${r.title}</b><span class="pill teal">${r.role}</span>
        <span class="small muted">${r.day_label}, ${fmtTime(r.start_time)} to ${fmtTime(r.end_time)}</span><span class="small muted">${r.hall}</span></div>`)
        : html`<p class="muted small">${sp ? 'Not linked to any session yet.' : 'Sessions appear here automatically once this speaker is added to the agenda.'}</p>`}

      <div class="form-section">Internal notes</div>
      ${field('Private notes', html`<textarea id="s_notes" rows="3" placeholder="Visible to the team only." ${d}>${x.internal_notes}</textarea>`)}`,
    footer: html`${sp && admin ? html`<button class="btn danger" data-act="deleteSpeaker">${icon('trash', 'sm')} Delete</button>` : ''}${sp ? html`<button class="btn" data-act="dlSpeakerProfile" data-id="${sp.id}">${icon('download', 'sm')} Profile PDF</button>` : ''}<span class="sp"></span>
      <button class="btn" data-close>${ro ? 'Close' : 'Cancel'}</button>${!ro ? html`<button class="btn primary" data-act="saveSpeaker" id="saveSp">${sp ? 'Save changes' : 'Add speaker'}</button>` : ''}`,
  });
  $('#photoFile', p.el)?.addEventListener('change', onPhotoPicked);
}

function statusNote(st) {
  if (st === 'Confirmed') return html`<div class="note">${icon('globe', 'sm')}<span>Confirmed speakers appear on the public website next to their sessions. The team is notified by email when you save.</span></div>`;
  return html`<div class="note amber">${icon('eye', 'sm')}<span>This speaker will not appear on the public website until their status is Confirmed.</span></div>`;
}

function onPhotoPicked(e) {
  const f = e.target.files[0]; if (!f) return;
  if (!/^image\/(jpeg|png)$/.test(f.type)) { toast('Please choose a JPG or PNG image.', 'err'); e.target.value = ''; return; }
  if (f.size > 5 * 1024 * 1024) { toast('That photo is larger than 5 MB.', 'err'); e.target.value = ''; return; }
  draft.photoFile = f; draft.removePhoto = false;
  const url = URL.createObjectURL(f);
  mount($('#photoPrev'), html`<span class="av lg"><img src="${url}" alt=""></span>`);
  $('#rmPhoto')?.classList.remove('hide');
}

inputs({
  spNameCheck: (el) => {
    const n = el.value.trim().toLowerCase();
    const dup = n && V.list.find((s) => s.full_name.toLowerCase() === n && s.id !== draft?.sp?.id);
    mount($('#dupNote'), dup ? html`<div class="note amber">${icon('warning', 'sm')}<span>A speaker named ${dup.full_name}${dup.organisation ? ' from ' + dup.organisation : ''} is already in the directory. You can still save this one.</span></div>` : '');
  },
});

acts({
  newSpeaker: () => openSpeaker(null),
  openSpeaker: (el) => openSpeaker(V.list.find((s) => s.id == el.dataset.id)),
  spFilter: (el) => { V.filter = el.dataset.v; repaint(); },
  pickPhoto: () => $('#photoFile').click(),
  removePhoto: () => {
    draft.photoFile = null; draft.removePhoto = true; $('#photoFile').value = '';
    mount($('#photoPrev'), avatar($('#s_name').value || 'New', '', 'lg')); $('#rmPhoto').classList.add('hide');
  },
  pickSpStatus: (el) => {
    draft.status = el.dataset.v;
    $$('#spStatusSeg button').forEach((b) => b.classList.toggle('on', b === el));
    mount($('#statusNote'), statusNote(draft.status));
    $('#s_remark').closest('.field').querySelector('.hint').textContent = REMARK_HINT[draft.status];
  },
  saveSpeaker: async (btn) => {
    const body = {
      full_name: val('s_name'), designation: val('s_desig'), organisation: val('s_org'), bio: val('s_bio'),
      email: val('s_email'), phone: val('s_phone'), linkedin_url: val('s_li'), website_url: val('s_web'),
      status: draft.status, status_remark: val('s_remark'), internal_notes: val('s_notes'),
    };
    if (!body.full_name) { $('#s_name').focus(); throw new Error('Enter the speaker’s full name.'); }
    btn.disabled = true;
    try {
      const base = `/events/${V.ev.id}/speakers`;
      let saved = draft.sp ? await api(`${base}/${draft.sp.id}`, 'PATCH', body) : await api(base, 'POST', body);
      const n = saved.team_notified;
      let photoFailed = '';
      try {
        if (draft.photoFile) { const fd = new FormData(); fd.append('file', draft.photoFile); saved = await api(`${base}/${saved.id}/photo`, 'POST', fd); }
        else if (draft.removePhoto && draft.sp?.photo_url) saved = await api(`${base}/${saved.id}/photo`, 'DELETE');
      } catch (e) { photoFailed = e.message; }
      topPanel()?.close();
      toast(n ? `${saved.full_name} is confirmed. ${plural(n, 'team member')} notified by email.` : draft.sp ? 'Speaker saved' : 'Speaker added');
      if (photoFailed) toast('Saved, but the photo could not be uploaded: ' + photoFailed, 'err');
      await reload();
    } finally { btn.disabled = false; }
  },
  deleteSpeaker: async () => {
    const sp = draft.sp;
    const n = sp.sessions.length;
    const ok = await confirmDialog({
      title: `Delete ${sp.full_name}?`, confirmLabel: 'Delete speaker', danger: true,
      message: n ? `${sp.full_name} will also be removed from ${plural(n, 'session')}. This cannot be undone.` : 'This cannot be undone.',
    });
    if (!ok) return;
    await api(`/events/${V.ev.id}/speakers/${sp.id}`, 'DELETE');
    topPanel()?.close(); toast('Speaker deleted'); await reload();
  },
});

export { openSpeaker as openSpeakerProfile };
