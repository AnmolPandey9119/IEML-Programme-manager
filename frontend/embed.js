/*!
 * IEML EventCore: live agenda widget.
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
  if (!key) { console.error('[IEML EventCore] data-event is missing'); return; }
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
    '.w{--bg:#fff;--ink:#0d1636;--mut:#667090;--line:#e3e7f1;--soft:#f5f7fc;--ac:' + accent + ';--ax:var(--ac);--gold:#d9a52b;font-family:inherit;font-size:15px;line-height:1.55;color:var(--ink);background:var(--bg);border-radius:28px;padding:24px 24px 14px;border:1px solid var(--line);box-shadow:0 1px 2px rgba(13,22,54,.04),0 24px 50px -30px rgba(13,22,54,.35);-webkit-font-smoothing:antialiased}' +
    '.w.dark{--ax:color-mix(in srgb,var(--ac) 38%,#fff);--bg:#0e1530;--ink:#ecf0ff;--mut:#9fadd0;--line:#232d58;--soft:#141d3f;box-shadow:0 24px 50px -30px #000}' +
    '@media(prefers-color-scheme:dark){.w.auto{--ax:color-mix(in srgb,var(--ac) 38%,#fff);--bg:#0e1530;--ink:#ecf0ff;--mut:#9fadd0;--line:#232d58;--soft:#141d3f;box-shadow:0 24px 50px -30px #000}}' +
    '*{box-sizing:border-box}h2,h3,p,ul{margin:0}button{font:inherit;color:inherit;cursor:pointer}' +
    '.hd{padding:4px 0 6px}.hd h2{font-family:Fraunces,"Iowan Old Style",Georgia,serif;font-size:32px;line-height:1.1;font-weight:600;letter-spacing:-.03em;text-wrap:balance}' +
    '.hd h2::after{content:"";display:block;width:48px;height:4px;border-radius:4px;margin-top:14px;background:linear-gradient(90deg,var(--gold),var(--ac))}' +
    '.hd p{color:var(--mut);margin-top:12px;font-size:16px;font-style:italic;font-family:Fraunces,Georgia,serif}' +
    '.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:20px 0 14px}' +
    '.tab{border:1px solid var(--line);background:transparent;border-radius:99px;padding:9px 20px;text-align:left;transition:border-color .15s,background .15s,box-shadow .2s,transform .15s}' +
    '.tab:hover{border-color:var(--ac);transform:translateY(-1px)}' +
    '.tab b{display:block;font-size:14.5px;letter-spacing:-.005em}.tab small{color:var(--mut);font-size:12.5px}' +
    '.tab[aria-selected=true]{background:linear-gradient(135deg,var(--ac),color-mix(in srgb,var(--ac) 68%,#000));border-color:transparent;color:#fff;box-shadow:inset 0 -3px 0 var(--gold),0 14px 24px -14px var(--ac)}' +
    '.tab[aria-selected=true] small{color:#ffffffcc}' +
    '.tab:focus-visible,select:focus-visible{outline:2px solid var(--ac);outline-offset:2px}' +
    'select{margin-left:auto;appearance:none;-webkit-appearance:none;border:1px solid var(--line);background-color:var(--bg);color:var(--ink);border-radius:99px;padding:10px 38px 10px 18px;font:inherit;font-size:14px;cursor:pointer;transition:border-color .15s;background-image:url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%2716%27 height=%2716%27 viewBox=%270 0 24 24%27 fill=%27none%27 stroke=%27%238a93a6%27 stroke-width=%272.2%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27%3E%3Cpath d=%27m6 9 6 6 6-6%27/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 14px center}' +
    'select:hover{border-color:var(--ac)}' +
    '.s{display:grid;grid-template-columns:112px 1fr;gap:6px 30px;padding:0 0 16px;position:relative}' +
    '.s::before{content:"";position:absolute;left:127px;top:0;bottom:0;width:2px;background:var(--line)}' +
    '.s:first-of-type::before{top:30px}' +
    '.s:last-of-type::before{bottom:auto;height:30px}' +
    '.s::after{content:"";position:absolute;left:120px;top:22px;width:16px;height:16px;border-radius:50%;background:var(--bg);border:4px solid var(--ac);box-shadow:0 0 0 5px color-mix(in srgb,var(--ac) 14%,transparent)}' +
    '.t{padding-top:16px;text-align:right}' +
    '.t b{display:block;font-family:Fraunces,Georgia,serif;font-size:18px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums}.t span{color:var(--mut);font-size:12.5px;font-variant-numeric:tabular-nums}' +
    '.s>div:last-child{background:var(--soft);border:1px solid var(--line);border-radius:22px;padding:18px 22px 20px;transition:border-color .2s,box-shadow .25s,transform .2s}' +
    '.s:hover>div:last-child{border-color:color-mix(in srgb,var(--ac) 45%,var(--line));box-shadow:0 18px 34px -24px color-mix(in srgb,var(--ac) 70%,#000)}' +
    '.ty{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:3px 11px;border-radius:99px;background:color-mix(in srgb,var(--ac) 12%,transparent);color:var(--ax);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ac) 30%,transparent)}' +
    '.hl{color:var(--mut);font-size:13px;margin-left:10px}' +
    '.ti{font-family:Fraunces,Georgia,serif;font-size:21px;line-height:1.25;font-weight:600;letter-spacing:-.02em;margin:10px 0 3px;text-wrap:balance}' +
    '.tg{all:unset;cursor:pointer;display:block;transition:color .15s}.tg:hover{color:var(--ax)}.tg:focus-visible{outline:2px solid var(--ac);outline-offset:3px;border-radius:6px}' +
    '.sp{display:flex;gap:14px 28px;flex-wrap:wrap;margin-top:14px}.p{display:flex;gap:12px;align-items:center;min-width:0}' +
    '.av{width:42px;height:42px;border-radius:50%;background:var(--bg);display:grid;place-items:center;font-weight:700;font-size:13.5px;color:var(--ax);flex:none;overflow:hidden;box-shadow:0 0 0 2px var(--soft),0 0 0 3px color-mix(in srgb,var(--ac) 38%,transparent)}' +
    '.av img{width:100%;height:100%;object-fit:cover;object-position:center 20%}' +
    '.p div{line-height:1.3}.p b{font-size:14.5px;letter-spacing:-.005em}.p small{display:block;color:var(--mut);font-size:12.5px;margin-top:1px}' +
    '.mod{display:inline-block;font-size:10.5px;color:var(--gold);font-weight:700;letter-spacing:.09em;text-transform:uppercase}' +
    '.exp{display:inline-flex;align-items:center;gap:8px;color:var(--ax);font-size:13px;font-weight:600;margin-top:14px;padding:6px 15px;border-radius:99px;border:1px solid color-mix(in srgb,var(--ac) 34%,transparent);background:var(--bg);transition:background .15s,border-color .15s}' +
    '.exp:hover{background:color-mix(in srgb,var(--ac) 9%,var(--bg));border-color:var(--ac);color:var(--ax)}' +
    '.exp::after{content:"";width:6px;height:6px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg) translateY(-2px);transition:transform .2s}' +
    '.exp[aria-expanded=true]::after{transform:rotate(-135deg) translate(-1px,-1px)}' +
    '.more{margin-top:14px;padding:16px 18px;background:var(--bg);border-radius:16px;border:1px solid var(--line);border-left:3px solid var(--ac)}.more p{white-space:pre-line}.more ul{padding-left:20px;margin-top:10px}.more li{margin:4px 0}.more li::marker{color:var(--ac)}' +
    '.bios{margin-top:14px;display:grid;gap:12px;padding-top:12px;border-top:1px dashed var(--line)}.bios p{font-size:13.5px;color:var(--mut)}.bios b{color:var(--ink)}' +
    '.empty{padding:48px 16px;margin-top:10px;text-align:center;color:var(--mut);border:1px dashed var(--line);border-radius:22px;background:var(--soft)}' +
    '@media(prefers-reduced-motion:reduce){*{transition:none!important}}' +
    '@media(max-width:560px){.w{padding:16px 14px 8px;border-radius:22px}.hd h2{font-size:26px}select{margin-left:0}.s{grid-template-columns:1fr;gap:0;padding-left:26px}.s::before{left:7px}.s::after{left:0;top:16px;width:14px;height:14px;border-width:3px}.t{display:flex;gap:8px;align-items:baseline;text-align:left;padding:10px 0 8px 22px}.s>div:last-child{padding:16px 16px 18px}}';

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