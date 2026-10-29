import { api, S, acts, guard, html, icon, mount, setToken, val, raw_val, field, $ } from './core.js';

const art = html`<aside class="auth-art">
  <a class="brand" href="#/login"><span class="mark"><img src="/assets/ec-mark.png" alt=""></span><span class="brand-txt"><b>IEML EventCore</b><small>India Exposition Mart Ltd.</small></span></a>
  <div>
    <h1>Plan the whole programme in one place.</h1>
    <p>Sessions, speakers and committees for your organising team, kept in step with your event website.</p>
  </div>
  <div class="sched" aria-hidden="true">
    <div style="--c:#d9b560"><b>9:30 AM</b><span>Inaugural Session</span></div>
    <div style="--c:#56c0b6"><b>11:00 AM</b><span>Panel Discussion, Hall 4</span></div>
    <div style="--c:#9bb4ff"><b>2:00 PM</b><span>Workshop, Hall 5</span></div>
  </div>
</aside>`;

function authPage(inner) {
  mount($('#app'), html`<div class="auth-wrap">${art}<main class="auth-form"><div class="box"><div class="auth-mobile-brand"><span class="mark"><img src="/assets/ec-mark.png" alt=""></span><div><b>IEML EventCore</b><small>India Exposition Mart Ltd.</small></div></div>${inner}</div></main></div>`);
}

export async function viewLogin() {
  const { needs_setup } = await api('/auth/setup-status');
  if (needs_setup) { location.hash = '#/setup'; return; }
  authPage(html`<h2>Welcome back</h2><p class="lead">Sign in with the email address your invitation was sent to.</p>
    ${field('Email', html`<input id="email" type="email" autocomplete="username" data-autofocus>`)}
    ${field('Password', html`<input id="pw" type="password" autocomplete="current-password" data-enter="login">`)}
    <button class="btn primary block" data-act="login">Sign in</button>
    <p class="muted small" style="margin-top:16px">Access is by invitation only. Ask your event admin if you need an invite.</p>`);
  $('#email')?.focus();
}

export async function viewFirstSetup() {
  const { needs_setup } = await api('/auth/setup-status');
  if (!needs_setup) { location.hash = '#/login'; return; }
  authPage(html`<h2>Create the first admin account</h2><p class="lead">This one-time step creates the account that will own the system. Everyone else joins by invitation.</p>
    ${field('Full name', html`<input id="name" autocomplete="name">`)}
    ${field('Email', html`<input id="email" type="email" autocomplete="username">`)}
    ${field('Password', html`<input id="pw" type="password" autocomplete="new-password" data-enter="firstSetup">`, { hint: 'At least 8 characters.' })}
    <button class="btn primary block" data-act="firstSetup">Create account</button>`);
}

export async function viewInvite(token) {
  const inv = await api('/auth/invite/' + encodeURIComponent(token));
  S.inviteToken = token;
  authPage(html`<h2>Join ${inv.event_name}</h2>
    <p class="lead">You have been invited as <b>${inv.role}</b> using ${inv.email}.</p>
    ${inv.has_account
      ? field('Your existing password', html`<input id="pw" type="password" data-enter="acceptInvite">`, { hint: 'You already have an account, so enter your current password.' })
      : html`${field('Full name', html`<input id="name" autocomplete="name">`)}
             ${field('Choose a password', html`<input id="pw" type="password" autocomplete="new-password" data-enter="acceptInvite">`, { hint: 'At least 8 characters.' })}`}
    <button class="btn primary block" data-act="acceptInvite">Accept invitation</button>`);
}

const enter = async (r) => { setToken(r.access_token); S.me = null; location.hash = '#/events'; window.dispatchEvent(new HashChangeEvent('hashchange')); };
acts({
  login: async () => enter(await api('/auth/login', 'POST', { email: val('email'), password: raw_val('pw') })),
  firstSetup: async () => enter(await api('/auth/setup', 'POST', { full_name: val('name'), email: val('email'), password: raw_val('pw') })),
  acceptInvite: async () => enter(await api('/auth/accept-invite', 'POST', { token: S.inviteToken, password: raw_val('pw'), full_name: $('#name') ? val('name') : '' })),
});