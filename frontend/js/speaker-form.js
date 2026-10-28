import { api, acts, html, icon, raw, val, field, mount, toast, $, $$ } from './core.js';

/* Public speaker form. Opened from a personal link in an email, no sign-in. */
const F = { token: '', info: null, open: false };
const path = () => `/public/speaker-form/${F.open ? 'open/' : ''}${encodeURIComponent(F.token)}`;

const shell = (inner) => mount($('#app'), html`<header class="plain-top"><span class="brand"><span class="mark"><img src="/assets/ieml-logo.png" alt=""></span><span class="brand-txt"><b>${F.info ? F.info.event_name : 'Speaker form'}</b><small>India Exposition Mart Ltd.</small></span></span></header>
  <main class="shared-wrap pubform">${inner}</main>`);

const message = (art, title, text) => html`<div class="panel"><div class="empty"><div class="art">${icon(art, 'lg')}</div><h3>${title}</h3><p>${text}</p></div></div>`;

export async function viewSpeakerForm(token, open = false) {
  F.token = token; F.open = open;
  try { F.info = await api(path()); }
  catch {
    F.info = null; document.title = 'Speaker form';
    return shell(message('lock', 'This link is not available', 'It may have been switched off or replaced. Please contact the organising team for a new invitation.'));
  }
  const i = F.info;
  document.title = `Speaker form · ${i.event_name}`;
  if (i.status === 'closed') return shell(message('lock', 'This event is closed', 'The event is no longer taking speaker details.'));
  if (i.status === 'approved') return shell(message('check', 'You are on the speaker list', 'The team has added you as a speaker. They will be in touch about your session. To change anything, please reply to their email.'));
  if (i.status === 'rejected') return shell(message('info', 'Thank you for your interest', 'The team has reviewed your response and will contact you directly if anything changes.'));
  renderForm();
}

const chk = (name, v, on) => html`<label class="chk"><input type="checkbox" name="${name}" value="${v}" ${on ? 'checked' : ''}><span>${v}</span></label>`;

function renderForm() {
  const i = F.info, v = i.values || {};
  const pending = i.status === 'pending';
  const t = (id, label, key, opts = {}) => field(label, html`<input id="${id}" value="${v[key] ?? opts.def ?? ''}" ${opts.ph ? html`placeholder="${opts.ph}"` : ''} ${opts.type ? html`type="${opts.type}"` : ''} autocomplete="${opts.ac || 'off'}">`, { optional: opts.opt, hint: opts.hint });
  const ta = (id, label, key, rows, ph, opts = {}) => field(label, html`<textarea id="${id}" rows="${rows}" placeholder="${ph}">${v[key] ?? ''}</textarea>`, opts);
  shell(html`
    <h1>${i.event_name}${i.edition ? ' ' + i.edition : ''}</h1>
    <p class="soft" style="margin:6px 0 22px">${[i.venue, i.theme_line].filter(Boolean).join(' · ')}</p>
    <div class="note">${icon('mail', 'sm')}<span>${i.invitee_name ? `Dear ${i.invitee_name}, we` : 'We'} would be glad to have you as a speaker. Please tell us about yourself and what you would like to speak on. It takes about five minutes.${i.message ? ' ' + i.message : ''}</span></div>
    ${pending ? html`<div class="note amber">${icon('info', 'sm')}<span>You have already sent this form. You can change your answers below and send it again until the team reviews it.</span></div>` : ''}
    <div class="panel"><div class="pad">
      <div class="form-section">About you</div>
      ${t('f_name', 'Full name', 'full_name', { def: i.invitee_name, ph: 'Dr. Meera Iyer', ac: 'name' })}
      <div class="grid2">${t('f_desig', 'Designation', 'designation', { ph: 'Managing Director' })}${t('f_org', 'Organisation', 'organisation', { ph: 'Company or institution', ac: 'organization' })}</div>
      <div class="grid2">${t('f_email', 'Email', 'email', { def: i.invitee_email, type: 'email', ac: 'email', hint: F.open ? 'We will reply to this address.' : '' })}${t('f_phone', 'Phone', 'phone', { type: 'tel', ph: '+91 98xxx xxxxx', opt: true, ac: 'tel' })}</div>
      ${t('f_city', 'City and country', 'city_country', { ph: 'Mumbai, India', opt: true })}
      ${ta('f_bio', 'Short bio', 'bio', 4, 'A short paragraph about your work and background. This may be shown on the event website.', {})}
      <div class="grid2">${t('f_li', 'LinkedIn', 'linkedin_url', { ph: 'linkedin.com/in/…', opt: true })}${t('f_web', 'Website', 'website_url', { ph: 'www.example.com', opt: true })}</div>

      <div class="form-section">Your expertise</div>
      ${ta('f_exp', 'Areas of expertise', 'expertise', 3, 'For example: sustainable packaging, EPR compliance, food-grade materials', { hint: 'The subjects you know best.' })}
      ${ta('f_topics', 'What would you like to speak about?', 'topics', 4, 'The topics or questions you would like to take up at the event.')}
      ${ta('f_past', 'Past speaking experience', 'past_speaking', 3, 'Events, panels or talks you have done before. Links are welcome.', { optional: true })}

      <div class="form-section">Your session idea</div>
      ${t('f_title', 'Proposed session title', 'proposed_title', { ph: 'Optional, a working title is fine', opt: true })}
      ${ta('f_abs', 'Short summary', 'abstract', 4, 'What will the audience hear and see?', { optional: true })}
      ${ta('f_take', 'What will the audience take away?', 'key_takeaways', 3, 'Two or three points.', { optional: true })}
      <div class="field"><span>Preferred format <em>(choose any)</em></span><div class="chk-grid">${i.formats.map((f) => chk('fmt', f, (v.formats || []).includes(f)))}</div></div>
      ${i.days.length ? html`<div class="field"><span>Days you can attend <em>(choose any)</em></span><div class="chk-grid">${i.days.map((d) => chk('day', d, (v.availability || []).includes(d)))}</div></div>` : ''}

      <div class="form-section">Anything we should plan for</div>
      ${ta('f_req', 'Requirements', 'requirements', 3, 'Audio-visual needs, travel or stay support, dietary needs, accessibility.', { optional: true })}
      ${ta('f_note', 'Anything else', 'extra_notes', 3, 'Anything you would like the team to know.', { optional: true })}

      <input id="f_hp" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;opacity:0">
      <label class="chk consent"><input type="checkbox" id="f_consent"><span>I confirm these details are correct and the organisers may use them to plan the programme and, if I am confirmed, to publish my name, designation, organisation, photo and bio on the event website.</span></label>
      <div style="margin-top:18px"><button class="btn primary" data-act="sendForm" id="f_send">${pending ? 'Send updated form' : 'Send form'}</button></div>
    </div></div>`);
}

acts({
  sendForm: async (btn) => {
    if (!val('f_name')) { $('#f_name').focus(); throw new Error('Please enter your full name.'); }
    if (!val('f_email')) { $('#f_email').focus(); throw new Error('Please enter your email address.'); }
    if (!$('#f_consent').checked) throw new Error('Please tick the confirmation box at the end of the form.');
    btn.disabled = true;
    try {
      const body = {
        full_name: val('f_name'), designation: val('f_desig'), organisation: val('f_org'), email: val('f_email'), phone: val('f_phone'),
        city_country: val('f_city'), bio: val('f_bio'), linkedin_url: val('f_li'), website_url: val('f_web'),
        expertise: val('f_exp'), topics: val('f_topics'), past_speaking: val('f_past'), proposed_title: val('f_title'),
        abstract: val('f_abs'), key_takeaways: val('f_take'), requirements: val('f_req'), extra_notes: val('f_note'),
        formats: $$('input[name=fmt]:checked').map((e) => e.value), availability: $$('input[name=day]:checked').map((e) => e.value),
        consent: true, hp: val('f_hp'),
      };
      const r = await api(path(), 'POST', body);
      window.scrollTo(0, 0);
      shell(message('check', r.updated ? 'Your form has been updated' : 'Thank you, we have your details',
        F.open ? 'The organising team will review your response and get back to you by email. If you need to change something, send the form again with the same email address before they review it.' : 'The organising team will review your response and get back to you by email. You can reopen your invitation link to change your answers until they have reviewed it.'));
    } finally { btn.disabled = false; }
  },
});