/*!
 * IEML Event Core: live agenda widget.
 * Usage (one line, anywhere in a page):
 *   <script src="https://YOUR-HOST/embed.js" data-event="PUBLIC_KEY" async></script>
 * Options (all optional): data-accent="#1d3f91"  data-theme="light|dark|auto"  data-day="DAY_ID"  data-hall="HALL_ID"
 *   data-photos="false"  data-header="false"  data-target="#element-id"  data-interval="15"
 * The widget draws inside a Shadow DOM, so the host website's CSS cannot break it and it cannot break the website.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  if (!script || script.getAttribute('data-pm-init')) return;
  script.setAttribute('data-pm-init', '1');
  var cfg = script.dataset, origin = new URL(script.src, location.href).origin, key = cfg.event;
  if (!key) { console.error('[IEML Event Core] data-event is missing'); return; }
  var interval = Math.max(5, parseInt(cfg.interval, 10) || 15) * 1000;
  var host = document.createElement('div');
  host.className = 'pm-agenda-host';
  var target = cfg.target && document.querySelector(cfg.target);
  if (target) target.appendChild(host); else script.parentNode.insertBefore(host, script.nextSibling);
  var root = host.attachShadow({ mode: 'open' });

  var state = { data: null, raw: '', day: cfg.day ? +cfg.day : null, hall: cfg.hall || '', open: {}, error: '' };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var safeUrl = function (u) { return /^https?:\/\//i.test(u || '') ? u : ''; };
  var accent = /^#[0-9a-f]{3,8}$/i.test(cfg.accent || '') ? cfg.accent : '#1d3f91';
  var theme = cfg.theme || 'auto';

  var CSS = ':host{display:block}' +
    '.w{--bg:#fff;--ink:#16233f;--mut:#667085;--line:#e4e7ec;--soft:#f5f7f9;--ac:' + accent + ';font-family:inherit;font-size:15px;line-height:1.55;color:var(--ink);background:var(--bg);border-radius:14px;padding:6px}' +
    '.w.dark{--bg:#0f1830;--ink:#eaf0fb;--mut:#9fb0cc;--line:#26335a;--soft:#17233f}' +
    '@media(prefers-color-scheme:dark){.w.auto{--bg:#0f1830;--ink:#eaf0fb;--mut:#9fb0cc;--line:#26335a;--soft:#17233f}}' +
    '*{box-sizing:border-box}h2,h3,p,ul{margin:0}button{font:inherit;color:inherit;cursor:pointer}' +
    '.hd{padding:10px 8px 4px}.hd h2{font-size:22px;line-height:1.2}.hd p{color:var(--mut);margin-top:4px}' +
    '.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 8px}' +
    '.tab{border:1px solid var(--line);background:transparent;border-radius:10px;padding:7px 14px;text-align:left}' +
    '.tab b{display:block;font-size:14px}.tab small{color:var(--mut);font-size:12px}' +
    '.tab[aria-selected=true]{background:var(--ac);border-color:var(--ac);color:#fff}.tab[aria-selected=true] small{color:#ffffffcc}' +
    'select{margin-left:auto;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:8px;padding:7px 10px;font:inherit}' +
    '.s{display:grid;grid-template-columns:110px 1fr;gap:6px 18px;padding:16px 10px;border-top:1px solid var(--line)}' +
    '.t b{display:block;font-size:16px;font-variant-numeric:tabular-nums}.t span{color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums}' +
    '.ty{display:inline-block;font-size:12px;font-weight:600;padding:1px 9px;border-radius:6px;background:color-mix(in srgb,var(--ac) 14%,transparent);color:var(--ac)}' +
    '.hl{color:var(--mut);font-size:13px;margin-left:8px}' +
    '.ti{font-size:18px;line-height:1.3;margin:6px 0 2px}' +
    '.tg{all:unset;cursor:pointer;display:block}.tg:focus-visible{outline:2px solid var(--ac);outline-offset:3px;border-radius:6px}' +
    '.sp{display:flex;gap:14px 22px;flex-wrap:wrap;margin-top:10px}.p{display:flex;gap:10px;align-items:center;min-width:0}' +
    '.av{width:38px;height:38px;border-radius:50%;background:var(--soft);display:grid;place-items:center;font-weight:600;font-size:13px;color:var(--ac);flex:none;overflow:hidden}' +
    '.av img{width:100%;height:100%;object-fit:cover;object-position:center 20%}' +
    '.p div{line-height:1.3}.p b{font-size:14px}.p small{display:block;color:var(--mut);font-size:12.5px}' +
    '.mod{font-size:11.5px;color:var(--ac);font-weight:600}' +
    '.more{margin-top:12px;padding:12px 14px;background:var(--soft);border-radius:10px}.more p{white-space:pre-line}.more ul{padding-left:18px;margin-top:8px}.more li{margin:3px 0}' +
    '.bios{margin-top:12px;display:grid;gap:10px}.bios p{font-size:13.5px;color:var(--mut)}.bios b{color:var(--ink)}' +
    '.exp{color:var(--ac);font-size:13px;margin-top:8px;display:inline-block}' +
    '.empty{padding:36px 10px;text-align:center;color:var(--mut)}' +
    '@media(max-width:560px){.s{grid-template-columns:1fr}}';

  function initials(n) { var p = String(n).replace(/\b(dr|mr|mrs|ms|prof)\.?\s/gi, '').trim().split(/\s+/); return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase(); }

  function render() {
    var d = state.data, h = '';
    if (state.error && !d) { root.innerHTML = '<style>' + CSS + '</style><div class="w ' + theme + '"><div class="empty">' + esc(state.error) + '</div></div>'; return; }
    if (!d) { root.innerHTML = '<style>' + CSS + '</style><div class="w ' + theme + '"><div class="empty">Loading programme…</div></div>'; return; }
    var days = d.days.filter(function (x) { return !cfg.day || x.id === +cfg.day; });
    if (!days.some(function (x) { return x.id === state.day; })) state.day = (days.find(function (x) { return x.sessions.length; }) || days[0] || {}).id;
    var day = days.find(function (x) { return x.id === state.day; });
    if (cfg.header !== 'false') h += '<div class="hd"><h2>' + esc(d.event.name + ' ' + d.event.edition) + '</h2>' + (d.event.theme_line ? '<p>' + esc(d.event.theme_line) + '</p>' : '') + '</div>';
    h += '<div class="bar" role="tablist">';
    if (days.length > 1) days.forEach(function (x) {
      var lab = x.label.split(' — ');
      h += '<button class="tab" role="tab" data-day="' + x.id + '" aria-selected="' + (x.id === state.day) + '"><b>' + esc(lab[0]) + '</b><small>' + esc(lab[1] || x.date) + '</small></button>';
    });
    var halls = d.halls.filter(function (hh) { return day && day.sessions.some(function (s) { return s.hall && !s.is_merged && s.hall === hh.name; }); });
    if (!cfg.hall && halls.length > 1) {
      h += '<select aria-label="Filter by hall"><option value="">All halls</option>' + halls.map(function (hh) { return '<option value="' + esc(hh.name) + '"' + (state.hall === hh.name ? ' selected' : '') + '>' + esc(hh.name) + '</option>'; }).join('') + '</select>';
    }
    h += '</div>';
    var rows = day ? day.sessions.filter(function (s) { return !state.hall || s.is_merged || s.hall === state.hall; }) : [];
    if (!rows.length) h += '<div class="empty">The programme for this day will be announced soon.</div>';
    rows.forEach(function (s) {
      var isOpen = !!state.open[s.id], mods = s.speakers.filter(function (p) { return p.role === 'moderator'; });
      var hasMore = s.writeup || s.subtopics.length || s.speakers.some(function (p) { return p.bio; });
      h += '<article class="s"><div class="t"><b>' + esc(s.start_label) + '</b><span>to ' + esc(s.end_label) + '</span></div><div>' +
        '<span class="ty">' + esc(s.type) + '</span>' + (s.hall ? '<span class="hl">' + esc(s.hall) + '</span>' : '') +
        '<h3 class="ti">' + (hasMore ? '<button class="tg" data-s="' + s.id + '" aria-expanded="' + isOpen + '">' + esc(s.title) + '</button>' : esc(s.title)) + '</h3>';
      if (s.speakers.length) {
        h += '<div class="sp">' + s.speakers.map(function (p) {
          var img = cfg.photos !== 'false' && p.photo_url ? '<img src="' + esc(p.photo_url) + '" alt="" loading="lazy">' : esc(initials(p.name));
          var ln = safeUrl(p.linkedin_url);
          return '<div class="p"><span class="av">' + (cfg.photos === 'false' ? '' : img) + '</span><div>' + (p.role === 'moderator' ? '<span class="mod">Moderator</span>' : '') +
            '<b>' + (ln ? '<a href="' + esc(ln) + '" target="_blank" rel="noopener" style="color:inherit">' + esc(p.name) + '</a>' : esc(p.name)) + '</b><small>' + esc([p.designation, p.organisation].filter(Boolean).join(', ')) + '</small></div></div>';
        }).join('') + '</div>';
      }
      if (hasMore) {
        h += '<button class="tg exp" data-s="' + s.id + '" aria-expanded="' + isOpen + '">' + (isOpen ? 'Show less' : 'Details') + '</button>';
        if (isOpen) {
          h += '<div class="more">' + (s.writeup ? '<p>' + esc(s.writeup) + '</p>' : '') +
            (s.subtopics.length ? '<ul>' + s.subtopics.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' : '') +
            (s.speakers.some(function (p) { return p.bio; }) ? '<div class="bios">' + s.speakers.filter(function (p) { return p.bio; }).map(function (p) { return '<p><b>' + esc(p.name) + '.</b> ' + esc(p.bio) + '</p>'; }).join('') + '</div>' : '') + '</div>';
        }
      }
      h += '</div></article>';
    });
    root.innerHTML = '<style>' + CSS + '</style><div class="w ' + theme + '">' + h + '</div>';
  }

  root.addEventListener('click', function (e) {
    var t = e.target.closest('[data-day]'); if (t) { state.day = +t.dataset.day; return render(); }
    var s = e.target.closest('[data-s]'); if (s) { state.open[s.dataset.s] = !state.open[s.dataset.s]; render(); var again = root.querySelector('[data-s="' + s.dataset.s + '"]'); if (again) again.focus(); }
  });
  root.addEventListener('change', function (e) { if (e.target.tagName === 'SELECT') { state.hall = e.target.value; render(); } });

  function load() {
    var url = origin + '/api/public/events/' + encodeURIComponent(key) + '/agenda' + (cfg.day || cfg.hall ? '?' + [cfg.day ? 'day=' + encodeURIComponent(cfg.day) : '', cfg.hall ? 'hall=' + encodeURIComponent(cfg.hall) : ''].filter(Boolean).join('&') : '');
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (r.status === 404) { state.error = 'The programme is not available yet.'; state.data = null; return render(); }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text().then(function (txt) { if (txt === state.raw) return; state.raw = txt; state.data = JSON.parse(txt); state.error = ''; render(); });
    }).catch(function () { if (!state.data) { state.error = 'The programme could not be loaded. Please try again shortly.'; render(); } });
  }
  render(); load();
  setInterval(function () { if (!document.hidden) load(); }, interval);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) load(); });
})();