/* Core utilities: state, API client, safe templating, icons, overlays, toasts, event delegation. */

export const S = { token: safeGet('token'), me: null, event: null, eventId: null };

function safeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function safeSet(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } }
export const store = { get: safeGet, set: safeSet };

/* ---------------------------------------------------------------- safe templating */
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s ?? ''));
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
function part(v) {
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(part).join('');
  if (v === null || v === undefined || v === false) return '';
  return esc(v);
}
/** Tagged template: every interpolated value is HTML-escaped unless it is itself html`` / raw(). */
export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
  return new Raw(out);
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export function mount(el, content) { el.innerHTML = content instanceof Raw ? content.s : String(content); }

/* ---------------------------------------------------------------- icons (stroke set) */
const P = {
  plus: '<path d="M5 12h14M12 5v14"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  down: '<path d="m6 9 6 6 6-6"/>', left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
  up2: '<path d="M12 19V5M5 12l7-7 7 7"/>', down2: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M22 20c0-3-2-5-5-5.7"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4"/>',
  agenda: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  sliders: '<path d="M4 6h8M16 6h4M4 12h2M10 12h10M4 18h12M20 18h0"/><circle cx="14" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  warning: '<path d="M12 3 2 20h20Z"/><path d="M12 10v5M12 18h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  camera: '<rect x="3" y="6" width="18" height="14" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 6l1.5-2.5h5L16 6"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  home: '<path d="M3 11 12 3l9 8M5 10v10h14V10"/>',
  pin: '<path d="M12 21s7-6 7-12a7 7 0 0 0-14 0c0 6 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/>',
  clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h4"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M3 21v-5h5"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  more: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 21a2 2 0 0 0 4 0"/>',
  copy2: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6Z"/>',
};
export function icon(name, cls = '') {
  return raw(`<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || ''}</svg>`);
}

/* ---------------------------------------------------------------- formatting helpers */
export function initials(name) {
  const parts = String(name || '?').replace(/\b(dr|mr|mrs|ms|prof|shri|smt)\.?\s/gi, '').trim().split(/\s+/);
  return ((parts[0]?.[0] || '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}
const AV = [['#dff1ee', '#0d5f59'], ['#e5ecfb', '#27479f'], ['#fbeadc', '#9a4d12'], ['#f3e6f6', '#7a3a8c'], ['#e8f1dc', '#4a6b1d'], ['#fbe5e8', '#9b2f46']];
export function avatarStyle(name) {
  let h = 0; for (const c of String(name || '')) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const [bg, fg] = AV[h % AV.length];
  return `background:${bg};color:${fg}`;
}
export function avatar(name, photoUrl, size = '') {
  return photoUrl
    ? html`<span class="av ${size}"><img src="${photoUrl}" alt="" loading="lazy"></span>`
    : html`<span class="av ${size}" style="${avatarStyle(name)}">${initials(name)}</span>`;
}
/** "14:05:00" -> "2:05 PM" */
export function fmtTime(t) {
  if (!t) return '';
  const [h, m] = String(t).split(':').map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}
export function fmtDur(mins) {
  if (!(mins > 0)) return '';
  const h = Math.floor(mins / 60), m = mins % 60;
  return h && m ? `${h} h ${m} min` : h ? `${h} h` : `${m} min`;
}
export function fmtDate(d) {
  if (!d) return '';
  const [y, m, dd] = String(d).split('-').map(Number);
  return new Date(y, m - 1, dd).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}
export const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + 's'}`;
export const STATUS_DOT = { Invited: 'invited', Confirmed: 'confirmed', Tentative: 'tentative', Declined: 'declined' };
export const statusPill = (st) => html`<span class="pill ${STATUS_DOT[st] || ''}"><span class="dot"></span>${st}</span>`;

/* ---------------------------------------------------------------- API */
export async function api(path, method = 'GET', body, opts = {}) {
  const headers = {};
  if (S.token) headers.Authorization = 'Bearer ' + S.token;
  let payload;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const res = await fetch('/api' + path, { method, headers, body: payload });
  if (opts.blob && res.ok) return { blob: await res.blob(), name: filenameFrom(res) };
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && S.token && !path.startsWith('/auth/login')) { logout(); }
    const d = data.detail;
    const err = new Error(Array.isArray(d) ? d.map((e) => `${String(e.loc.slice(-1)[0]).replace(/_/g, ' ')}: ${e.msg.replace(/^Value error, /, '')}`).join('; ') : d || 'Something went wrong. Please try again.');
    err.status = res.status;
    throw err;
  }
  return data;
}
function filenameFrom(res) {
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(res.headers.get('content-disposition') || '');
  return m ? decodeURIComponent(m[1]) : 'download';
}
export function saveBlob({ blob, name }) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

export function setToken(t) { S.token = t; safeSet('token', t); }
export function logout() { S.token = null; S.me = null; S.event = null; safeSet('token', null); location.hash = '#/login'; }

/* ---------------------------------------------------------------- toasts */
export function toast(msg, kind = 'ok') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind; el.setAttribute('role', kind === 'err' ? 'alert' : 'status');
  el.innerHTML = (kind === 'ok' ? icon('check', 'sm').s : kind === 'err' ? icon('warning', 'sm').s : '') + `<span>${esc(msg)}</span>`;
  $('#toasts').append(el);
  setTimeout(() => el.remove(), kind === 'err' ? 6000 : 3500);
}

/** Wraps an action so failures show an error toast instead of silently breaking. */
export const guard = (fn) => async (...a) => {
  try { return await fn(...a); } catch (e) { toast(e.message, 'err'); }
};

/* ---------------------------------------------------------------- overlays */
const layer = () => $('#layer');
let stack = [];

/** Opens a drawer or dialog. `body`/`footer` are html``. Returns { el, close, setBody }. */
export function openPanel({ title, subtitle = '', body, footer = null, kind = 'dialog', wide = false, onClose }) {
  const scrim = document.createElement('div');
  scrim.className = 'scrim' + (kind === 'dialog' ? ' center' : '');
  const closeBtn = html`<button class="btn quiet icon" data-close aria-label="Close">${icon('x')}</button>`;
  scrim.innerHTML = `<div class="${kind === 'drawer' ? 'drawer' : 'dialog' + (wide ? ' wide' : '')}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <div class="ov-head"><div class="t"><h2>${esc(title)}</h2>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div>${closeBtn.s}</div>
    <div class="ov-body" data-body>${part(body)}</div>${footer ? `<div class="ov-foot" data-foot>${part(footer)}</div>` : ''}</div>`;
  const prevFocus = document.activeElement;
  const panel = { el: scrim, closed: false };
  panel.close = (result) => {
    if (panel.closed) return; panel.closed = true;
    scrim.remove(); stack = stack.filter((p) => p !== panel); prevFocus?.focus?.();
    onClose?.(result);
  };
  panel.setBody = (b) => { $('[data-body]', scrim).innerHTML = part(b); };
  panel.setFooter = (f) => { const el = $('[data-foot]', scrim); if (el) el.innerHTML = part(f); };
  scrim.addEventListener('mousedown', (e) => { if (e.target === scrim) panel.close(); });
  scrim.addEventListener('click', (e) => { if (e.target.closest('[data-close]')) panel.close(); });
  layer().append(scrim); stack.push(panel);
  const first = $('[data-autofocus], input:not([type=hidden]):not([disabled]), textarea', scrim);
  first?.focus();
  return panel;
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && stack.length) stack[stack.length - 1].close(); });
export const topPanel = () => stack[stack.length - 1];

export function confirmDialog({ title, message, confirmLabel = 'Confirm', danger = false }) {
  return new Promise((resolve) => {
    let answer = false;
    const p = openPanel({
      title, body: html`<p class="soft">${message}</p>`,
      footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button>
        <button class="btn ${danger ? 'solid-danger' : 'primary'}" data-act="__yes" data-autofocus>${confirmLabel}</button>`,
      onClose: () => resolve(answer),
    });
    p.el.querySelector('[data-act="__yes"]').addEventListener('click', () => { answer = true; p.close(); });
  });
}
export function promptDialog({ title, label, value = '', confirmLabel = 'Save', placeholder = '' }) {
  return new Promise((resolve) => {
    let answer = null;
    const p = openPanel({
      title, body: html`<label class="field"><span>${label}</span><input id="__prompt" value="${value}" placeholder="${placeholder}" data-autofocus></label>`,
      footer: html`<span class="sp"></span><button class="btn" data-close>Cancel</button><button class="btn primary" id="__ok">${confirmLabel}</button>`,
      onClose: () => resolve(answer),
    });
    const input = $('#__prompt', p.el);
    const done = () => { const v = input.value.trim(); if (v) { answer = v; p.close(); } };
    $('#__ok', p.el).addEventListener('click', done);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') done(); });
    input.select();
  });
}

/* ---------------------------------------------------------------- event delegation */
const ACTS = {};
/** Register click handlers: <button data-act="name" data-id="3">. Handler receives (element, event). */
export function acts(map) { Object.assign(ACTS, map); }
const CHANGES = {};
export function changes(map) { Object.assign(CHANGES, map); }
const INPUTS = {};
export function inputs(map) { Object.assign(INPUTS, map); }

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el || el.disabled) return;
  const fn = ACTS[el.dataset.act];
  if (fn) { if (el.tagName === 'A' && !el.dataset.native) e.preventDefault(); Promise.resolve(guard(fn)(el, e)); }
});
document.addEventListener('change', (e) => {
  const el = e.target.closest('[data-change]');
  const fn = el && CHANGES[el.dataset.change];
  if (fn) Promise.resolve(guard(fn)(el, e));
});
document.addEventListener('input', (e) => {
  const el = e.target.closest('[data-input]');
  const fn = el && INPUTS[el.dataset.input];
  if (fn) fn(el, e);
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' || e.isComposing) return;
  const el = e.target.closest('[data-enter]');
  if (el && el.tagName !== 'TEXTAREA') { e.preventDefault(); ACTS[el.dataset.enter]?.(el, e); }
});

/* form helpers */
export const val = (id, root = document) => (root.querySelector('#' + id)?.value ?? '').trim();
export const raw_val = (id, root = document) => root.querySelector('#' + id)?.value ?? '';
export const field = (label, control, { hint = '', optional = false } = {}) =>
  html`<label class="field"><span>${label}${optional ? html` <em>(optional)</em>` : ''}</span>${control}${hint ? html`<small class="hint">${hint}</small>` : ''}</label>`;

export async function copyText(text, msg = 'Copied to clipboard') {
  try { await navigator.clipboard.writeText(text); toast(msg); }
  catch {
    const ta = document.createElement('textarea'); ta.value = text; document.body.append(ta); ta.select();
    try { document.execCommand('copy'); toast(msg); } catch { toast('Copy failed. Select the text and copy it manually.', 'err'); }
    ta.remove();
  }
}

/* ---------------------------------------------------------------- session types */
export const TYPES = {
  'Keynote': ['#6d4fc7', '#ece7fa'], 'Plenary': ['#2f5bd0', '#e7edfb'], 'Inaugural': ['#b57a00', '#fdf0cf'],
  'Roundtable': ['#0c7c92', '#dff3f7'], 'Panel Discussion': ['#12776f', '#e0f2f0'], 'Fireside Chat': ['#b83a64', '#fbe4ec'],
  'Talk / Address': ['#3d6aa3', '#e6eef8'], 'Leadership Address': ['#8a3fa0', '#f3e5f8'], 'Workshop': ['#2f8a3d', '#e4f3e6'],
  'Lightning Talk': ['#c4571a', '#fbe9dc'], 'Networking': ['#a8478a', '#f7e4f1'], 'Break': ['#6b778c', '#eceff2'],
  'Custom': ['#46566e', '#e6eaf0'],
};
export const typeVars = (t) => { const [c, b] = TYPES[t] || TYPES.Custom; return `--tc:${c};--tb:${b}`; };

/* ---------------------------------------------------------------- 12-hour time input helpers */
/** "9:30 AM", "930pm", "14:05", "2.30 pm" -> "HH:MM" (24h) or null. A bare 1 to 6 is read as PM, 7 to 11 as AM. */
export function parseTime(str) {
  const m = /^\s*(\d{1,2})(?:[:.]?(\d{2}))?\s*([ap])?\.?(?:m\.?)?\s*$/i.exec(String(str || ''));
  if (!m) return null;
  let h = +m[1]; const min = m[2] ? +m[2] : 0; const mer = m[3]?.toLowerCase();
  if (min > 59) return null;
  if (mer) { if (h < 1 || h > 12) return null; h = (h % 12) + (mer === 'p' ? 12 : 0); }
  else if (h > 23) return null;
  else if (h >= 1 && h <= 6 && !m[1].startsWith('0')) h += 12; // "2:30" almost always means 2:30 PM at a conference
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
}
export const to12 = (hhmm) => (hhmm ? fmtTime(hhmm + ':00') : '');
export const toMin = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };
export function timeOptions() {
  let out = '';
  for (let m = 6 * 60; m <= 23 * 60 + 45; m += 15) out += `<option value="${to12(`${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`)}">`;
  return raw(out);
}
