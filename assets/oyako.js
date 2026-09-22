// 親子上場ウォッチリスト(oyako.html)。data/oyako-jojo.json と data/dissolution-rankings.csv を読み込んで一覧と予測ランキングを描画する。
(function () {
  'use strict';

  var DATA_URL = 'data/oyako-jojo.json';
  var RANKING_URL = 'data/dissolution-rankings.csv';
  var state = { pairs: [], excluded: [], category: '', term: '', sort: 'ratio', currentView: 'list' };
  var rankingState = { allData: [], term: '', sort: 'score' };
  var scoreMap = {};

  var tbody = document.getElementById('oyako-body');
  var countEl = document.getElementById('count');
  var statsEl = document.getElementById('stats');
  var excludedEl = document.getElementById('excluded');
  var updatedEl = document.getElementById('updated-at');
  var tableScrollTop = document.getElementById('table-scroll-top');
  var tableScrollTopContent = document.getElementById('table-scroll-top-content');
  var tableScrollBottom = document.getElementById('table-scroll-bottom');

  // Sync scroll between top and bottom
  tableScrollTop.addEventListener('scroll', function () {
    tableScrollBottom.scrollLeft = tableScrollTop.scrollLeft;
  });

  tableScrollBottom.addEventListener('scroll', function () {
    tableScrollTop.scrollLeft = tableScrollBottom.scrollLeft;
  });

  // Update top scroll container width based on table width
  function updateScrollTopWidth() {
    var table = document.getElementById('oyako-table');
    if (table && tableScrollTopContent) {
      tableScrollTopContent.style.width = table.scrollWidth + 'px';
      tableScrollTopContent.style.height = '1px';
    }
  }

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
      var score = scoreMap[row.code] || '―';
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
        '<td class="num">' + score + '</td>' +
        '<td><span class="sub">' + escapeHtml(row.as_of || '不明') + '</span>' + source + '</td>' +
        '<td class="note">' + escapeHtml(row.note || '') + '</td>' +
        '</tr>';
    }).join('');

    updateScrollTopWidth();
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

  // Ranking functions
  function parseRankingCSV(csv) {
    var lines = csv.trim().split('\n');
    var headers = lines[0].split(',');
    var data = [];
    for (var i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      var obj = {};
      var values = lines[i].split(',');
      headers.forEach(function (h, idx) {
        obj[h] = values[idx] || '';
      });
      data.push(obj);
    }
    return data;
  }

  function renderRankings() {
    var rankingsEl = document.getElementById('rankings');
    var rankingInfoEl = document.getElementById('ranking-info');
    var filtered = filterRankingData(rankingState.term);

    if (rankingState.sort === 'mcap') {
      filtered.sort(function (a, b) {
        return (parseFloat(b['時価総額(億円)']) || 0) - (parseFloat(a['時価総額(億円)']) || 0);
      });
    }

    rankingInfoEl.textContent = filtered.length + ' 組を表示中(全 ' + rankingState.allData.length + ' 組)';
    rankingsEl.innerHTML = filtered.slice(0, 50).map(function (row) {
      return '<div class="rank-card">' +
        '<div class="rank-number">' + escapeHtml(row['順位']) + '</div>' +
        '<div class="rank-info">' +
          '<div class="rank-title">' +
            escapeHtml(row['子会社名']) +
            '<span class="rank-score">スコア ' + escapeHtml(row['スコア']) + '</span>' +
          '</div>' +
          '<div class="rank-code">' +
            escapeHtml(row['子会社コード']) + ' / ' + escapeHtml(row['市場']) + ' 市場<br>' +
            '親会社: ' + escapeHtml(row['親会社']) + ' (' + escapeHtml(row['親会社コード']) + ')' +
          '</div>' +
          '<div class="rank-reason">' +
            '<strong>理由：</strong> ' + escapeHtml(row['スコアの根拠']).replace(/ \/ /g, '<br>') +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');

    if (filtered.length === 0) {
      rankingsEl.innerHTML = '<p style="text-align: center; color: var(--text-sub);">該当する銘柄がありません</p>';
    }
  }

  function filterRankingData(query) {
    if (!query) return rankingState.allData;
    var q = query.toLowerCase();
    return rankingState.allData.filter(function (row) {
      return (row['子会社コード'] || '').toLowerCase().includes(q) ||
             (row['子会社名'] || '').toLowerCase().includes(q) ||
             (row['親会社'] || '').toLowerCase().includes(q);
    });
  }

  function switchView(viewName) {
    state.currentView = viewName;
    var listView = document.getElementById('list-view');
    var rankingView = document.getElementById('ranking-view');
    var tabs = document.querySelectorAll('.tab-btn');

    tabs.forEach(function (tab) {
      if (tab.dataset.view === viewName) {
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
      } else {
        tab.classList.remove('active');
        tab.setAttribute('aria-selected', 'false');
      }
    });

    if (viewName === 'ranking') {
      listView.classList.remove('active');
      rankingView.classList.add('active');
      if (rankingState.allData.length > 0) {
        renderRankings();
      }
    } else {
      rankingView.classList.remove('active');
      listView.classList.add('active');
    }
  }

  // View tab click handlers
  document.querySelectorAll('.tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      switchView(this.dataset.view);
    });
  });

  // Ranking view event handlers
  document.getElementById('ranking-filter').addEventListener('input', function (event) {
    rankingState.term = event.target.value.trim().toLowerCase();
    renderRankings();
  });

  document.getElementById('ranking-sort').addEventListener('change', function (event) {
    rankingState.sort = event.target.value;
    renderRankings();
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
      setTimeout(updateScrollTopWidth, 0);
    })
    .catch(function (error) {
      updatedEl.textContent = error.message;
    });

  // Load ranking data
  fetch(RANKING_URL)
    .then(function (response) {
      if (!response.ok) throw new Error('ランキングデータを読み込めませんでした');
      return response.text();
    })
    .then(function (csv) {
      rankingState.allData = parseRankingCSV(csv);
      rankingState.allData.forEach(function (row) {
        scoreMap[row['子会社コード']] = row['スコア'];
      });
      render();
    })
    .catch(function (error) {
      console.error('ランキングデータの読み込みに失敗しました:', error);
    });
})();
