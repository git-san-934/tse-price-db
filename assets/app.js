(() => {
  "use strict";

  const state = {
    items: [],
    historyCache: new Map(),
    sortKey: "code",
    sortAsc: true,
    filter: "",
  };

  const tbody = document.getElementById("stock-tbody");
  const updatedAtEl = document.getElementById("updated-at");
  const filterInput = document.getElementById("filter");
  const detail = document.getElementById("detail");
  const detailTitle = document.getElementById("detail-title");
  const detailReasons = document.getElementById("detail-reasons");
  const detailChart = document.getElementById("detail-chart");
  const detailTbody = document.getElementById("detail-tbody");
  const detailClose = document.getElementById("detail-close");

  const numberFmt = (n) => (n === null || n === undefined ? "―" : n.toLocaleString("ja-JP"));
  const yenFmt = (n) => (n === null || n === undefined ? "―" : n.toLocaleString("ja-JP", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));

  function badgeClass(judgment) {
    if (judgment === "高値圏") return "badge-high";
    if (judgment === "安値圏") return "badge-low";
    if (judgment === "中立") return "badge-neutral";
    return "badge-neutral";
  }

  function sortedFilteredItems() {
    const q = state.filter.trim().toLowerCase();
    let rows = state.items;
    if (q) {
      rows = rows.filter(
        (r) => r.code.toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q)
      );
    }
    const key = state.sortKey;
    const dir = state.sortAsc ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "string") return av.localeCompare(bv, "ja") * dir;
      return (av - bv) * dir;
    });
  }

  function render() {
    const rows = sortedFilteredItems();
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" class="empty">該当する銘柄がありません</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr data-code="${r.code}">
        <td>${r.code}</td>
        <td>${r.name || ""}</td>
        <td>${r.date || "―"}</td>
        <td>${yenFmt(r.open)}</td>
        <td>${yenFmt(r.high)}</td>
        <td>${yenFmt(r.low)}</td>
        <td>${yenFmt(r.close)}</td>
        <td>${numberFmt(r.volume)}</td>
        <td>${yenFmt(r.ma25)}</td>
        <td>${yenFmt(r.ma75)}</td>
        <td><span class="badge ${badgeClass(r.judgment)}">${r.judgment}</span></td>
      </tr>`
      )
      .join("");

    document.querySelectorAll("#stock-tbody tr[data-code]").forEach((tr) => {
      tr.addEventListener("click", () => openDetail(tr.dataset.code));
    });

    document.querySelectorAll("thead th[data-key]").forEach((th) => {
      th.classList.toggle("sorted", th.dataset.key === state.sortKey);
      th.classList.toggle("asc", th.dataset.key === state.sortKey && state.sortAsc);
    });
  }

  function setupSorting() {
    document.querySelectorAll("thead th[data-key]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        if (state.sortKey === key) {
          state.sortAsc = !state.sortAsc;
        } else {
          state.sortKey = key;
          state.sortAsc = key === "code" || key === "name";
        }
        render();
      });
    });
  }

  function buildChart(rows) {
    const w = 640;
    const h = 220;
    const padTop = 10;
    const padBottom = 10;
    const values = [];
    rows.forEach((r) => {
      if (r.close !== null) values.push(r.close);
      if (r.ma25 !== null) values.push(r.ma25);
      if (r.ma75 !== null) values.push(r.ma75);
    });
    if (values.length === 0) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const x = (i) => (rows.length <= 1 ? w / 2 : (i / (rows.length - 1)) * w);
    const y = (v) => padTop + (1 - (v - min) / range) * (h - padTop - padBottom);

    const toPath = (key) => {
      let d = "";
      let started = false;
      rows.forEach((r, i) => {
        const v = r[key];
        if (v === null || v === undefined) {
          started = false;
          return;
        }
        const cmd = started ? "L" : "M";
        d += `${cmd}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
        started = true;
      });
      return d.trim();
    };

    return `
      <path d="${toPath("close")}" fill="none" stroke="var(--text)" stroke-width="1.6" />
      <path d="${toPath("ma25")}" fill="none" stroke="var(--accent)" stroke-width="1.4" />
      <path d="${toPath("ma75")}" fill="none" stroke="var(--low)" stroke-width="1.4" />
    `;
  }

  async function fetchHistory(code) {
    if (state.historyCache.has(code)) return state.historyCache.get(code);
    try {
      const res = await fetch(`data/history/${encodeURIComponent(code)}.json`, { cache: "no-store" });
      const rows = res.ok ? await res.json() : [];
      state.historyCache.set(code, rows);
      return rows;
    } catch (err) {
      console.error(err);
      return [];
    }
  }

  async function openDetail(code) {
    const item = state.items.find((r) => r.code === code);
    if (!item) return;

    detailTitle.textContent = `${item.code} ${item.name || ""}`.trim();
    detailReasons.textContent = (item.reasons || []).join(" / ");
    detailChart.innerHTML = "";
    detailTbody.innerHTML = `<tr><td colspan="8" class="loading">読み込み中...</td></tr>`;
    detail.hidden = false;
    detail.scrollIntoView({ behavior: "smooth", block: "start" });

    const rows = await fetchHistory(code);
    if (detailTitle.textContent !== `${item.code} ${item.name || ""}`.trim()) return; // 別銘柄に切り替わっていたら破棄

    detailChart.innerHTML = buildChart(rows);

    const tailRows = rows.slice(-20).reverse();
    detailTbody.innerHTML = tailRows.length
      ? tailRows
          .map(
            (r) => `
      <tr>
        <td>${r.date}</td>
        <td>${yenFmt(r.open)}</td>
        <td>${yenFmt(r.high)}</td>
        <td>${yenFmt(r.low)}</td>
        <td>${yenFmt(r.close)}</td>
        <td>${numberFmt(r.volume)}</td>
        <td>${yenFmt(r.ma25)}</td>
        <td>${yenFmt(r.ma75)}</td>
      </tr>`
          )
          .join("")
      : `<tr><td colspan="8" class="empty">データがありません</td></tr>`;
  }

  detailClose.addEventListener("click", () => {
    detail.hidden = true;
  });

  let filterTimer = null;
  filterInput.addEventListener("input", (e) => {
    const value = e.target.value;
    clearTimeout(filterTimer);
    filterTimer = setTimeout(() => {
      state.filter = value;
      render();
    }, 120);
  });

  async function loadData() {
    try {
      const latestRes = await fetch("data/latest.json", { cache: "no-store" });
      if (!latestRes.ok) throw new Error("data fetch failed");
      const latest = await latestRes.json();

      state.items = latest.items || [];

      const parts = [];
      if (latest.updated_at) parts.push(`最終更新: ${latest.updated_at.replace("T", " ")}`);
      if (
        typeof latest.backfill_done === "number" &&
        typeof latest.backfill_total === "number" &&
        latest.backfill_done < latest.backfill_total
      ) {
        parts.push(
          `初回データ取り込み中: ${latest.backfill_done.toLocaleString("ja-JP")} / ${latest.backfill_total.toLocaleString("ja-JP")} 銘柄`
        );
      }
      updatedAtEl.textContent = parts.join(" ・ ");

      render();
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="11" class="empty">データの読み込みに失敗しました。まだ初回のデータ更新(GitHub Actions)が実行されていない可能性があります。</td></tr>`;
      updatedAtEl.textContent = "";
      console.error(err);
    }
  }

  setupSorting();
  loadData();
})();
