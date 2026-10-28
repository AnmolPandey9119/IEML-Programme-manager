/* Export dialogs (Section 4.6, 5.3, 6.3). Each button opens a small dialog, then downloads the file. */
import { api, S, acts, html, icon, raw, openPanel, saveBlob, toast, topPanel, $, $$ } from './core.js';

const eid = () => S.event.id;
const flag = (el, name) => (el.querySelector(`[name="${name}"]`)?.checked ? 'true' : 'false');

async function download(path, btn) {
  if (btn) { btn.disabled = true; btn.dataset.label = btn.innerHTML; btn.textContent = 'Preparing file…'; }
  try {
    saveBlob(await api(path, 'GET', undefined, { blob: true }));
    toast('Your file is ready. Check your downloads.');
  } finally { if (btn) { btn.disabled = false; btn.innerHTML = btn.dataset.label; } }
}

const checkbox = (name, label, hint, on = false) => html`<label class="check" style="margin-bottom:10px"><input type="checkbox" name="${name}" ${on ? 'checked' : ''}>
  <span><b>${label}</b><br><span class="small muted">${hint}</span></span></label>`;
const choice = (act, ic, title, hint, extra = '') => html`<button class="export-row" data-act="${act}" ${raw(extra)}>${icon(ic)}<span><b>${title}</b><small>${hint}</small></span>${icon('download', 'sm')}</button>`;

/** Shown in Sessions: choose what goes into the agenda, then PDF, Word or runsheet. */
function agendaDialog() {
  openPanel({
    title: 'Export agenda', subtitle: 'Choose what to include, then pick a format.',
    body: html`<div id="agendaOpts">
      <div class="form-section" style="margin-top:0">Include</div>
      ${checkbox('writeups', 'Writeups', 'The paragraph describing each session.', true)}
      ${checkbox('subtopics', 'Sub-topics', 'Discussion points listed under each session.', true)}
      ${checkbox('drafts', 'Draft sessions', 'Sessions that are not yet published on the website.')}
      ${checkbox('notes', 'Internal notes', 'Private team notes. Leave this off when sharing with sponsors or speakers.')}
      <div class="form-section">Format</div>
      <div class="export-list">
        ${choice('dlAgenda', 'file', 'Agenda, PDF', 'Formatted programme for printing or sharing.', 'data-ext="pdf"')}
        ${choice('dlAgenda', 'edit', 'Agenda, Word (.docx)', 'Same content, editable. For internal sharing or sponsors.', 'data-ext="docx"')}
        ${choice('dlRunsheet', 'clipboard', 'Speaker runsheet, PDF', 'Compact table of times, halls and speakers for the on-ground team. Uses the draft setting above.')}
      </div></div>`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Close</button>`,
  });
}

function speakersDialog() {
  openPanel({
    title: 'Export speakers', subtitle: 'Choose who to include, then pick a format.',
    body: html`<div id="spOpts"><div class="form-section" style="margin-top:0">Include</div>
      <div class="seg" id="spWho"><button type="button" class="on" data-act="spWho" data-v="false">All statuses</button>
        <button type="button" data-act="spWho" data-v="true">Confirmed only</button></div>
      <div class="form-section">Format</div>
      <div class="export-list">
        ${choice('dlSpeakers', 'file', 'Full list, PDF', 'Photo, name, designation, organisation, bio and linked sessions. No contact details.', 'data-ext="pdf"')}
        ${choice('dlSpeakers', 'grid', 'Full list, Excel', 'One row per speaker with every field, including email, phone and internal notes.', 'data-ext="xlsx"')}
      </div>
      <p class="small muted" style="margin-top:12px">The Excel file contains private contact details. Share it inside the team only.</p></div>`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Close</button>`,
  });
}

function groupDialog(el) {
  const gid = el.dataset.id;
  openPanel({
    title: 'Export ' + el.dataset.name, subtitle: 'Internal documents. Nothing here is published to the website.',
    body: html`<div class="export-list" data-gid="${gid}">
      ${choice('dlGroup', 'file', 'Member list, PDF', 'Name, designation, organisation, role and contact.', 'data-path="members.pdf"')}
      ${choice('dlGroup', 'grid', 'Member list, Excel', 'One row per member, with notes.', 'data-path="members.xlsx"')}
      ${choice('dlGroup', 'calendar', 'Meeting schedule, PDF', 'All meetings of this group as a simple schedule.', 'data-path="schedule.pdf"')}</div>
      <p class="small muted" style="margin-top:12px">To give someone a view-only member list without a login, use Share link.</p>`,
    footer: html`<span class="sp"></span><button class="btn" data-close>Close</button>`,
  });
}

acts({
  exportAgenda: agendaDialog,
  exportSpeakers: speakersDialog,
  exportGroup: groupDialog,
  dlAgenda: (b) => {
    const root = $('#agendaOpts');
    const q = ['writeups', 'subtopics', 'drafts', 'notes'].map((n) => `${n}=${flag(root, n)}`).join('&');
    return download(`/events/${eid()}/export/agenda.${b.dataset.ext}?${q}`, b);
  },
  dlRunsheet: (b) => download(`/events/${eid()}/export/runsheet.pdf?drafts=${flag($('#agendaOpts'), 'drafts')}`, b),
  spWho: (el) => { $$('#spWho button').forEach((x) => x.classList.toggle('on', x === el)); },
  dlSpeakers: (b) => {
    const only = $('#spWho button.on')?.dataset.v === 'true';
    return download(`/events/${eid()}/export/speakers.${b.dataset.ext}?confirmed_only=${only}`, b);
  },
  dlSpeakerProfile: (b) => download(`/events/${eid()}/export/speakers/${b.dataset.id}.pdf`, b),
  dlGroup: (b) => download(`/events/${eid()}/export/groups/${b.closest('[data-gid]').dataset.gid}/${b.dataset.path}`, b),
  dlMeeting: (b) => download(`/events/${eid()}/export/groups/${b.dataset.gid}/meetings/${b.dataset.id}.pdf`, b),
});
