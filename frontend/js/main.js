import { api, S, html, icon, mount, toast, $, logout, acts, esc, plural, brandInner, intPill } from './core.js';
import { viewLogin, viewFirstSetup, viewInvite } from './auth.js';
import { viewEvents, viewSetup, viewTeam } from './events.js';
import { viewSpeakers } from './speakers.js';
import { viewSessions } from './sessions.js';
import { viewOverview } from './overview.js';
import { viewLists } from './lists.js';
import { viewShared } from './shared.js';
import { viewInvites } from './invites.js';
import { viewSpeakerForm } from './speaker-form.js';
import { raw } from './core.js';
import { viewWebsite } from './website.js';
import './exports.js';

/* Tabs shown in the event sidebar. Each later phase adds its tab here. */
const TABS = [
  { key: 'overview', label: 'Overview', icon: 'home', view: viewOverview },
  { key: 'sessions', label: 'Sessions', icon: 'agenda', view: viewSessions, count: (c) => c.sessions },
  { key: 'speakers', label: 'Speakers', icon: 'mic', view: viewSpeakers, count: (c) => c.speakers },
  { key: 'invites', label: 'Speaker Invites', icon: 'mail', view: viewInvites, count: (c) => c.pending_applications },
  { key: 'lists', label: 'Lists & Meetings', icon: 'clipboard', view: viewLists, count: (c) => c.groups },
  { key: 'website', label: 'Website', icon: 'globe', view: viewWebsite },
  { key: 'team', label: 'Team', icon: 'users', view: viewTeam, group: 'manage' },
  { key: 'setup', label: 'Event setup', icon: 'sliders', view: viewSetup, group: 'manage' },
];

let renderToken = 0;
let cachedEventId = null; // same event ke tabs ke beech event dobara fetch na ho
window.__refresh = () => route(true);
window.addEventListener('hashchange', () => route());
window.addEventListener('load', () => route());

async function route(keepScroll = false) {
  const my = ++renderToken;
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  const y = window.scrollY;
  try {
    if (parts[0] === 'shared') return await viewShared(parts[1]);
    if (parts[0] === 'speaker-form') return parts[1] === 'open' ? await viewSpeakerForm(parts[2], true) : await viewSpeakerForm(parts[1]);
    if (parts[0] === 'invite') return await viewInvite(parts[1]);
    if (parts[0] === 'setup') return await viewFirstSetup();
    if (parts[0] === 'login') { if (S.token) { location.hash = '#/events'; return; } return await viewLogin(); }
    if (!S.token) { location.hash = '#/login'; return; }
    if (!S.me) S.me = await api('/auth/me');
    if (my !== renderToken) return;

    if (parts[0] === 'event' && parts[1]) {
      if (cachedEventId === parts[1] && S.event && !keepScroll) {
        // Tab switch: purana event turant use karein, taaki ek poora round-trip bache; counts peeche se refresh.
        api('/events/' + parts[1]).then((e) => { if (cachedEventId === parts[1]) S.event = e; }).catch(() => {});
      } else {
        S.event = await api('/events/' + parts[1]);
        cachedEventId = parts[1];
      }
      const tab = TABS.find((t) => t.key === parts[2]) || (S.event.halls.length ? TABS[0] : TABS.find((t) => t.key === 'setup'));
      if (!parts[2] && tab) { history.replaceState(null, '', `#/event/${S.event.id}/${tab.key}`); }
      const body = await tab.view({ event: S.event, param: parts[3], go: route });
      if (my !== renderToken) return;
      mount($('#app'), shell(tab, body));
    } else {
      cachedEventId = null;
      const body = await viewEvents();
      if (my !== renderToken) return;
      mount($('#app'), plainShell(body));
    }
    if (keepScroll) window.scrollTo(0, y); else window.scrollTo(0, 0);
    document.title = (S.event && parts[0] === 'event' ? S.event.name + ' · ' : '') + 'IEML EventCore';
  } catch (e) {
    if (e.status === 404 && parts[0] === 'event') { toast('That event was not found.', 'err'); location.hash = '#/events'; return; }
    toast(e.message, 'err');
  }
}

const themeBtn = raw('<button class="theme-btn" data-act="toggleTheme" aria-label="Switch between light and dark theme" title="Switch theme"><svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/></svg><svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button>');
const userBlock = () => html`<div class="me"><span class="av sm" style="background:#ffffff1f;color:#fff">${(S.me.user.full_name || S.me.user.email)[0].toUpperCase()}</span>
  <div class="who"><b>${S.me.user.full_name || S.me.user.email}</b><span>${S.event ? S.event.my_role : 'Signed in'}</span></div>
  ${themeBtn}<button data-act="logout" aria-label="Sign out" title="Sign out">${icon('logout')}</button></div>`;

function plainShell(body) {
  return html`<header class="plain-top"><a class="brand" href="#/events">${brandInner()}</a><span class="sp"></span>${intPill()}${themeBtn}
    <span class="soft small">${S.me.user.full_name || S.me.user.email}</span><button class="btn sm" data-act="logout">${icon('logout', 'sm')} Sign out</button></header>
    <main class="main"><div class="inner">${body}</div></main>`;
}

function shell(active, body) {
  const ev = S.event, c = ev.counts || {};
  const link = (t) => html`<a href="#/event/${ev.id}/${t.key}" class="${t.key === active.key ? 'on' : ''}">${icon(t.icon)}<span>${t.label}</span>${t.count && t.count(c) ? html`<span class="count num">${t.count(c)}</span>` : ''}</a>`;
  return html`<div class="shell">
    <aside class="rail" id="rail">
      <a class="brand" href="#/events">${brandInner({ pill: true })}</a>
      <a class="ev-card" href="#/events" title="Switch event"><b>${ev.name}${ev.edition ? ' ' + ev.edition : ''}</b>
        <span>${[ev.venue_city, ev.status[0].toUpperCase() + ev.status.slice(1)].filter(Boolean).join(', ')}</span></a>
      <nav class="nav" aria-label="Event sections">${TABS.filter((t) => !t.group).map(link)}<div class="sep"></div>${TABS.filter((t) => t.group).map(link)}</nav>
      <div class="grow"></div>${userBlock()}
    </aside>
    <div><div class="topbar"><button data-act="toggleRail" aria-label="Open menu">${icon('menu', 'lg')}</button><b>${ev.name}</b></div>
      <main class="main"><div class="inner">
        ${ev.status === 'archived' ? html`<div class="banner">${icon('archive', 'sm')}<span>This event is archived and read-only. An admin can set it back to Active in Event setup.</span></div>` : ''}
        ${body}</div></main></div></div>`;
}

acts({
  logout: () => logout(),
  toggleRail: () => $('#rail').classList.toggle('open'),
});
document.addEventListener('click', (e) => { if (e.target.closest('.nav a')) $('#rail')?.classList.remove('open'); });