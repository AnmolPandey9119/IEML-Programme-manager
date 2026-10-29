import { api, html, icon, mount, $ } from './core.js';

/** Public, read-only member list. No sign-in. */
export async function viewShared(token) {
  try {
    const d = await api('/public/groups/' + encodeURIComponent(token));
    document.title = `${d.group_name} · ${d.event_name}`;
    mount($('#app'), html`<header class="plain-top"><span class="brand"><span class="mark"><img src="/assets/ec-mark.png" alt=""></span><span class="brand-txt"><b>IEML EventCore</b><small>India Exposition Mart Ltd.</small></span></span><span class="sp"></span>
        <button class="btn sm no-print" onclick="window.print()">Print</button></header>
      <main class="shared-wrap"><h1>${d.group_name}</h1><p class="soft" style="margin:4px 0 22px">${d.event_name}, ${d.group_type}. Read-only member list.</p>
        <div class="panel"><div class="table-wrap"><table class="t"><thead><tr><th>Name</th><th>Designation</th><th>Organisation</th><th>Role</th>${d.include_contacts ? html`<th>Contact</th>` : ''}</tr></thead>
          <tbody>${d.members.map((m) => html`<tr><td><b>${m.name}</b></td><td>${m.designation}</td><td>${m.organisation}</td><td>${m.role_in_group}</td>
            ${d.include_contacts ? html`<td class="small">${m.email}${m.email && m.phone ? html`<br>` : ''}${m.phone}</td>` : ''}</tr>`)}
            ${d.members.length ? '' : html`<tr><td colspan="5" class="muted">No members have been added yet.</td></tr>`}</tbody></table></div></div></main>`);
  } catch {
    mount($('#app'), html`<main class="shared-wrap"><div class="panel"><div class="empty"><div class="art">${icon('lock', 'lg')}</div><h3>This link is not available</h3><p>It may have been switched off or replaced. Ask the organising team for a new link.</p></div></div></main>`);
  }
}