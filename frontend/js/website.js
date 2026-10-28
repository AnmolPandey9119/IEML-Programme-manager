import { api, S, acts, changes, inputs, html, icon, plural, copyText, toast, confirmDialog, $ } from './core.js';
import { STATUS_INFO } from './events.js';

const W = { accent: '#1d3f91', theme: 'light' };

export async function viewWebsite({ event: ev }) {
  const [sessions, speakers] = await Promise.all([api(`/events/${ev.id}/sessions`), api(`/events/${ev.id}/speakers`)]);
  const published = sessions.filter((s) => s.status === 'published'), drafts = sessions.length - published.length;
  const shown = new Map(), hidden = new Map();
  published.forEach((s) => s.people.forEach((p) => (p.status === 'Confirmed' ? shown : hidden).set(p.speaker_id, p)));
  const live = ev.status !== 'draft';
  const origin = location.origin;
  W.key = ev.public_key; W.origin = origin;
  const api_url = `${origin}/api/public/events/${ev.public_key}/agenda`;
  const admin = ev.my_role === 'admin';
  return html`
  <div class="page-head"><div class="t"><h1>Website</h1>
    <p>Your event website shows the agenda straight from this system. There is no upload step: save a session as Published and it appears on the website within 30 seconds.</p></div></div>

  <div class="panel" style="margin-bottom:22px"><div class="pad" style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">
    <span class="av" style="background:${live ? 'var(--green-soft)' : 'var(--amber-soft)'};color:${live ? 'var(--green)' : 'var(--amber)'};width:46px;height:46px">${icon(live ? 'globe' : 'lock', 'lg')}</span>
    <div style="flex:1;min-width:240px"><h3>${live ? 'Live on your website' : 'Not live yet'}</h3>
      <p class="soft">${live ? `The event is ${STATUS_INFO[ev.status][0]}. ${plural(published.length, 'published session')} and ${plural(shown.size, 'confirmed speaker')} are public.`
        : 'The event is in Draft, so nothing is public. Set the event to Active when you are ready to go live.'}</p></div>
    ${!live && admin ? html`<button class="btn primary" data-act="goLive">Make event Active</button>` : ''}</div>
    <div class="pad small soft" style="border-top:1px solid var(--rule-2);display:flex;gap:22px;flex-wrap:wrap">
      <span>${icon('eye', 'sm')} Published sessions: <b>${published.length}</b></span><span>${icon('lock', 'sm')} Draft sessions, never shown: <b>${drafts}</b></span>
      <span>${icon('mic', 'sm')} Speakers shown: <b>${shown.size}</b></span>
      <span>${icon('warning', 'sm')} Attached but not yet confirmed, hidden: <b>${hidden.size}</b></span></div></div>

  <section class="section"><div class="lead"><h3>Add the agenda to your website</h3><p>Paste one line where the agenda should appear. After that, no developer work is needed.</p></div>
    <div class="panel"><div class="pad">
      <div class="grid2"><label class="field"><span>Accent colour</span><input type="color" id="w_accent" value="${W.accent}" data-input="wChange" style="height:40px;padding:3px"></label>
        <label class="field"><span>Appearance</span><select id="w_theme" data-change="wChangeSel"><option value="light">Light</option><option value="dark">Dark</option><option value="auto">Match visitor’s device</option></select></label></div>
      <div class="code" id="w_code">${embedCode()}</div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap"><button class="btn primary" data-act="copyEmbed">${icon('copy', 'sm')} Copy code</button>
        <a class="btn" href="/preview.html?event=${ev.public_key}" target="_blank" rel="noopener">${icon('external', 'sm')} Open full preview</a></div>
      <p class="small muted" style="margin-top:12px">It draws the agenda inside its own protected container, so it will not clash with your site’s styles. Optional settings: <code>data-day</code>, <code>data-hall</code>, <code>data-photos="false"</code>, <code>data-header="false"</code>.</p>
    </div></div></section>

  <section class="section"><div class="lead"><h3>Live preview</h3><p>This is the real widget, reading the same public feed your website uses.</p></div>
    <div class="panel"><div class="pad" style="padding:0"><iframe id="w_frame" title="Agenda preview" src="${previewSrc()}" style="width:100%;height:560px;border:0;border-radius:var(--radius);background:#fff"></iframe></div></div></section>

  <section class="section"><div class="lead"><h3>Public data feed</h3><p>For developers who prefer to build their own page. Read-only JSON, no login.</p></div>
    <div class="panel"><div class="pad"><div class="copybox"><input readonly value="${api_url}" aria-label="Public feed address"><button class="btn" data-act="copyApi" data-url="${api_url}">${icon('copy', 'sm')} Copy</button>
      <a class="btn" href="${api_url}" target="_blank" rel="noopener">${icon('external', 'sm')} Open</a></div>
      <ul class="small soft" style="margin:14px 0 0;padding-left:18px;line-height:1.7"><li>Only <b>Published</b> sessions are included. Drafts are never shown.</li><li>A speaker appears only once their status is <b>Confirmed</b>.</li>
        <li>Email, phone, internal notes and draft content are never included.</li><li>Sessions in merged halls show the venue name instead of a hall.</li><li>Add <code>?day=ID</code> or <code>?hall=ID</code> to filter.</li></ul></div></div></section>`;
}
const embedCode = () => `<script src="${W.origin}/embed.js" data-event="${W.key}"${W.accent !== '#1d3f91' ? ` data-accent="${W.accent}"` : ''}${W.theme !== 'light' ? ` data-theme="${W.theme}"` : ''} async></script>`;
const previewSrc = () => `/preview.html?event=${W.key}&accent=${encodeURIComponent(W.accent)}&theme=${W.theme}`;
const refreshCode = () => { $('#w_code').textContent = embedCode(); $('#w_frame').src = previewSrc(); };

inputs({ wChange: (el) => { W.accent = el.value; $('#w_code').textContent = embedCode(); clearTimeout(W.t); W.t = setTimeout(refreshCode, 300); } });
changes({ wChangeSel: (el) => { W.theme = el.value; refreshCode(); } });
acts({
  copyEmbed: () => copyText(embedCode(), 'Embed code copied'),
  copyApi: (el) => copyText(el.dataset.url, 'Feed address copied'),
  goLive: async () => {
    if (!(await confirmDialog({ title: 'Make the event Active?', message: 'Published sessions and confirmed speakers become visible on your website.', confirmLabel: 'Go live' }))) return;
    await api('/events/' + S.event.id, 'PATCH', { status: 'active' }); toast('The event is live'); window.__refresh();
  },
});