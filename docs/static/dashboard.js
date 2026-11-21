/* ポチフル ダッシュボード。
   前半は DOM に触らない純粋な関数（混ぜ方・3日切り・分散）。test_dashboard.py が osascript(JXA) で検証する。
   後半が画面の組み立て。仕様は feed-spec.md。 */
var PochiDash = (function () {
  'use strict';
  var KEEP_DAYS = 3;
  var MAX_RUN = 2; // 同じ source は3枚以上連続させない
  // 表示の上限（新しい順に何件まで）。セール・入荷は新しい数件で足り、以降は似た顔ぶれが続くため（オーナー決定 2026-11-21）。
  // feed.json 自体は各20件のまま。ここに無い source は上限なし。
  var SOURCE_CAP = { kaden: 6, apple: 6 };

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  // 今日（JST）を YYYY-MM-DD で返す
  function jstToday(nowMs) {
    var d = new Date(nowMs + 9 * 3600 * 1000);
    return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
  }
  function dayNum(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    return m ? Math.round(Date.UTC(+m[1], +m[2] - 1, +m[3]) / 86400000) : NaN;
  }
  function isHttp(u) { return typeof u === 'string' && /^https?:\/\//i.test(u); }
  function validItem(it) {
    return !!it && typeof it.id === 'string' && it.id && typeof it.title === 'string' && it.title &&
      isHttp(it.url) && !isNaN(dayNum(it.date)) && typeof it.source === 'string' && it.source;
  }

  // feeds: feed.json を読んだオブジェクトの配列（失敗したものは入れない）。
  // 日付の新しい順（同じ日は generated の新しい feed、次に元の順）→ 3日より古いものを捨てる（未来日付は残す）→ id で重複除去。
  // → SOURCE_CAP の source は新しいほうから上限件数まで。
  function mix(feeds, today) {
    var floor = dayNum(today) - KEEP_DAYS, all = [], seq = 0;
    (feeds || []).forEach(function (f) {
      if (!f || !Array.isArray(f.items)) return;
      var gen = Date.parse(f.generated) || 0;
      f.items.forEach(function (it) {
        if (validItem(it)) all.push({ it: it, d: dayNum(it.date), g: gen, n: seq++ });
      });
    });
    all.sort(function (a, b) { return (b.d - a.d) || (b.g - a.g) || (a.n - b.n); });
    var seen = {}, count = {}, out = [];
    all.forEach(function (x) {
      if (x.d < floor || seen[x.it.id]) return;
      seen[x.it.id] = true;
      var s = x.it.source, cap = SOURCE_CAP[s];
      if (cap !== undefined && (count[s] || 0) >= cap) return;
      count[s] = (count[s] || 0) + 1;
      out.push(x.it);
    });
    return out;
  }

  // 同じ source が3枚以上連続しないよう、3枚目になるものを後ろの別 source の item と入れ替える。
  function spread(items) {
    var a = items.slice();
    for (var i = MAX_RUN; i < a.length; i++) {
      if (a[i].source === a[i - 1].source && a[i].source === a[i - 2].source) {
        for (var j = i + 1; j < a.length; j++) {
          if (a[j].source !== a[i].source) {
            var t = a[i]; a[i] = a[j]; a[j] = t;
            break;
          }
        }
      }
    }
    return a;
  }

  // off: チップをオフにした source のキー配列
  function visible(items, off) {
    var o = {};
    (off || []).forEach(function (k) { o[k] = true; });
    return spread(items.filter(function (it) { return !o[it.source]; }));
  }

  return { jstToday: jstToday, mix: mix, spread: spread, visible: visible, isHttp: isHttp, dayNum: dayNum };
})();

/* ---------------- 画面 ---------------- */
if (typeof document !== 'undefined') (function () {
  'use strict';
  var VIEW_KEY = 'pochi.view', OFF_KEY = 'pochi.chipsOff';
  function load(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* 使えなくても動く */ } }

  var tabs = [].slice.call(document.querySelectorAll('.pf-tab'));
  var panels = { links: document.getElementById('view-links'), dash: document.getElementById('view-dash') };
  var tabBar = document.getElementById('pf-tabs');
  var dash = document.getElementById('view-dash');
  if (!tabs.length || !panels.links || !dash) return;
  tabBar.hidden = false;

  var status = document.getElementById('dash-status');
  var list = document.getElementById('dash-list');
  var chips = [].slice.call(document.querySelectorAll('.pf-chip'));
  var feedUrls = [];
  try { feedUrls = JSON.parse(dash.getAttribute('data-feeds')) || []; } catch (e) { feedUrls = []; }
  var sites = {};
  chips.forEach(function (c) {
    sites[c.getAttribute('data-source')] = { name: c.getAttribute('data-name'), color: c.getAttribute('data-color'), icon: c.getAttribute('data-icon') };
  });

  var off = [];
  try { off = JSON.parse(load(OFF_KEY) || '[]'); if (!Array.isArray(off)) off = []; } catch (e) { off = []; }
  function syncChips() {
    chips.forEach(function (c) { c.setAttribute('aria-pressed', off.indexOf(c.getAttribute('data-source')) < 0 ? 'true' : 'false'); });
  }
  syncChips();

  var mixed = null, loading = false;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmtDate(s) {
    var m = /^\d{4}-(\d{2})-(\d{2})$/.exec(s);
    return m ? (+m[1]) + '/' + (+m[2]) : s;
  }

  function thumb(it, site) {
    var box = el('span', 'dc-thumb');
    var src = PochiDash.isHttp(it.image) ? it.image : (PochiDash.isHttp(it.icon) ? it.icon : null);
    var img = document.createElement('img');
    img.alt = '';
    img.loading = 'lazy';
    img.decoding = 'async';
    if (src) {
      img.src = src;
      if (src === it.icon && src !== it.image) box.className += ' is-icon';
    } else {
      box.className += ' is-band';
      box.style.setProperty('--c', (site && site.color) || '');
      if (site && site.icon) img.src = site.icon; else img = null;
    }
    if (img) box.appendChild(img);
    var a = document.createElement('a');
    a.className = 'dc-imglink';
    if (PochiDash.isHttp(it.image) && PochiDash.isHttp(it.image_link)) {
      a.href = it.image_link;
      a.target = '_blank';
      a.rel = 'nofollow sponsored noopener';
      a.setAttribute('aria-label', it.title + '（商品ページを開く）');
    } else {
      a.href = it.url;
      a.tabIndex = -1;
      a.setAttribute('aria-hidden', 'true'); // 題名リンクと同じ行き先なので読み上げは重ねない
    }
    a.appendChild(box);
    return a;
  }

  function card(it) {
    var site = sites[it.source];
    var li = el('li', 'dc');
    li.style.setProperty('--c', (site && site.color) || '');
    li.appendChild(thumb(it, site));
    var body = el('div', 'dc-body');
    var meta = el('p', 'dc-meta');
    meta.appendChild(el('span', 'dc-badge', (site && site.name) || it.source_name || it.source));
    var t = el('time', 'dc-date', fmtDate(it.date));
    t.setAttribute('datetime', it.date);
    meta.appendChild(t);
    body.appendChild(meta);
    var h = el('h3', 'dc-title');
    var a = el('a', null, it.title);
    a.href = it.url;
    h.appendChild(a);
    body.appendChild(h);
    if (it.note) body.appendChild(el('p', 'dc-note', it.note));
    li.appendChild(body);
    return li;
  }

  function render() {
    list.textContent = '';
    if (!mixed) return;
    var items = PochiDash.visible(mixed, off);
    if (!items.length) {
      status.hidden = false;
      status.textContent = '';
      status.appendChild(document.createTextNode(mixed.length ? '選んだポチの新着はまだありません。' : '新着はまだありません。'));
      return;
    }
    status.hidden = true;
    var frag = document.createDocumentFragment();
    items.forEach(function (it) { frag.appendChild(card(it)); });
    list.appendChild(frag);
  }

  function fetchFeed(url) {
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctl ? setTimeout(function () { ctl.abort(); }, 10000) : null;
    return fetch(url, ctl ? { signal: ctl.signal } : {}).then(function (r) {
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }).then(function (j) { if (timer) clearTimeout(timer); return j; },
      function () { if (timer) clearTimeout(timer); return null; }); // 1つ失敗しても他は出す
  }

  function loadFeeds() {
    if (mixed || loading) return;
    loading = true;
    status.hidden = false;
    status.textContent = '新着を読み込み中…';
    Promise.all(feedUrls.map(fetchFeed)).then(function (res) {
      mixed = PochiDash.mix(res.filter(Boolean), PochiDash.jstToday(Date.now()));
      loading = false;
      render();
    });
  }

  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      var k = c.getAttribute('data-source'), i = off.indexOf(k);
      if (i < 0) off.push(k); else off.splice(i, 1);
      save(OFF_KEY, JSON.stringify(off));
      syncChips();
      render();
    });
  });

  function show(name, persist) {
    tabs.forEach(function (t) {
      var on = t.getAttribute('data-view') === name;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    panels.links.hidden = name !== 'links';
    panels.dash.hidden = name !== 'dash';
    if (persist) save(VIEW_KEY, name);
    if (name === 'dash') loadFeeds();
  }
  tabs.forEach(function (t, i) {
    t.addEventListener('click', function () { show(t.getAttribute('data-view'), true); });
    t.addEventListener('keydown', function (e) {
      var n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1;
      if (n < 0) return;
      e.preventDefault();
      n = (n + tabs.length) % tabs.length;
      tabs[n].focus();
      show(tabs[n].getAttribute('data-view'), true);
    });
  });

  show(load(VIEW_KEY) === 'dash' ? 'dash' : 'links', false);
})();
