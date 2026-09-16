(() => {
  "use strict";

  const state = {
    items: [],
    historyCache: new Map(),
    sortKey: "code",
    sortAsc: true,
    filter: "",
    period: "6mo",
    currentCode: null,
  };

  const tbody = document.getElementById("stock-tbody");
  const updatedAtEl = document.getElementById("updated-at");
  const filterInput = document.getElementById("filter");
  const exportCsvBtn = document.getElementById("export-csv");
  const detail = document.getElementById("detail");
  const detailTitle = document.getElementById("detail-title");
  const detailReasons = document.getElementById("detail-reasons");
  const detailChart = document.getElementById("detail-chart");
  const detailTbody = document.getElementById("detail-tbody");
  const detailClose = document.getElementById("detail-close");
  const periodButtons = document.querySelectorAll(".period-btn");
  const legendMa25 = document.getElementById("legend-ma25");
  const legendMa75 = document.getElementById("legend-ma75");
  const tableScroll = document.getElementById("table-scroll");
  const tableScrollTop = document.getElementById("table-scroll-top");
  const tableScrollTopInner = document.getElementById("table-scroll-top-inner");
  const stockTable = document.getElementById("stock-table");
  const toTopBtn = document.getElementById("to-top-btn");

  const numberFmt = (n) => (n === null || n === undefined ? "―" : n.toLocaleString("ja-JP"));
  const yenFmt = (n) => (n === null || n === undefined ? "―" : n.toLocaleString("ja-JP", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
  const okuFmt = (n) =>
    n === null || n === undefined
      ? "―"
      : (n / 1e8).toLocaleString("ja-JP", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const perFmt = (n) =>
    n === null || n === undefined
      ? "―"
      : `${n.toLocaleString("ja-JP", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}倍`;

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
      tbody.innerHTML = `<tr><td colspan="14" class="empty">該当する銘柄がありません</td></tr>`;
      syncTableScrollWidth();
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
        <td>${okuFmt(r.marketCap)}</td>
        <td>${numberFmt(r.turnover)}</td>
        <td>${perFmt(r.per)}</td>
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

    syncTableScrollWidth();
  }

  function syncTableScrollWidth() {
    tableScrollTopInner.style.width = `${stockTable.scrollWidth}px`;
  }

  function setupScrollSync() {
    let syncing = false;
    tableScrollTop.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      tableScroll.scrollLeft = tableScrollTop.scrollLeft;
      syncing = false;
    });
    tableScroll.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      tableScrollTop.scrollLeft = tableScroll.scrollLeft;
      syncing = false;
    });

    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(syncTableScrollWidth, 120);
    });
  }

  function setupToTopButton() {
    window.addEventListener(
      "scroll",
      () => {
        toTopBtn.hidden = window.scrollY < 400;
      },
      { passive: true }
    );
    toTopBtn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
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
      if (r.close != null) values.push(r.close);
      if (r.ma25 != null) values.push(r.ma25);
      if (r.ma75 != null) values.push(r.ma75);
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

  async function fetchHistory(code, period) {
    const key = `${period}:${code}`;
    if (state.historyCache.has(key)) return state.historyCache.get(key);
    const path =
      period === "5y"
        ? `data/history_weekly/${encodeURIComponent(code)}.json`
        : `data/history/${encodeURIComponent(code)}.json`;
    try {
      const res = await fetch(path, { cache: "no-store" });
      const rows = res.ok ? await res.json() : [];
      state.historyCache.set(key, rows);
      return rows;
    } catch (err) {
      console.error(err);
      return [];
    }
  }

  function syncPeriodButtons() {
    periodButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.period === state.period);
    });
    const showMa = state.period !== "5y";
    legendMa25.hidden = !showMa;
    legendMa75.hidden = !showMa;
  }

  async function loadDetailChart() {
    const code = state.currentCode;
    detailChart.innerHTML = "";
    const rows = await fetchHistory(code, state.period);
    if (state.currentCode !== code) return; // 別銘柄・別期間に切り替わっていたら破棄
    detailChart.innerHTML = buildChart(rows);
  }

  async function loadDetailTable() {
    const code = state.currentCode;
    detailTbody.innerHTML = `<tr><td colspan="8" class="loading">読み込み中...</td></tr>`;
    const rows = await fetchHistory(code, "6mo");
    if (state.currentCode !== code) return;

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

  async function openDetail(code) {
    const item = state.items.find((r) => r.code === code);
    if (!item) return;

    state.currentCode = code;
    detailTitle.textContent = `${item.code} ${item.name || ""}`.trim();
    detailReasons.textContent = (item.reasons || []).join(" / ");
    syncPeriodButtons();
    detail.hidden = false;
    detail.scrollIntoView({ behavior: "smooth", block: "start" });

    await Promise.all([loadDetailChart(), loadDetailTable()]);
  }

  periodButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.period === btn.dataset.period || !state.currentCode) return;
      state.period = btn.dataset.period;
      syncPeriodButtons();
      loadDetailChart();
    });
  });

  detailClose.addEventListener("click", () => {
    detail.hidden = true;
    state.currentCode = null;
  });

  function csvField(value) {
    const s = value === null || value === undefined ? "" : String(value);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  function exportCsv() {
    const rows = sortedFilteredItems();
    const header = [
      "コード", "銘柄名", "日付", "始値", "高値", "安値", "終値", "出来高",
      "時価総額(億円)", "売買代金", "PER(倍)", "MA25", "MA75", "判定",
    ];
    const lines = [header.map(csvField).join(",")];
    rows.forEach((r) => {
      const marketCapOku = r.marketCap == null ? null : r.marketCap / 1e8;
      lines.push(
        [r.code, r.name, r.date, r.open, r.high, r.low, r.close, r.volume, marketCapOku, r.turnover, r.per, r.ma25, r.ma75, r.judgment]
          .map(csvField)
          .join(",")
      );
    });
    const csv = "﻿" + lines.join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const now = new Date();
    const stamp = now.toISOString().slice(0, 10).replace(/-/g, "");
    const a = document.createElement("a");
    a.href = url;
    a.download = `tse-price-db_${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  exportCsvBtn.addEventListener("click", exportCsv);

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

      state.items = (latest.items || []).map((item) => ({
        ...item,
        marketCap: item.market_cap,
      }));

      const parts = [];
      if (latest.updated_at) parts.push(`最終更新: ${latest.updated_at.replace("T", " ")}`);
      if (
        typeof latest.codes_with_data === "number" &&
        typeof latest.codes_total === "number" &&
        latest.codes_with_data < latest.codes_total
      ) {
        parts.push(
          `データ取得済み: ${latest.codes_with_data.toLocaleString("ja-JP")} / ${latest.codes_total.toLocaleString("ja-JP")} 銘柄`
        );
      }
      updatedAtEl.textContent = parts.join(" ・ ");

      render();
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="14" class="empty">データの読み込みに失敗しました。まだ初回のデータ更新(GitHub Actions)が実行されていない可能性があります。</td></tr>`;
      updatedAtEl.textContent = "";
      console.error(err);
    }
  }

  setupSorting();
  setupScrollSync();
  setupToTopButton();
  loadData();
})();
