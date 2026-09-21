// 親子上場ウォッチリスト(oyako.html)。data/oyako-jojo.json を読み込んで一覧を描画する。
(function () {
  'use strict';

  var DATA_URL = 'data/oyako-jojo.json';
  var state = { pairs: [], excluded: [], category: '', term: '', sort: 'ratio' };

  var tbody = document.getElementById('oyako-body');
  var countEl = document.getElementById('count');
  var statsEl = document.getElementById('stats');
  var excludedEl = document.getElementById('excluded');
  var updatedEl = document.getElementById('updated-at');

  function num(value) {
    if (value === null || value === undefined) return '―';
    return value.toLocaleString('ja-JP', { maximumFractionDigits: 0 });
  }

  function tagOf(category) {
    if (category === '連結子会社(50%超)') return ['tag-major', '50%超'];
    if (category === '持分法適用など(20〜50%)') return ['tag-minor', '20〜50%'];
    return ['tag-unknown', '未確認'];
  }

  function escapeHtml(text) {
    return String(text === null || text === undefined ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function matches(row) {
    if (state.category && row.category !== state.category) return false;
    if (!state.term) return true;
    var haystack = (row.name + row.parent_name + row.code + row.parent_code).toLowerCase();
    return haystack.indexOf(state.term) !== -1;
  }

  function compare(a, b) {
    if (state.sort === 'mcap') return (b.mcap || 0) - (a.mcap || 0);
    if (state.sort === 'pmcap') return (b.parent_mcap || 0) - (a.parent_mcap || 0);
    if (state.sort === 'code') return a.code.localeCompare(b.code);
    var ra = a.ratio === null || a.ratio === undefined ? -1 : a.ratio;
    var rb = b.ratio === null || b.ratio === undefined ? -1 : b.ratio;
    return rb - ra;
  }

  function render() {
    var rows = state.pairs.filter(matches).sort(compare);
    countEl.textContent = rows.length + ' 組を表示中(全 ' + state.pairs.length + ' 組)';

    tbody.innerHTML = rows.map(function (row) {
      var tag = tagOf(row.category);
      var ratio = row.ratio === null || row.ratio === undefined
        ? '―'
        : row.ratio.toFixed(2) + '<span class="sub">' + escapeHtml(row.ratio_type || '') + '</span>';
      var source = row.source
        ? '<a href="' + escapeHtml(row.source) + '" target="_blank" rel="noopener">出所</a>'
        : '';
      return '<tr>' +
        '<td><span class="tag ' + tag[0] + '">' + tag[1] + '</span></td>' +
        '<td><span class="name">' + escapeHtml(row.name) + '</span>' +
          '<span class="sub">' + escapeHtml(row.code) + '・' + escapeHtml(row.market || '') + '</span></td>' +
        '<td class="num">' + num(row.mcap) + '<span class="sub">億円</span></td>' +
        '<td class="num">' + (row.pbr === null || row.pbr === undefined ? '―' : row.pbr) + '</td>' +
        '<td><span class="name">' + escapeHtml(row.parent_name) + '</span>' +
          '<span class="sub">' + escapeHtml(row.parent_code) + '・' + escapeHtml(row.parent_market || '') + '</span></td>' +
        '<td class="num">' + num(row.parent_mcap) + '<span class="sub">億円</span></td>' +
        '<td class="num"><span class="ratio">' + ratio + '</span></td>' +
        '<td><span class="sub">' + escapeHtml(row.as_of || '不明') + '</span>' + source + '</td>' +
        '<td class="note">' + escapeHtml(row.note || '') + '</td>' +
        '</tr>';
    }).join('');
  }

  function renderStats() {
    var major = state.pairs.filter(function (r) { return r.category === '連結子会社(50%超)'; }).length;
    var minor = state.pairs.filter(function (r) { return r.category === '持分法適用など(20〜50%)'; }).length;
    var unknown = state.pairs.length - major - minor;
    var cells = [
      [state.pairs.length, '掲載している組み合わせ'],
      [major, '親会社が過半数を保有'],
      [minor, '20〜50%の保有'],
      [unknown, '比率を確認できず'],
      [state.excluded.length, '調べた結果、除外']
    ];
    statsEl.innerHTML = cells.map(function (cell) {
      return '<div><strong>' + cell[0] + '</strong><span>' + cell[1] + '</span></div>';
    }).join('');
  }

  function renderExcluded() {
    excludedEl.innerHTML = state.excluded.map(function (row) {
      return '<li><strong>' + escapeHtml(row.name) + '</strong>(' + escapeHtml(row.code) + ') ← ' +
        escapeHtml(row.parent_name) + ' <span class="why">' + escapeHtml(row.reason) + '</span></li>';
    }).join('');
  }

  document.getElementById('filter').addEventListener('input', function (event) {
    state.term = event.target.value.trim().toLowerCase();
    render();
  });

  document.getElementById('sort').addEventListener('change', function (event) {
    state.sort = event.target.value;
    render();
  });

  document.getElementById('cat-filter').addEventListener('click', function (event) {
    var button = event.target.closest('.chip');
    if (!button) return;
    Array.prototype.forEach.call(this.querySelectorAll('.chip'), function (chip) {
      chip.setAttribute('aria-pressed', chip === button ? 'true' : 'false');
    });
    state.category = button.dataset.cat;
    render();
  });

  fetch(DATA_URL)
    .then(function (response) {
      if (!response.ok) throw new Error('データを読み込めませんでした (' + response.status + ')');
      return response.json();
    })
    .then(function (data) {
      state.pairs = data.pairs || [];
      state.excluded = data.excluded || [];
      var meta = data.meta || {};
      updatedEl.textContent = '作成日 ' + (meta.created || '') +
        ' / 株価・時価総額は ' + (meta.price_date || '') + ' 終値 / 上場状況は ' +
        (meta.universe_date || '') + ' 時点の銘柄マスタで判定';
      renderStats();
      renderExcluded();
      render();
    })
    .catch(function (error) {
      updatedEl.textContent = error.message;
    });
})();
