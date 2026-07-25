/* ═══════════════════════════════════════════════════════════
   BIST Trade Asistan — Frontend JavaScript
═══════════════════════════════════════════════════════════ */

'use strict';

// ─── STATE ───────────────────────────────────────────────
const state = {
  universe: 'bist30',
  scanning: false,
  scanResults: [],
  selectedTicker: null,
};

// ─── DOM REFERANSLARI ─────────────────────────────────────
const $ = (id) => document.getElementById(id);

// ─── YARDIMCI FONKSİYONLAR ───────────────────────────────

function fmt(val, decimals = 2) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toFixed(decimals);
}

function fmtTL(val) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₺';
}

function fmtPct(val) {
  if (val == null || isNaN(val)) return '—';
  const sign = val >= 0 ? '+' : '';
  return sign + Number(val).toFixed(2) + '%';
}

function fmtNum(val) {
  if (val == null || isNaN(val)) return '—';
  return Number(val).toLocaleString('tr-TR');
}

function changeClass(val) {
  if (val > 0) return 'pos';
  if (val < 0) return 'neg';
  return 'neu';
}

function colorClass(color) {
  if (!color) return 'yellow';
  return color; // 'green', 'yellow', 'red'
}

function scoreColor(score) {
  if (score >= 75) return 'green';
  if (score >= 50) return 'yellow';
  return 'red';
}

function showToast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  $('toastContainer').appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ─── SAAT & BORSA DURUMU ─────────────────────────────────

function updateClock() {
  const now = new Date();
  const hour = now.getHours();
  const min  = now.getMinutes();

  $('marketTime').textContent =
    String(hour).padStart(2, '0') + ':' + String(min).padStart(2, '0');

  const isOpen = (hour > 10 || (hour === 10 && min >= 0)) && hour < 18;
  // BIST: 10:00 - 18:00 Türkiye saati
  const statusEl = $('marketStatus');
  if (isOpen) {
    statusEl.textContent = '● Borsa Açık';
    statusEl.className = 'market-status open';
  } else {
    statusEl.textContent = '● Borsa Kapalı';
    statusEl.className = 'market-status';
  }
}

// ─── TARAYICI ─────────────────────────────────────────────

async function runScan(universe = state.universe) {
  if (state.scanning) return;
  state.scanning = true;

  // UI güncelle
  const loading = $('scannerLoading');
  const results = $('scannerResults');
  loading.classList.remove('hidden');
  results.innerHTML = '';
  $('scannerCount').textContent = 'Taranıyor…';

  try {
    const res = await fetch(`/api/scan?universe=${universe}&top=20`);
    const data = await res.json();

    if (data.status !== 'ok') throw new Error(data.message);

    state.scanResults = data.results || [];
    renderScanResults(state.scanResults);

    const suitable = state.scanResults.filter(r => r.suitable).length;
    $('scannerCount').textContent = `${suitable} fırsat / ${state.scanResults.length} hisse`;
    $('statusLastUpdate').textContent = `Son güncelleme: ${data.timestamp}`;

  } catch (err) {
    results.innerHTML = `<div class="risk-error" style="margin:0.5rem">Tarama hatası: ${err.message}</div>`;
    showToast('Tarama başarısız: ' + err.message, 'error');
  } finally {
    loading.classList.add('hidden');
    state.scanning = false;
  }
}

function renderScanResults(results) {
  const container = $('scannerResults');
  container.innerHTML = '';

  if (!results.length) {
    container.innerHTML = '<div class="empty-state" style="height:200px"><p>Sonuç bulunamadı</p></div>';
    return;
  }

  results.forEach((r, i) => {
    const card = document.createElement('div');
    const cc = colorClass(r.color);
    const chgClass = changeClass(r.change_1d);
    const chgText = fmtPct(r.change_1d);

    card.className = `stock-card ${cc}`;
    card.dataset.ticker = r.ticker;
    card.innerHTML = `
      <div class="card-row1">
        <span class="card-ticker">${r.ticker}</span>
        <span class="card-price">${fmtTL(r.price)}</span>
      </div>
      <div class="card-row2">
        <span class="card-sector">${r.sector || ''}</span>
        <span class="card-change ${chgClass}">${chgText}</span>
      </div>
      <div class="score-bar-wrap">
        <div class="score-bar-track">
          <div class="score-bar-fill ${cc}" style="width:0%" data-width="${r.score}%"></div>
        </div>
        <span class="score-value ${cc}">${r.score}</span>
      </div>
      <div class="card-levels">
        <div class="level-badge">
          <span class="level-badge-label">📌 Al</span>
          <span class="level-badge-val">${fmt(r.entry)}</span>
        </div>
        <div class="level-badge">
          <span class="level-badge-label">🎯 Hedef</span>
          <span class="level-badge-val">${fmt(r.target1)}</span>
        </div>
        <div class="level-badge">
          <span class="level-badge-label">🛑 Stop</span>
          <span class="level-badge-val">${fmt(r.stop)}</span>
        </div>
      </div>
    `;

    card.addEventListener('click', () => {
      document.querySelectorAll('.stock-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      loadAnalysis(r.ticker);
      prefillRisk(r);
    });

    container.appendChild(card);

    // Animasyonlu bar
    setTimeout(() => {
      const fill = card.querySelector('.score-bar-fill');
      if (fill) fill.style.width = fill.dataset.width;
    }, 50 + i * 30);
  });
}

// ─── ANALİZ ───────────────────────────────────────────────

async function loadAnalysis(ticker) {
  if (!ticker) return;
  ticker = ticker.toUpperCase().trim();
  state.selectedTicker = ticker;

  // Analiz sekmesini aktif et
  switchTab('analyze');

  // Input'u güncelle
  $('analyzeInput').value = ticker;

  const container = $('analyzeResult');
  container.innerHTML = `
    <div class="result-loading">
      <div class="spinner"></div>
      <span>${ticker} analiz ediliyor…</span>
    </div>
  `;

  try {
    const res = await fetch(`/api/analyze?ticker=${encodeURIComponent(ticker)}`);
    const data = await res.json();

    if (data.status !== 'ok') {
      container.innerHTML = `<div class="risk-error" style="padding:1rem">${data.message}</div>`;
      return;
    }

    renderAnalysis(data, container);

  } catch (err) {
    container.innerHTML = `<div class="risk-error" style="padding:1rem">Bağlantı hatası: ${err.message}</div>`;
  }
}

function renderAnalysis(data, container) {
  const s = data.score || {};
  const ind = data.indicators || {};
  const summary = data.status_summary || {};
  const targets = s.targets || {};
  const cc = colorClass(s.color);

  // Skor çubuklarını render et
  const scoreRows = [
    { label: 'Trend Gücü',    val: s.trend,    max: 20 },
    { label: 'Hacim Kalitesi',val: s.volume,   max: 20 },
    { label: 'Pivot Konumu',  val: s.pivot,    max: 20 },
    { label: 'Risk/Ödül',     val: s.rr,       max: 20 },
    { label: 'Momentum',      val: s.momentum, max: 20 },
  ];

  const scoreRowsHTML = scoreRows.map(r => {
    const pct = ((r.val || 0) / r.max) * 100;
    const fc = pct >= 70 ? 'green' : pct >= 40 ? 'yellow' : 'red';
    return `
      <div class="score-row">
        <span class="score-row-label">${r.label}</span>
        <div class="score-row-bar">
          <div class="score-row-fill ${fc}" style="width:0%" data-width="${pct}%"></div>
        </div>
        <span class="score-row-val">${r.val}/${r.max}</span>
      </div>
    `;
  }).join('');

  // Teknik değerler
  const fp  = ind.floor_pivots || {};
  const cam = ind.camarilla || {};
  const vwapAbove = ind.above_vwap;

  // Özet listesi
  const mkItem = (arr, cls) => arr.map(t =>
    `<div class="summary-item ${cls}"><span>${cls === 'positive' ? '✅' : cls === 'warning' ? '⚠️' : '📡'}</span><span>${t}</span></div>`
  ).join('');

  container.innerHTML = `
    <div class="analyze-card">
      <!-- Başlık -->
      <div class="analyze-header">
        <div class="analyze-name">
          <span class="analyze-ticker">${data.ticker}</span>
          <span class="analyze-company">${data.name}</span>
          <span class="analyze-sector-badge">${data.sector}</span>
        </div>
        <div class="analyze-verdict">
          <div class="verdict-badge ${cc}">${s.verdict || '—'}</div>
          <div class="verdict-score ${cc}">${s.total || 0}/100</div>
        </div>
      </div>

      <!-- Verdict metin -->
      <div class="risk-${cc === 'green' ? 'highlight' : (cc === 'red' ? 'error' : 'warning')}" style="padding:0.6rem 0.8rem;border-radius:6px;font-size:0.8rem;line-height:1.5">
        ${summary.verdict_text || ''}
      </div>

      <!-- Skor detayı -->
      <div class="score-breakdown">
        <div class="score-breakdown-title">Skor Dağılımı</div>
        ${scoreRowsHTML}
      </div>

      <!-- Al/Sat Seviyeleri -->
      <div>
        <div class="section-title">Giriş / Kar-Al / Stop-Loss</div>
        <div class="levels-box">
          <div class="level-card entry">
            <div class="level-card-icon">📌</div>
            <div class="level-card-label">Giriş Fiyatı</div>
            <div class="level-card-price">${fmt(targets.entry)} ₺</div>
            <div class="level-card-note">Mevcut fiyat</div>
          </div>
          <div class="level-card target">
            <div class="level-card-icon">🎯</div>
            <div class="level-card-label">Kar-Al Hedefi</div>
            <div class="level-card-price">${fmt(targets.target1)} ₺</div>
            <div class="level-card-note">R1 / H3 seviyesi</div>
          </div>
          <div class="level-card stop">
            <div class="level-card-icon">🛑</div>
            <div class="level-card-label">Stop-Loss</div>
            <div class="level-card-price">${fmt(targets.stop)} ₺</div>
            <div class="level-card-note">R/R: 1:${fmt(targets.rr_ratio, 1)}</div>
          </div>
        </div>
      </div>

      <!-- Teknik Göstergeler -->
      <div>
        <div class="section-title">Teknik Göstergeler</div>
        <div class="tech-grid">
          <div class="tech-item">
            <span class="tech-label">RSI (14)</span>
            <span class="tech-val ${ind.rsi >= 70 ? 'red' : ind.rsi <= 30 ? 'yellow' : 'green'}">${fmt(ind.rsi, 1)}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">VWAP</span>
            <span class="tech-val ${vwapAbove ? 'green' : 'red'}">${vwapAbove ? 'Üstünde ✅' : 'Altında ⚠️'}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">EMA 9</span>
            <span class="tech-val ${ind.current_price >= ind.ema9 ? 'green' : 'red'}">${fmt(ind.ema9)}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">EMA 20</span>
            <span class="tech-val ${ind.current_price >= ind.ema20 ? 'green' : 'red'}">${fmt(ind.ema20)}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">Hacim Oranı</span>
            <span class="tech-val ${ind.volume_ratio >= 1.5 ? 'green' : ind.volume_ratio >= 1.0 ? 'yellow' : 'red'}">${fmt(ind.volume_ratio, 1)}x</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">ATR %</span>
            <span class="tech-val">${fmt(ind.atr_pct)}%</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">Trend</span>
            <span class="tech-val ${ind.trend === 'YUKARI' ? 'green' : ind.trend === 'AŞAĞI' ? 'red' : 'yellow'}">${ind.trend || '—'}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">MACD Cross</span>
            <span class="tech-val ${ind.macd_bullish_cross ? 'green' : 'yellow'}">${ind.macd_bullish_cross ? 'Bullish 🚀' : 'Yok'}</span>
          </div>
        </div>
      </div>

      <!-- Özet -->
      <div>
        <div class="section-title">Analiz Özeti</div>
        <div class="summary-list">
          ${mkItem(summary.positives || [], 'positive')}
          ${mkItem(summary.signals || [], 'signal')}
          ${mkItem(summary.warnings || [], 'warning')}
        </div>
      </div>

      <!-- Pivot Seviyeleri -->
      <div>
        <div class="section-title">Pivot Seviyeleri (Önceki Gün Bazlı)</div>
        <table class="pivot-table">
          <thead>
            <tr>
              <th>Seviye</th>
              <th>Floor Pivot</th>
              <th>Camarilla</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>R2 / H4</td>
              <td>${fmt(fp.R2)}</td>
              <td>${fmt(cam.H4)}</td>
            </tr>
            <tr>
              <td>R1 / H3</td>
              <td>${fmt(fp.R1)}</td>
              <td>${fmt(cam.H3)}</td>
            </tr>
            <tr class="highlight">
              <td>Pivot (P)</td>
              <td><strong>${fmt(fp.P)}</strong></td>
              <td>—</td>
            </tr>
            <tr>
              <td>S1 / L3</td>
              <td>${fmt(fp.S1)}</td>
              <td>${fmt(cam.L3)}</td>
            </tr>
            <tr>
              <td>S2 / L4</td>
              <td>${fmt(fp.S2)}</td>
              <td>${fmt(cam.L4)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 52 Haftalık İstatistikler -->
      <div>
        <div class="section-title">İstatistikler</div>
        <div class="tech-grid">
          <div class="tech-item">
            <span class="tech-label">52H Yüksek</span>
            <span class="tech-val">${fmt(data.stats?.high_52w)} ₺</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">52H Düşük</span>
            <span class="tech-val">${fmt(data.stats?.low_52w)} ₺</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">Yüksekten Uzaklık</span>
            <span class="tech-val ${data.stats?.from_high_52w >= 0 ? 'green' : 'red'}">${fmtPct(data.stats?.from_high_52w)}</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">5 Günlük Değişim</span>
            <span class="tech-val ${ind.price_change_5d >= 0 ? 'green' : 'red'}">${fmtPct(ind.price_change_5d)}</span>
          </div>
        </div>
      </div>
    </div>
  `;

  // Animasyonlu barlar
  setTimeout(() => {
    container.querySelectorAll('[data-width]').forEach(el => {
      el.style.width = el.dataset.width;
    });
  }, 50);
}

// ─── KARŞILAŞTIRMA ────────────────────────────────────────

async function runCompare() {
  const t1 = $('compareInput1').value.toUpperCase().trim();
  const t2 = $('compareInput2').value.toUpperCase().trim();

  if (!t1 || !t2) {
    showToast('İki hisse kodu girin.', 'error');
    return;
  }
  if (t1 === t2) {
    showToast('Aynı hisseyi iki kez girdiniz.', 'error');
    return;
  }

  const container = $('compareResult');
  container.innerHTML = `
    <div class="result-loading">
      <div class="spinner"></div>
      <span>${t1} ve ${t2} karşılaştırılıyor…</span>
    </div>
  `;

  try {
    const res = await fetch(`/api/compare?ticker1=${t1}&ticker2=${t2}`);
    const data = await res.json();

    if (data.status !== 'ok') {
      container.innerHTML = `<div class="risk-error" style="padding:1rem">${data.message}</div>`;
      return;
    }

    renderComparison(data, container);

  } catch (err) {
    container.innerHTML = `<div class="risk-error" style="padding:1rem">Bağlantı hatası: ${err.message}</div>`;
  }
}

function renderComparison(data, container) {
  const s1 = data.stock1 || {};
  const s2 = data.stock2 || {};
  const cmp = data.comparison || {};

  // Kazanan banner
  let winnerHTML = '';
  if (data.winner === null) {
    winnerHTML = `
      <div class="tie-banner">
        <p>🤝 <strong>Beraberlik!</strong> İki hisse birbirine çok yakın skor aldı.</p>
        <p style="margin-top:0.3rem;font-size:0.72rem;color:var(--text-muted)">${(data.winner_reasons || []).join(' ')}</p>
      </div>
    `;
  } else {
    const winName = data.winner_name;
    const reasons = (data.winner_reasons || []).slice(0, 3);
    winnerHTML = `
      <div class="winner-banner">
        <span class="winner-trophy">🏆</span>
        <div class="winner-text">
          <h3>${winName} daha iyi!</h3>
          <p>${reasons.join(' · ')}</p>
        </div>
      </div>
    `;
  }

  // Özet kutular
  const mkStock = (s, isWinner) => `
    <div class="level-card ${isWinner ? 'entry' : ''}">
      <div class="level-card-icon">${isWinner ? '🏆' : '📊'}</div>
      <div class="analyze-ticker" style="font-size:1rem">${s.ticker}</div>
      <div class="verdict-score ${colorClass(s.color)}" style="font-size:1.2rem">${s.score}/100</div>
      <div class="level-card-note">${s.suitable ? '✅ Uygun' : '❌ Uygun Değil'}</div>
      <div class="level-card-note" style="margin-top:0.2rem">R/R 1:${fmt(s.targets?.rr_ratio, 1)}</div>
    </div>
  `;

  // Karşılaştırma satırları
  const cmpOrder = ['total_score', 'trend', 'volume', 'momentum', 'rr', 'pivot',
                    'rsi', 'volume_ratio', 'rr_ratio', 'atr_pct', 'vwap_status', 'price_change_1d'];

  const cmpRowsHTML = cmpOrder.map(key => {
    const row = cmp[key];
    if (!row) return '';
    const w = row.winner;
    const v1 = typeof row.val1 === 'number' ? fmt(row.val1, 1) : row.val1;
    const v2 = typeof row.val2 === 'number' ? fmt(row.val2, 1) : row.val2;
    const unit = row.unit || '';
    return `
      <div class="compare-row">
        <span class="cmp-label">${row.label}</span>
        <span class="cmp-val ${w === 1 ? 'winner' : 'loser'}">
          ${w === 1 ? '<span class="win-marker"></span>' : ''}
          ${v1}${unit}
        </span>
        <span class="cmp-val ${w === 2 ? 'winner' : 'loser'}">
          ${w === 2 ? '<span class="win-marker"></span>' : ''}
          ${v2}${unit}
        </span>
      </div>
    `;
  }).join('');

  container.innerHTML = `
    <div class="compare-card">
      ${winnerHTML}

      <div class="levels-box" style="grid-template-columns:1fr 1fr">
        ${mkStock(s1, data.winner === 1)}
        ${mkStock(s2, data.winner === 2)}
      </div>

      <div class="compare-table">
        <div class="compare-table-header">
          <span>Kriter</span>
          <span>${data.ticker1}</span>
          <span>${data.ticker2}</span>
        </div>
        ${cmpRowsHTML}
      </div>

      <!-- Giriş seviyeleri karşılaştırması -->
      <div>
        <div class="section-title">${data.ticker1} — Giriş Seviyeleri</div>
        <div class="levels-box">
          <div class="level-card entry"><div class="level-card-label">Giriş</div><div class="level-card-price">${fmt(s1.targets?.entry)} ₺</div></div>
          <div class="level-card target"><div class="level-card-label">Hedef</div><div class="level-card-price">${fmt(s1.targets?.target1)} ₺</div></div>
          <div class="level-card stop"><div class="level-card-label">Stop</div><div class="level-card-price">${fmt(s1.targets?.stop)} ₺</div></div>
        </div>
      </div>

      <div>
        <div class="section-title">${data.ticker2} — Giriş Seviyeleri</div>
        <div class="levels-box">
          <div class="level-card entry"><div class="level-card-label">Giriş</div><div class="level-card-price">${fmt(s2.targets?.entry)} ₺</div></div>
          <div class="level-card target"><div class="level-card-label">Hedef</div><div class="level-card-price">${fmt(s2.targets?.target1)} ₺</div></div>
          <div class="level-card stop"><div class="level-card-label">Stop</div><div class="level-card-price">${fmt(s2.targets?.stop)} ₺</div></div>
        </div>
      </div>
    </div>
  `;
}

// ─── RİSK HESAPLAYICI ─────────────────────────────────────

async function calcRisk() {
  const account = parseFloat($('riskAccount').value);
  const entry   = parseFloat($('riskEntry').value);
  const stop    = parseFloat($('riskStop').value);
  const target  = parseFloat($('riskTarget').value) || 0;
  const riskPct = parseFloat($('riskPct').value) || 2;

  if (!account || !entry || !stop) {
    showToast('Hesap büyüklüğü, giriş ve stop fiyatı zorunlu.', 'error');
    return;
  }

  try {
    const res = await fetch('/api/risk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_size: account, entry_price: entry,
                              stop_price: stop, target_price: target, risk_pct: riskPct }),
    });
    const data = await res.json();

    if (data.status !== 'ok') {
      $('riskResult').innerHTML = `<div class="risk-error">${data.message}</div>`;
      return;
    }

    renderRiskResult(data);
  } catch (err) {
    $('riskResult').innerHTML = `<div class="risk-error">Bağlantı hatası: ${err.message}</div>`;
  }
}

function renderRiskResult(d) {
  const warnings = (d.warnings || []).map(w =>
    `<div class="risk-warning">${w}</div>`
  ).join('');

  const profitRow = d.potential_profit != null ? `
    <div class="risk-row">
      <span class="risk-row-label">Potansiyel Kazanç</span>
      <span class="risk-row-val green">+${fmtTL(d.potential_profit)}</span>
    </div>
    <div class="risk-row">
      <span class="risk-row-label">Risk/Ödül</span>
      <span class="risk-row-val ${d.rr_ratio >= 2 ? 'green' : 'yellow'}">1:${fmt(d.rr_ratio, 1)}</span>
    </div>
    <div class="risk-row">
      <span class="risk-row-label">Hesaba Katkı (%)</span>
      <span class="risk-row-val green">+%${fmt(d.profit_on_account)}</span>
    </div>
    <div class="risk-divider"></div>
  ` : '';

  $('riskResult').innerHTML = `
    <div class="risk-result-card">
      <div class="risk-highlight">
        <div class="risk-highlight-label">Alınacak Lot</div>
        <div class="risk-highlight-val">${fmtNum(d.shares)} adet</div>
      </div>
      <div class="risk-divider"></div>
      <div class="risk-row">
        <span class="risk-row-label">Max Risk (%${d.risk_pct})</span>
        <span class="risk-row-val red">${fmtTL(d.max_risk_tl)}</span>
      </div>
      <div class="risk-row">
        <span class="risk-row-label">Hisse Başı Risk</span>
        <span class="risk-row-val">${fmtTL(d.risk_per_share)}</span>
      </div>
      <div class="risk-row">
        <span class="risk-row-label">Toplam Yatırım</span>
        <span class="risk-row-val">${fmtTL(d.total_investment)}</span>
      </div>
      <div class="risk-row">
        <span class="risk-row-label">Hesap Kullanımı</span>
        <span class="risk-row-val ${d.investment_pct > 100 ? 'red' : d.investment_pct > 50 ? 'yellow' : 'green'}">%${fmt(d.investment_pct)}</span>
      </div>
      <div class="risk-divider"></div>
      ${profitRow}
      <div class="risk-row">
        <span class="risk-row-label">Gerçek Risk</span>
        <span class="risk-row-val red">${fmtTL(d.actual_risk)} (%${fmt(d.actual_risk_pct)})</span>
      </div>
    </div>
    ${warnings}
    ${d.rr_warning ? `<div class="risk-warning" style="margin-top:0.4rem">${d.rr_warning}</div>` : ''}
    ${d.rr_ok ? `<div class="risk-warning" style="margin-top:0.4rem;color:var(--green);background:var(--green-glow);border-color:var(--green)">${d.rr_ok}</div>` : ''}
  `;
}

function updateDailyLimit() {
  const account = parseFloat($('riskAccount').value) || 0;
  const loss    = parseFloat($('dailyLoss').value) || 0;
  if (!account) return;

  const limit   = account * 0.02;
  const used    = Math.abs(loss);
  const pct     = Math.min(100, (used / limit) * 100);
  const rem     = Math.max(0, limit - used);
  const stop    = used >= limit;

  const fillColor = stop ? 'var(--red)' : pct > 60 ? 'var(--yellow)' : 'var(--green)';

  $('dailyLimitResult').innerHTML = `
    <div class="daily-bar-wrap">
      <div class="daily-bar-track">
        <div class="daily-bar-fill" style="width:${pct}%;background:${fillColor}"></div>
      </div>
    </div>
    <div class="daily-limit-msg ${stop ? 'stop' : 'ok'}">
      ${stop
        ? '🔴 Günlük zarar limitine ulaştın! Bugün trade yapmayı bırak.'
        : `✅ Günlük limitin %${pct.toFixed(0)}'ini kullandın. Kalan: ${fmtTL(rem)}`
      }
    </div>
  `;
}

function prefillRisk(stockData) {
  if (!stockData) return;
  if (stockData.entry) $('riskEntry').value = fmt(stockData.entry);
  if (stockData.stop)  $('riskStop').value  = fmt(stockData.stop);
  if (stockData.target1) $('riskTarget').value = fmt(stockData.target1);
}

// ─── SEKME YÖNETİMİ ───────────────────────────────────────

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const btn = document.querySelector(`[data-tab="${tab}"]`);
  const content = $(`content${tab.charAt(0).toUpperCase() + tab.slice(1)}`);

  if (btn) btn.classList.add('active');
  if (content) content.classList.add('active');
}

// ─── CACHE TEMİZLE ────────────────────────────────────────

async function clearAndRefresh() {
  const btn = $('btnRefresh');
  btn.classList.add('spinning');

  try {
    await fetch('/api/clear-cache', { method: 'POST' });
    await runScan(state.universe);
    showToast('Veri yenilendi ✅', 'success');
  } catch (err) {
    showToast('Yenileme hatası: ' + err.message, 'error');
  } finally {
    btn.classList.remove('spinning');
  }
}

// ─── EVENT LISTENERS ─────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Evren seçici
  document.querySelectorAll('.univ-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.univ-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.universe = btn.dataset.value;
      runScan(state.universe);
    });
  });

  // Yenile butonu
  $('btnRefresh').addEventListener('click', clearAndRefresh);

  // Analiz butonu
  $('btnAnalyze').addEventListener('click', () => {
    loadAnalysis($('analyzeInput').value);
  });

  // Enter tuşu analiz
  $('analyzeInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') loadAnalysis($('analyzeInput').value);
  });

  // Hızlı seç butonları
  document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $('analyzeInput').value = btn.dataset.ticker;
      loadAnalysis(btn.dataset.ticker);
    });
  });

  // Karşılaştırma butonu
  $('btnCompare').addEventListener('click', runCompare);
  $('compareInput1').addEventListener('keydown', e => { if (e.key === 'Enter') runCompare(); });
  $('compareInput2').addEventListener('keydown', e => { if (e.key === 'Enter') runCompare(); });

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Risk hesaplayıcı
  $('btnCalcRisk').addEventListener('click', calcRisk);

  // Risk slider
  $('riskPct').addEventListener('input', (e) => {
    $('riskPctLabel').textContent = `%${parseFloat(e.target.value).toFixed(1)}`;
  });

  // Günlük zarar takibi
  $('dailyLoss').addEventListener('input', updateDailyLimit);
  $('riskAccount').addEventListener('input', updateDailyLimit);

  // Saat güncelle
  updateClock();
  setInterval(updateClock, 30000);

  // İlk taramayı başlat
  runScan(state.universe);
});
