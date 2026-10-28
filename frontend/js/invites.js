import {
    api, S, acts, html, icon, raw, val, field, plural, fmtTime, copyText, openPanel, confirmDialog, toast, mount, $, $$, topPanel,
  } from './core.js';
  
  /* Speaker Invites tab: invite speakers by email, read what they filled in, add or reject them, assign sessions. */
  const V = { ev: null, tab: 'pending', apps: [], invites: [], sessions: null };
  const admin = () => V.ev.my_role === 'admin' && V.ev.status !== 'archived';
  const canAssign = () => ['admin', 'editor'].includes(V.ev.my_role) && V.ev.status !== 'archived';
  const TABS = [['pending', 'Pending'], ['approved', 'Added'], ['rejected', 'Rejected'], ['invites', 'Invitations sent']];
  const pillFor = { pending: ['amber', 'Pending review'], approved: ['green', 'Added'], rejected: ['brick', 'Rejected'] };
  
  const when = (s) => {
    if (!s) return '';
    const d = new Date(/Z|[+-]\d\d:?\d\d$/.test(s) ? s : s + 'Z');
    return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
  };
  const snippet = (t, n = 90) => { t = (t || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
  
  export async function viewInvites({ event }) {
    V.ev = event;
    await load();
    return html`
    <div class="page-head"><div class="t"><h1>Speaker Invites</h1>
      <p>Send speakers a personal form link. Their answers arrive here for you to add or reject, and then to place in a session.</p></div>
      <div class="actions">${admin() ? html`<button class="btn primary" data-act="newInvites">${icon('mail', 'sm')} Invite speakers</button>` : ''}</div></div>
    <div class="toolbar"><div class="seg" id="ivTabs">${tabs()}</div></div>
    <div id="ivBody">${body()}</div>`;
  }
  
  async function load() {
    [V.apps, V.invites] = await Promise.all([
      api(`/events/${V.ev.id}/speaker-applications`), api(`/events/${V.ev.id}/speaker-invites`)]);
  }
  const count = (k) => (k === 'invites' ? V.invites.length : V.apps.filter((a) => a.status === k).length);
  const tabs = () => TABS.map(([k, l]) => html`<button class="${V.tab === k ? 'on' : ''}" data-act="ivTab" data-v="${k}">${l} <span class="n">${count(k)}</span></button>`);
  const repaint = () => { mount($('#ivTabs'), tabs()); mount($('#ivBody'), body()); };
  const closeAll = () => { while (topPanel()) topPanel().close(); };
  /** Keeps the sidebar badge in step without re-rendering the whole page. */
  function syncBadge() {
    const a = $(`.nav a[href$="/invites"]`); if (!a) return;
    const n = count('pending'); let c = a.querySelector('.count');
    if (!n) { c?.remove(); return; }
    if (!c) { c = document.createElement('span'); c.className = 'count num'; a.append(c); }
    c.textContent = n;
  }
  async function reload() { await load(); if ($('#ivBody')) repaint(); syncBadge(); }
  
  function body() { return V.tab === 'invites' ? invitesTable() : responsesTable(); }
  
  function responsesTable() {
    const rows = V.apps.filter((a) => a.status === V.tab);
    if (!rows.length) {
      const msg = { pending: ['No responses waiting', 'When a speaker submits the form, it shows up here for review.'],
        approved: ['Nobody added yet', 'Speakers you approve are added to the Speakers tab and listed here.'],
        rejected: ['Nothing rejected', 'Responses you reject are kept here, and you can restore them.'] }[V.tab];
      return html`<div class="panel"><div class="empty"><div class="art">${icon('mail', 'lg')}</div><h3>${msg[0]}</h3><p>${msg[1]}</p>
        ${V.tab === 'pending' && admin() && !V.invites.length ? html`<button class="btn primary" data-act="newInvites">${icon('mail', 'sm')} Invite your first speaker</button>` : ''}</div></div>`;
    }
    return html`<div class="panel"><div class="table-wrap"><table class="t"><thead><tr><th>Speaker</th><th>Wants to speak on</th><th>Formats</th><th>Received</th><th></th></tr></thead>
      <tbody>${rows.map((a) => html`<tr data-act="openApp" data-id="${a.id}" style="cursor:pointer">
        <td><b>${a.full_name}</b><div class="small muted">${[a.designation, a.organisation].filter(Boolean).join(', ')}</div></td>
        <td class="small">${snippet(a.topics || a.proposed_title) || html`<span class="muted">Not filled in</span>`}</td>
        <td class="small">${a.formats.join(', ') || html`<span class="muted">Any</span>`}</td>
        <td class="small muted">${when(a.submitted_at)}</td>
        <td class="right"><span class="pill ${pillFor[a.status][0]}">${pillFor[a.status][1]}</span></td></tr>`)}</tbody></table></div></div>`;
  }
  
  function invitesTable() {
    if (!V.invites.length) {
      return html`<div class="panel"><div class="empty"><div class="art">${icon('mail', 'lg')}</div><h3>No invitations yet</h3><p>Invite speakers by email, or copy one link and send it to anyone yourself.</p>
        ${admin() ? html`<button class="btn primary" data-act="newInvites">${icon('mail', 'sm')} Invite speakers</button>` : ''}</div></div>`;
    }
    return html`<div class="panel"><div class="table-wrap"><table class="t"><thead><tr><th>Invited</th><th>Email sent</th><th>Form</th><th></th></tr></thead>
      <tbody>${V.invites.map((i) => html`<tr><td><b>${i.name || i.email}</b>${i.name ? html`<div class="small muted">${i.email}</div>` : ''}</td>
        <td class="small">${i.email_sent ? html`<span class="pill green">Sent ${when(i.last_sent_at)}</span>` : html`<span class="pill">Not emailed</span>`}</td>
        <td class="small">${i.submitted ? html`<a href="#" data-act="openApp" data-id="${i.application_id}">${pillFor[i.application_status]?.[1] || 'Received'}</a>` : html`<span class="muted">Waiting for response</span>`}</td>
        <td class="right" style="white-space:nowrap"><button class="btn sm" data-act="copyInvite" data-id="${i.id}">${icon('copy', 'sm')} Copy link</button>
          ${admin() ? html`<button class="btn sm quiet" data-act="resendInvite" data-id="${i.id}">Resend</button><button class="btn sm quiet danger" data-act="deleteInvite" data-id="${i.id}" aria-label="Delete invitation">${icon('trash', 'sm')}</button>` : ''}</td></tr>`)}</tbody></table></div></div>`;
  }
  
  /* ---------------------------------------------------------------- invite dialog */
  function parseInvitees(text) {
    const out = [], bad = [];
    for (const line of text.split(/\n|;/).map((l) => l.trim()).filter(Boolean)) {
      const m = /<([^>]+)>/.exec(line);
      const email = (m ? m[1] : (line.match(/[^\s,<>]+@[^\s,<>]+\.[^\s,<>]+/) || [''])[0]).trim();
      if (!email) { bad.push(line); continue; }
      const name = line.replace(/<[^>]+>/, '').replace(email, '').replace(/[,"]/g, '').trim();
      out.push({ name, email });
    }
    return { out, bad };
  }
  
  let linkState = null;
  
  function linkPane() {
    const l = linkState;
    if (!l) return html`<p class="muted small">Loading…</p>`;
    if (!l.enabled) {
      return html`<div class="note">${icon('link', 'sm')}<span>Create one link and send it to anyone yourself: WhatsApp, LinkedIn, a personal email. Whoever opens it fills the same form, and their answers land in <b>Pending</b> for you to review.</span></div>
        <button class="btn primary" data-act="createLink">${icon('link', 'sm')} Create invite link</button>`;
    }
    return html`<div class="copybox"><input readonly id="lk_url" value="${l.link}" aria-label="Speaker form link" onclick="this.select()">
        <button class="btn primary" data-act="copyOpenLink">${icon('copy', 'sm')} Copy link</button></div>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap"><a class="btn sm" href="${l.link}" target="_blank" rel="noopener">${icon('external', 'sm')} Open the form</a>
        <button class="btn sm quiet" data-act="renewLink">${icon('refresh', 'sm')} Replace link</button>
        <button class="btn sm quiet danger" data-act="disableLink">Switch off</button></div>
      <ul class="small soft" style="margin:14px 0 0;padding-left:18px;line-height:1.7"><li>This one link works for everyone. Anyone who has it can send the form, so share it only with people you want to invite.</li>
        <li>Responses are never added automatically. You review each one first.</li>
        <li>If it spreads too far, use <b>Replace link</b> (the old one stops working) or <b>Switch off</b>.</li></ul>`;
  }
  
  async function openInviteDialog() {
    linkState = null;
    openPanel({
      title: 'Invite speakers', subtitle: 'Send the speaker form by email, or copy a link and send it yourself.', wide: true,
      body: html`
        <div class="seg" id="iv_mode" style="margin-bottom:16px"><button class="on" data-act="ivMode" data-v="email">${icon('mail', 'sm')} Invite by email</button>
          <button data-act="ivMode" data-v="link">${icon('link', 'sm')} Invite by link</button></div>
        <div id="iv_email">
          ${field('Who to invite', html`<textarea id="iv_list" rows="6" placeholder="One per line, for example:&#10;Dr. Meera Iyer &lt;meera@greenpack.com&gt;&#10;rahul@company.com"></textarea>`,
            { hint: 'Name and email, or just the email. You can paste a whole list. Each person gets their own link.' })}
          ${field('Personal note', html`<textarea id="iv_msg" rows="3" placeholder="Optional. Added to the email, for example why you are inviting them."></textarea>`, { optional: true })}
          <label class="switch-row" style="padding:6px 0"><div><b>Send the email now</b><span class="d">Turn off to only create the links and share them yourself.</span></div>
            <input type="checkbox" id="iv_send" checked></label></div>
        <div id="iv_link" class="hide">${linkPane()}</div>`,
      footer: html`<span class="sp"></span><button class="btn" data-close id="iv_close">Cancel</button><button class="btn primary" data-act="sendInvites" id="iv_sendbtn">Send invitations</button>`,
    });
    try { linkState = await api(`/events/${V.ev.id}/speaker-form-link`); } catch { linkState = { enabled: false }; }
    if ($('#iv_link')) mount($('#iv_link'), linkPane());
  }
  const paintLink = () => { if ($('#iv_link')) mount($('#iv_link'), linkPane()); };
  
  /* ---------------------------------------------------------------- response drawer */
  async function sessionList() {
    if (!V.sessions) V.sessions = await api(`/events/${V.ev.id}/sessions`);
    return V.sessions;
  }
  const sessLabel = (s) => `${s.day_label.split(' — ')[0]} · ${fmtTime(s.start_time)} · ${s.title} (${s.hall_name || 'Hall to be confirmed'})`;
  const sessOptions = (list, placeholder) => raw(`<option value="">${placeholder}</option>` + list.map((s) =>
    `<option value="${s.id}">${sessLabel(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))}</option>`).join(''));
  
  const row = (label, v) => (v ? html`<dt>${label}</dt><dd style="white-space:pre-wrap">${v}</dd>` : '');
  
  async function openApp(id, keep) {
    const a = await api(`/events/${V.ev.id}/speaker-applications/${id}`);
    V.sessions = null;
    const sessions = a.speaker_id && canAssign() ? await sessionList() : [];
    const draw = (x) => ({
      title: x.full_name, subtitle: [x.designation, x.organisation].filter(Boolean).join(', ') || 'Speaker form response',
      body: html`
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px"><span class="pill ${pillFor[x.status][0]}">${pillFor[x.status][1]}</span>
          <span class="small muted">Received ${when(x.submitted_at)} · ${x.invited ? 'personal email invitation' : 'shared invite link'}</span></div>
        ${x.review_note ? html`<div class="note amber">${icon('info', 'sm')}<span>${x.review_note}</span></div>` : ''}
        <div class="form-section">About the speaker</div>
        <dl class="kv">${row('Email', x.email)}${row('Phone', x.phone)}${row('Based in', x.city_country)}${row('LinkedIn', x.linkedin_url)}${row('Website', x.website_url)}${row('Bio', x.bio)}</dl>
        <div class="form-section">Expertise and topics</div>
        <dl class="kv">${row('Expertise', x.expertise)}${row('Wants to speak on', x.topics)}${row('Past speaking', x.past_speaking)}</dl>
        <div class="form-section">Proposed session</div>
        <dl class="kv">${row('Title idea', x.proposed_title)}${row('Summary', x.abstract)}${row('Takeaways', x.key_takeaways)}${row('Formats', x.formats.join(', '))}${row('Available on', x.availability.join(', '))}</dl>
        <div class="form-section">Logistics</div>
        <dl class="kv">${row('Requirements', x.requirements)}${row('Anything else', x.extra_notes)}</dl>
        ${x.status === 'approved' ? assignBlock(x, sessions) : ''}`,
      footer: html`${admin() ? html`<button class="btn quiet danger" data-act="deleteApp" data-id="${x.id}">${icon('trash', 'sm')} Delete response</button>` : ''}<span class="sp"></span>
        <button class="btn" data-close>Close</button>
        ${admin() && x.status === 'pending' ? html`<button class="btn danger" data-act="rejectApp" data-id="${x.id}">Reject</button><button class="btn primary" data-act="approveApp" data-id="${x.id}">${icon('check', 'sm')} Add as speaker</button>` : ''}
        ${admin() && x.status === 'rejected' ? html`<button class="btn" data-act="restoreApp" data-id="${x.id}">Move back to pending</button>` : ''}`,
    });
    const d = draw(a);
    if (keep && topPanel()) { topPanel().setBody(d.body); topPanel().setFooter(d.footer); return; }
    openPanel({ kind: 'drawer', ...d });
  }
  
  function assignBlock(x, sessions) {
    return html`<div class="form-section">Sessions</div>
      <p class="small muted" style="margin-bottom:8px">In the Speakers tab as <b>${x.speaker_status}</b>. They appear on the public website once Confirmed and the session is Published.</p>
      ${x.sessions.length ? x.sessions.map((r) => html`<div class="sess-ref"><b>${r.title}</b><span class="pill teal">${r.role}</span>
        <span class="small muted">${r.day_label}, ${fmtTime(r.start_time)} to ${fmtTime(r.end_time)} · ${r.hall}</span>
        ${canAssign() ? html`<button class="btn sm quiet danger" data-act="unassign" data-sid="${r.session_id}" data-id="${x.id}">Remove</button>` : ''}</div>`)
        : html`<p class="muted small">Not in any session yet.</p>`}
      ${canAssign() ? html`<div class="inline-form" style="margin-top:12px">
        <label class="field" style="flex:2;min-width:220px"><span>Add to a session</span><select id="as_session">${sessOptions(sessions, 'Choose a session')}</select></label>
        <label class="field"><span>As</span><select id="as_role"><option value="speaker">Speaker</option><option value="panelist">Panelist</option><option value="moderator">Moderator</option></select></label>
        <button class="btn primary" data-act="assignApp" data-id="${x.id}" style="margin-bottom:14px">Assign</button></div>
        ${sessions.length ? '' : html`<p class="small muted">No sessions exist yet. Create one in the Sessions tab, then come back to assign.</p>`}` : ''}`;
  }
  
  async function approveDialog(id) {
    const a = V.apps.find((x) => x.id == id);
    const sessions = canAssign() ? await sessionList() : [];
    openPanel({
      title: `Add ${a.full_name} as a speaker`, subtitle: 'They will appear in the Speakers tab with the details from their form.',
      body: html`
        <div class="form-section">Speaker status</div>
        <div class="seg status" id="ap_seg" style="margin-bottom:12px">${['Confirmed', 'Tentative', 'Invited'].map((s) => html`<button type="button" class="${s === 'Tentative' ? 'on' : ''}" data-act="apStatus" data-v="${s}"><span class="dot ${s.toLowerCase()}"></span>${s}</button>`)}</div>
        <p class="small muted" id="ap_note">Tentative speakers stay off the public website until you set them to Confirmed.</p>
        ${field('Remark', html`<input id="ap_remark" placeholder="Optional, for example “Applied through the speaker form”">`, { optional: true })}
        <div class="form-section">Session</div>
        ${field('Assign to a session now', html`<select id="ap_session">${sessOptions(sessions, 'Not now, I will assign later')}</select>`, { optional: true })}
        ${field('Role in that session', html`<select id="ap_role"><option value="speaker">Speaker</option><option value="panelist">Panelist</option><option value="moderator">Moderator</option></select>`)}`,
      footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn primary" data-act="confirmApprove" data-id="${id}">Add speaker</button>`,
    });
    apStatus = 'Tentative';
  }
  
  /* ---------------------------------------------------------------- actions */
  let apStatus = 'Tentative';
  acts({
    ivMode: (el) => {
      const link = el.dataset.v === 'link';
      $$('#iv_mode button').forEach((b) => b.classList.toggle('on', b === el));
      $('#iv_email').classList.toggle('hide', link); $('#iv_link').classList.toggle('hide', !link);
      $('#iv_sendbtn').classList.toggle('hide', link); $('#iv_close').textContent = link ? 'Done' : 'Cancel';
    },
    createLink: async () => { linkState = await api(`/events/${V.ev.id}/speaker-form-link`, 'PUT', { enabled: true }); paintLink(); },
    copyOpenLink: () => copyText(linkState.link, 'Invite link copied. Send it to anyone you want to invite.'),
    renewLink: async () => {
      if (!(await confirmDialog({ title: 'Replace the invite link?', confirmLabel: 'Replace link',
        message: 'The current link stops working straight away. Send the new link to anyone who still needs it. Responses already received are kept.' }))) return;
      linkState = await api(`/events/${V.ev.id}/speaker-form-link/renew`, 'POST'); paintLink(); toast('New link created');
    },
    disableLink: async () => {
      if (!(await confirmDialog({ title: 'Switch the invite link off?', confirmLabel: 'Switch off', danger: true,
        message: 'Nobody can open the form with this link any more. Responses already received are kept. You can create a new link later.' }))) return;
      linkState = await api(`/events/${V.ev.id}/speaker-form-link`, 'PUT', { enabled: false }); paintLink(); toast('Invite link switched off');
    },
    ivTab: (el) => { V.tab = el.dataset.v; repaint(); },
    newInvites: () => openInviteDialog(),
    openApp: (el) => openApp(el.dataset.id),
    sendInvites: async (btn) => {
      const { out, bad } = parseInvitees($('#iv_list').value);
      if (!out.length) { $('#iv_list').focus(); throw new Error('Add at least one email address.'); }
      btn.disabled = true;
      try {
        const r = await api(`/events/${V.ev.id}/speaker-invites`, 'POST', { invitees: out, message: val('iv_msg'), send_email: $('#iv_send').checked });
        topPanel()?.close();
        toast(r.emailed ? `${plural(r.emailed, 'invitation')} sent by email.` : `${plural(r.invites.length, 'invitation link')} created. Email is not set up on this server, so copy the links and share them.`);
        if (bad.length) toast(`Skipped lines without an email: ${bad.slice(0, 2).join(' | ')}`, 'err');
        V.tab = 'invites'; await reload();
      } finally { btn.disabled = false; }
    },
    copyInvite: (el) => copyText(V.invites.find((i) => i.id == el.dataset.id).link, 'Invitation link copied'),
    resendInvite: async (el) => { await api(`/events/${V.ev.id}/speaker-invites/${el.dataset.id}/resend`, 'POST'); toast('Invitation email queued'); await reload(); },
    deleteInvite: async (el) => {
      const i = V.invites.find((x) => x.id == el.dataset.id);
      if (!(await confirmDialog({ title: `Delete the invitation for ${i.name || i.email}?`, confirmLabel: 'Delete invitation', danger: true,
        message: 'Their link stops working. If they already submitted the form, that response is kept.' }))) return;
      await api(`/events/${V.ev.id}/speaker-invites/${i.id}`, 'DELETE'); toast('Invitation deleted'); await reload();
    },
    approveApp: (el) => approveDialog(el.dataset.id),
    apStatus: (el) => {
      apStatus = el.dataset.v;
      $$('#ap_seg button').forEach((b) => b.classList.toggle('on', b === el));
      $('#ap_note').textContent = apStatus === 'Confirmed' ? 'Confirmed speakers appear on the public website next to published sessions. The team gets an email.' : 'Not confirmed speakers stay off the public website until you set them to Confirmed.';
    },
    confirmApprove: async (btn) => {
      btn.disabled = true;
      try {
        const sid = $('#ap_session').value;
        await api(`/events/${V.ev.id}/speaker-applications/${btn.dataset.id}/approve`, 'POST',
          { speaker_status: apStatus, note: val('ap_remark'), session_id: sid ? +sid : null, role: $('#ap_role').value });
        toast(sid ? 'Speaker added and assigned to the session' : 'Speaker added to the Speakers tab');
        closeAll(); V.tab = 'approved'; await reload();
      } finally { btn.disabled = false; }
    },
    rejectApp: async (el) => {
      const a = V.apps.find((x) => x.id == el.dataset.id);
      openPanel({ title: `Reject ${a.full_name}?`, subtitle: 'They are not added to the Speakers tab. You can restore this later.',
        body: field('Note for the team', html`<textarea id="rj_note" rows="3" placeholder="Optional, for example “Topic overlaps with another speaker”"></textarea>`, { optional: true }),
        footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn solid-danger" data-act="confirmReject" data-id="${a.id}">Reject</button>` });
    },
    confirmReject: async (btn) => {
      await api(`/events/${V.ev.id}/speaker-applications/${btn.dataset.id}/reject`, 'POST', { note: val('rj_note') });
      closeAll(); toast('Response rejected'); await reload();
    },
    restoreApp: async (el) => {
      await api(`/events/${V.ev.id}/speaker-applications/${el.dataset.id}/restore`, 'POST');
      topPanel()?.close(); toast('Moved back to pending'); V.tab = 'pending'; await reload();
    },
    deleteApp: async (el) => {
      const a = V.apps.find((x) => x.id == el.dataset.id);
      if (!(await confirmDialog({ title: `Delete the response from ${a.full_name}?`, confirmLabel: 'Delete response', danger: true,
        message: a.speaker_id ? 'This only deletes the form response. The speaker stays in the Speakers tab.' : 'This cannot be undone.' }))) return;
      await api(`/events/${V.ev.id}/speaker-applications/${a.id}`, 'DELETE');
      topPanel()?.close(); toast('Response deleted'); await reload();
    },
    assignApp: async (el) => {
      const a = V.apps.find((x) => x.id == el.dataset.id), sid = $('#as_session').value;
      if (!sid) throw new Error('Choose a session first.');
      const s = await api(`/events/${V.ev.id}/sessions/${sid}/people`, 'POST', { speaker_id: a.speaker_id, role: $('#as_role').value });
      const warn = s.warnings.filter((w) => w.level !== 'info');
      warn.length ? toast('Assigned, but check the schedule: ' + warn[0].message, 'err') : toast(`Assigned to “${s.title}”`);
      V.sessions = null; await openApp(a.id, true); await reload();
    },
    unassign: async (el) => {
      await api(`/events/${V.ev.id}/sessions/${el.dataset.sid}/people/${V.apps.find((x) => x.id == el.dataset.id).speaker_id}`, 'DELETE');
      toast('Removed from the session'); V.sessions = null; await openApp(el.dataset.id, true); await reload();
    },
  });