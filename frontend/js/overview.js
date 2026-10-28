import { api, S, acts, html, raw, icon, avatar, fmtTime, fmtDur, fmtDate, plural, typeVars, store, mount, $, $$ } from './core.js';
import { STATUS_INFO } from './events.js';

/* Overview: a calm summary first, details one click away. Styles live in /css/overview.css. */
if (!document.getElementById('ov-css')) {
  const l = document.createElement('link');
  l.id = 'ov-css'; l.rel = 'stylesheet'; l.href = '/css/overview.css';
  document.head.append(l);
}

const O = { ev: null, sessions: [], day: null, eventId: null };
const dayShort = (d) => (d.label.includes(' — ') ? d.label.split(' — ')[0] : d.label);
const hasWarning = (s) => s.warnings.some((w) => w.level === 'warning');
const toLocal = (iso) => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d); };

function countdown(ev) {
  if (!ev.days.length) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const first = toLocal(ev.days[0].day_date), last = toLocal(ev.days.at(-1).day_date);
  const diff = Math.round((first - today) / 86400000);
  if (today > last) return { big: 'Done', small: 'This event has ended' };
  if (today >= first) {
    const n = Math.round((today - first) / 86400000) + 1;
    return { big: `Day ${n}`, small: 'The event is on today' };
  }
  return { big: String(diff), small: diff === 1 ? 'day to go' : 'days to go' };
}

export async function viewOverview({ event: ev }) {
  const [sessions, speakers] = await Promise.all([api(`/events/${ev.id}/sessions`), api(`/events/${ev.id}/speakers`)]);
  if (O.eventId !== ev.id) { O.eventId = ev.id; O.day = null; }
  O.ev = ev; O.sessions = sessions;
  if (!ev.days.find((d) => d.id === O.day)) O.day = ev.days[0]?.id ?? null;

  const canEdit = ['admin', 'editor'].includes(ev.my_role) && ev.status !== 'archived';
  const published = sessions.filter((s) => s.status === 'published').length;
  const drafts = sessions.length - published;
  const flagged = sessions.filter(hasWarning);
  const count = (st) => speakers.filter((s) => s.status === st).length;
  const confirmed = count('Confirmed');
  const range = !ev.days.length ? '' : ev.days.length === 1 ? fmtDate(ev.days[0].day_date) : `${fmtDate(ev.days[0].day_date)} to ${fmtDate(ev.days.at(-1).day_date)}`;
  const cd = countdown(ev);

  return html`
  <section class="ov-hero">
    <div class="ov-hero-main">
      <span class="ov-eyebrow">Event overview</span>
      <h1>${ev.name} ${ev.edition}</h1>
      ${ev.theme_line ? html`<p class="ov-theme">${ev.theme_line}</p>` : ''}
      <div class="ov-chips">
        ${range ? html`<span>${icon('calendar', 'sm')} ${range}</span>` : ''}
        ${ev.venue_name || ev.venue_city ? html`<span>${icon('pin', 'sm')} ${[ev.venue_name, ev.venue_city].filter(Boolean).join(', ')}</span>` : ''}
        <span class="ov-status ${ev.status}"><i></i>${STATUS_INFO[ev.status][0]}</span>
      </div>
      ${canEdit ? html`<button class="ov-cta" data-act="ovNew">${icon('plus', 'sm')} Add session</button>` : ''}
    </div>
    ${cd ? html`<div class="ov-count"><b>${cd.big}</b><span>${cd.small}</span></div>` : ''}
  </section>

  <section class="ov-kpis">
    ${kpi(`#/event/${ev.id}/sessions`, 'agenda', 'Sessions', sessions.length, sessions.length ? `${published} published${drafts ? `, ${drafts} draft` : ''}` : 'None added yet')}
    ${kpi(`#/event/${ev.id}/speakers`, 'mic', 'Speakers confirmed', speakers.length ? `${confirmed}<small>/${speakers.length}</small>` : 0, speakers.length ? `${speakers.length - confirmed} still to confirm` : 'None added yet', true)}
    ${kpi(`#/event/${ev.id}/setup`, 'layers', 'Days and halls', `${ev.days.length}<small> days</small>`, plural(ev.halls.length, 'hall') + ' in use', true)}
    ${flagged.length
      ? kpi(`#/event/${ev.id}/sessions`, 'warning', 'To review', flagged.length, flagged.length === 1 ? 'session has a warning' : 'sessions have warnings', false, 'bad')
      : kpi(`#/event/${ev.id}/sessions`, 'check', 'Schedule health', sessions.length ? 'Clear' : '–', sessions.length ? 'No conflicts found' : 'Nothing to check yet', true, sessions.length ? 'good' : '')}
  </section>

  <div class="ov-grid">
    <section class="ov-card ov-prog">
      <header><h2>Programme</h2><a class="ov-link" href="#/event/${ev.id}/sessions">Open Sessions ${icon('right', 'sm')}</a></header>
      ${ev.days.length ? html`
        <div class="ov-tabs" role="tablist">${ev.days.map((d) => html`<button role="tab" class="${d.id === O.day ? 'on' : ''}" data-act="ovTab" data-id="${d.id}">
          <b>${dayShort(d)}</b><span>${toLocal(d.day_date).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}</span></button>`)}</div>
        <div id="ovDay">${dayList()}</div>`
        : html`<div class="ov-empty">${icon('calendar', 'lg')}<h3>No event days yet</h3><p>Add the days of the event to start planning.</p><a class="btn primary" href="#/event/${ev.id}/setup">Open event setup</a></div>`}
    </section>

    <aside class="ov-side">
      ${attention(ev, sessions, flagged)}
      ${speakerCard(speakers, count, confirmed)}
      ${setupCard(ev, sessions, speakers)}
    </aside>
  </div>`;
}

const kpi = (href, ic, label, value, sub, mid = false, tone = '') => html`<a class="ov-kpi ${tone}" href="${href}">
  <span class="ov-kpi-ic">${icon(ic)}</span><span class="ov-kpi-l">${label}</span><b>${raw(value)}</b><span class="ov-kpi-s">${sub}</span></a>`;

/* ---------------------------------------------------------------- day timeline */
function dayList() {
  const rows = O.sessions.filter((s) => s.day_id === O.day);
  const day = O.ev.days.find((d) => d.id === O.day);
  if (!rows.length) return html`<div class="ov-empty">${icon('agenda', 'lg')}<h3>Nothing scheduled for ${dayShort(day)} yet</h3><p>Each day is planned on its own.</p></div>`;
  return html`<p class="ov-day-sum">${plural(rows.length, 'session')}, ${rows.filter((s) => s.status === 'published').length} published</p>
    <ol class="ov-list">${rows.map(row)}</ol>`;
}
function row(s) {
  const warn = s.warnings.find((w) => w.level === 'warning');
  const names = s.people.map((p) => p.full_name);
  const hall = s.is_merged ? 'All halls' : s.hall_name || 'Hall to be confirmed';
  return html`<li><button class="ov-row ${warn ? 'warn' : ''} ${s.status === 'draft' ? 'draft' : ''}" style="${typeVars(s.session_type)}" data-act="ovOpen" data-id="${s.id}">
    <span class="ov-time"><b>${fmtTime(s.start_time)}</b><span>${fmtDur(s.duration_minutes) || 'check time'}</span></span>
    <span class="ov-bar"></span>
    <span class="ov-body">
      <span class="ov-tags"><em>${s.type_label}</em><span class="ov-hall ${s.is_merged ? 'merged' : ''}">${icon('pin', 'sm')} ${hall}</span>${s.status === 'draft' ? html`<span class="ov-draft">Draft</span>` : ''}</span>
      <strong>${s.title}</strong>
      ${names.length ? html`<span class="ov-people"><span class="ov-stack">${s.people.slice(0, 3).map((p) => avatar(p.full_name, p.photo_url, 'sm'))}</span>
        <span>${names.slice(0, 2).join(', ')}${names.length > 2 ? ` +${names.length - 2}` : ''}</span></span>` : ''}
      ${warn ? html`<span class="ov-warn">${icon('warning', 'sm')} ${warn.message}</span>` : ''}
    </span></button></li>`;
}

/* ---------------------------------------------------------------- side cards */
function attention(ev, sessions, flagged) {
  const unconfirmed = new Map();
  sessions.filter((s) => s.status === 'published').forEach((s) => s.people.filter((p) => p.status !== 'Confirmed').forEach((p) => unconfirmed.set(p.speaker_id, p)));
  const noHall = sessions.filter((s) => !s.is_merged && !s.hall_id).length;
  const items = [];
  flagged.slice(0, 4).forEach((s) => items.push(html`<button class="ov-item bad" data-act="ovOpen" data-id="${s.id}">${icon('warning', 'sm')}<span><b>${s.title}</b><small>${s.day_label.split(' — ')[0]}, ${fmtTime(s.start_time)}</small></span></button>`));
  if (flagged.length > 4) items.push(html`<a class="ov-item more" href="#/event/${ev.id}/sessions">${icon('right', 'sm')}<span>${flagged.length - 4} more with warnings</span></a>`);
  if (unconfirmed.size) items.push(html`<a class="ov-item warn" href="#/event/${ev.id}/speakers">${icon('eye', 'sm')}<span><b>${plural(unconfirmed.size, 'speaker')} not confirmed yet</b><small>Listed in published sessions but hidden on the website: ${[...unconfirmed.values()].slice(0, 2).map((p) => p.full_name).join(', ')}${unconfirmed.size > 2 ? '…' : ''}</small></span></a>`);
  if (noHall) items.push(html`<a class="ov-item warn" href="#/event/${ev.id}/sessions">${icon('pin', 'sm')}<span><b>${plural(noHall, 'session')} without a hall</b><small>Choose a hall for each.</small></span></a>`);
  return html`<section class="ov-card"><header><h2>Needs attention</h2>${items.length ? html`<span class="ov-count-pill">${flagged.length + unconfirmed.size + (noHall ? 1 : 0)}</span>` : ''}</header>
    ${items.length ? html`<div class="ov-items">${items}</div>` : html`<div class="ov-ok">${icon('check')}<span>${sessions.length ? 'All clear. Nothing needs attention.' : 'Schedule warnings will show up here.'}</span></div>`}</section>`;
}

const COLORS = { Confirmed: '#1b7f4d', Tentative: '#d49a14', Invited: '#2f5bd0', Declined: '#b3402f' };
function speakerCard(speakers, count, confirmed) {
  const total = speakers.length;
  let acc = 0;
  const stops = total ? Object.keys(COLORS).map((k) => { const a = acc; acc += (count(k) / total) * 100; return `${COLORS[k]} ${a}% ${acc}%`; }).join(',') : 'var(--sunk-2) 0 100%';
  return html`<section class="ov-card"><header><h2>Speakers</h2><a class="ov-link" href="#/event/${S.event.id}/speakers">View ${icon('right', 'sm')}</a></header>
    <div class="ov-donut-wrap"><div class="ov-donut" style="background:conic-gradient(${raw(stops)})"><div><b>${confirmed}</b><span>of ${total}</span></div></div>
      <ul class="ov-legend">${Object.keys(COLORS).map((k) => html`<li><i style="background:${COLORS[k]}"></i>${k}<b>${count(k)}</b></li>`)}</ul></div>
    ${total ? '' : html`<p class="muted small">Add speakers to track who has confirmed.</p>`}</section>`;
}

function setupCard(ev, sessions, speakers) {
  const steps = [['Add the event days', ev.days.length > 0, 'setup'], ['Add the halls in use', ev.halls.length > 0, 'setup'],
    ['Add the first speakers', speakers.length > 0, 'speakers'], ['Build the agenda', sessions.length > 0, 'sessions'],
    ['Enter the website address', !!ev.website_url, 'setup'], ['Set the event to Active', ev.status !== 'draft', 'setup']];
  const done = steps.filter((s) => s[1]).length;
  if (done === steps.length) return '';
  return html`<section class="ov-card"><header><h2>Getting set up</h2><span class="muted small">${done} of ${steps.length}</span></header>
    <div class="ov-progress"><i style="width:${(done / steps.length) * 100}%"></i></div>
    <ul class="ov-steps">${steps.map(([t, ok, tab]) => html`<li class="${ok ? 'done' : ''}"><span>${ok ? icon('check', 'sm') : ''}</span>${ok ? t : html`<a href="#/event/${ev.id}/${tab}">${t}</a>`}</li>`)}</ul></section>`;
}

acts({
  ovNew: () => { store.set('openSession', 'new'); location.hash = `#/event/${S.event.id}/sessions`; },
  ovOpen: (el) => { store.set('openSession', el.dataset.id); location.hash = `#/event/${S.event.id}/sessions`; },
  ovTab: (el) => {
    O.day = +el.dataset.id;
    $$('.ov-tabs button').forEach((b) => b.classList.toggle('on', b === el));
    mount($('#ovDay'), dayList());
  },
});