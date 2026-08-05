/* ═══════════════════════════════════════════
   BIST Tarayıcı — Ana JavaScript
   ═══════════════════════════════════════════ */

'use strict';

// ──────────────────────────────────────
// Global Durum
// ──────────────────────────────────────
let allStocks   = [];     // Tüm taranan hisseler
let currentFilter = 'all';
const CHUNK = 15;         // Her istekte kaç hisse
let scanning  = false;

// ──────────────────────────────────────
// Tarama
// ──────────────────────────────────────
async function startScan() {
    if (scanning) return;
    scanning = true;

    const btn  = document.getElementById('scanBtn');
    const prog = document.getElementById('progress-wrap');
    const bar  = document.getElementById('progress-bar');
    const txt  = document.getElementById('progress-text');
    const res  = document.getElementById('results');
    const smry = document.getElementById('summary-bar');
    const flt  = document.getElementById('filters');

    // Reset
    allStocks = [];
    res.innerHTML = '';
    smry.style.display = 'none';
    flt.style.display = 'none';
    prog.style.display = 'flex';
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = 'Taranıyor...';

    let offset = 0;
    let total  = 134; // fallback

    try {
        while (true) {
            const url  = `/scan?offset=${offset}&limit=${CHUNK}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('Sunucu hatası');
            const json = await resp.json();

            total  = json.total || total;
            offset = json.next_offset;

            // Geçerli verileri ekle
            allStocks.push(...json.results);

            // Progress güncelle
            const pct = Math.min(100, Math.round(offset / total * 100));
            bar.style.width  = pct + '%';
            txt.textContent  = `Taranan: ${Math.min(offset, total)} / ${total}`;

            // Yeni gelenlerden geçenleri canlı olarak göster
            renderFiltered();

            if (json.done || offset >= total) break;
        }
    } catch (e) {
        txt.textContent = '⚠ Bağlantı hatası. Yeniden deneyin.';
        console.error(e);
    }

    // Tamamlandı
    bar.style.width = '100%';
    txt.textContent = `✅ Tarama tamamlandı — ${allStocks.length} hisse bulundu`;

    document.getElementById('scan-time').textContent =
        'Son tarama: ' + new Date().toLocaleTimeString('tr-TR');

    flt.style.display = 'flex';
    smry.style.display = 'flex';
    renderSummary();

    btn.querySelector('.btn-text').textContent = 'Yeniden Tara';
    btn.disabled = false;
    scanning = false;
}

// ──────────────────────────────────────
// Filtreleme
// ──────────────────────────────────────
function setFilter(f, el) {
    currentFilter = f;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    renderFiltered();
}

function passFilter(s) {
    if (currentFilter === 'all')        return true;
    if (currentFilter === 'support')    return ['near_s1','near_s2','between_s2_s1','below_pivot','below_s2'].includes(s.pivot_zone);
    if (currentFilter === 'pivot_above') return ['above_pivot','near_pivot','near_r1'].includes(s.pivot_zone);
    if (currentFilter === 'strong')     return s.sma_trend === 'strong_up';
    if (currentFilter === 'high_score') return s.score >= 6;
    return true;
}

function renderFiltered() {
    const visible = allStocks
        .filter(passFilter)
        .sort((a, b) => b.score - a.score || b.rvol - a.rvol);

    const res = document.getElementById('results');
    res.innerHTML = visible.length === 0
        ? ''
        : visible.map(renderCard).join('');

    document.getElementById('empty-state').style.display =
        (visible.length === 0 && allStocks.length > 0) ? 'block' : 'none';
}

function renderSummary() {
    const total   = allStocks.length;
    const support = allStocks.filter(s => passFilter({...s, _f: 'support'}) ||
        ['near_s1','near_s2','between_s2_s1','below_pivot'].includes(s.pivot_zone)).length;
    const high    = allStocks.filter(s => s.score >= 6).length;

    document.getElementById('sum-total').innerHTML   = `<b>${total}</b> hisse tarandı`;
    document.getElementById('sum-support').innerHTML = `<b>${support}</b> destek bölgesinde`;
    document.getElementById('sum-high').innerHTML    = `<b>${high}</b> skor ≥ 6`;
}

// ──────────────────────────────────────
// Kart render
// ──────────────────────────────────────
function renderCard(s) {
    const budget = parseFloat(document.getElementById('budgetInput').value) || 0;
    const slots  = parseInt(document.getElementById('slotInput').value)  || 5;
    const perSlot = budget > 0 ? budget / slots : 0;
    const lots    = (perSlot > 0 && s.price > 0)
        ? Math.floor(perSlot / s.price)
        : null;
    const lotCost = lots ? (lots * s.price).toLocaleString('tr-TR', {maximumFractionDigits:0}) : null;

    // Skor rengi
    const scorePct  = (s.score / s.score_max) * 100;
    const scoreColor = s.score >= 7 ? '#00e599'
        : s.score >= 5 ? '#f6c90e'
        : s.score >= 3 ? '#f6853a'
        : '#ff4d6d';

    // Pivot bar hesabı
    const pBar = buildPivotBar(s);

    // SMA trend rozeti
    const trendBadge = {
        'strong_up':   '<span class="badge badge-green">⬆ Güçlü Trend</span>',
        'up':          '<span class="badge badge-blue">↑ Trend Yukarı</span>',
        'down':        '<span class="badge badge-red">↓ Trend Aşağı</span>',
        'strong_down': '<span class="badge badge-red">⬇ Güçlü Düşüş</span>',
    }[s.sma_trend] || '';

    // RSI rozeti
    const rsiBadge = s.rsi != null
        ? `<span class="badge ${s.rsi >= 40 && s.rsi <= 65 ? 'badge-green' : s.rsi < 40 ? 'badge-yellow' : 'badge-red'}">RSI ${s.rsi}</span>`
        : '';

    // MACD rozeti
    const macdBadge = s.macd_bull
        ? '<span class="badge badge-blue">MACD ↑</span>'
        : '<span class="badge badge-red">MACD ↓</span>';

    // ADX rozeti
    const adxBadge = s.adx != null
        ? `<span class="badge ${s.adx >= 25 ? 'badge-purple' : s.adx >= 20 ? 'badge-blue' : 'badge-neutral'}">ADX ${s.adx}</span>`
        : '';

    // ATR% rozeti
    const atrBadge = s.atr_pct != null
        ? `<span class="badge badge-neutral">ATR ${s.atr_pct}%</span>`
        : '';

    // Rel. Hacim
    const rvolBadge = s.rvol != null
        ? `<span class="badge ${s.rvol >= 1.5 ? 'badge-green' : s.rvol >= 1.3 ? 'badge-blue' : 'badge-neutral'}">Hacim ${s.rvol}x</span>`
        : '';

    // 5G Momentum
    const momBadge = s.mom_5d != null
        ? `<span class="badge ${s.mom_5d >= 2 && s.mom_5d <= 15 ? 'badge-green' : s.mom_5d > 15 ? 'badge-red' : 'badge-neutral'}">5G: ${s.mom_5d > 0 ? '+' : ''}${s.mom_5d}%</span>`
        : '';

    // BB rozeti
    const bbBadge = s.bb_pct != null
        ? `<span class="badge badge-neutral">BB: ${s.bb_pct}%</span>`
        : '';

    // Lot bilgisi
    const lotInfo = lots
        ? `Her pozisyona <b>${perSlot.toLocaleString('tr-TR',{maximumFractionDigits:0})} TL</b> → <b>${lots} lot</b> × ${s.price} TL = ${lotCost} TL`
        : '<span style="color:var(--text-muted)">Bütçe girin → lot hesabı görünsün</span>';

    return `
<div class="card">
    <div class="card-header">
        <div>
            <div class="ticker">${s.ticker}</div>
            <div style="font-size:0.78rem; color:var(--text-muted); margin-top:2px;">
                Stop: <b style="color:var(--red)">${s.stop} TL</b>
                &nbsp;·&nbsp;
                Hedef: <b style="color:var(--green)">${s.target} TL</b>
            </div>
        </div>
        <div style="text-align:right;">
            <div class="price">${s.price.toLocaleString('tr-TR')} TL</div>
            <div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">
                Mevcut fiyat
            </div>
        </div>
    </div>

    <!-- Skor Barı -->
    <div class="score-row">
        <span class="score-label">Skor</span>
        <div class="score-track">
            <div class="score-fill" style="width:${scorePct}%; background:${scoreColor};"></div>
        </div>
        <span class="score-num" style="color:${scoreColor}">${s.score}/${s.score_max}</span>
    </div>

    <!-- Pivot Bar -->
    <div class="pivot-section">
        <div class="pivot-title">Pivot Seviyeleri</div>
        ${pBar.html}
        <div class="pivot-labels">
            <span>S2 ${s.s2}</span>
            <span>S1 ${s.s1}</span>
            <span style="color:var(--blue)">P ${s.pivot}</span>
            <span>R1 ${s.r1}</span>
            <span>R2 ${s.r2}</span>
        </div>
        ${pBar.badge}
    </div>

    <!-- Stop / Hedef Kutucukları -->
    <div class="trade-row">
        <div class="trade-box stop">
            <div class="trade-box-label">🛑 STOP</div>
            <div class="trade-box-price">${s.stop} TL</div>
            <div class="trade-box-pct">-%2.0</div>
        </div>
        <div class="trade-box target">
            <div class="trade-box-label">🎯 HEDEF</div>
            <div class="trade-box-price">${s.target} TL</div>
            <div class="trade-box-pct">+%4.0</div>
        </div>
    </div>

    <!-- İndikatör Rozetleri -->
    <div class="badges">
        ${trendBadge}
        ${rsiBadge}
        ${macdBadge}
        ${adxBadge}
        ${atrBadge}
        ${rvolBadge}
        ${momBadge}
        ${bbBadge}
    </div>

    <!-- Lot Hesabı -->
    <div class="lot-row">
        📦 ${lotInfo}
    </div>
</div>`;
}

// ──────────────────────────────────────
// Pivot Bar Görselleştirme
// ──────────────────────────────────────
function buildPivotBar(s) {
    const { price, s2, s1, pivot, r1, r2 } = s;

    // Ekranın kapsayacağı aralık: S2'nin %10 altından R2'nin %10 üstüne
    const rangeMin = s2 * 0.92;
    const rangeMax = r2 * 1.08;
    const range    = rangeMax - rangeMin;
    if (range <= 0) return { html: '', badge: '' };

    const pct = v => Math.max(0, Math.min(100, ((v - rangeMin) / range) * 100)).toFixed(1);

    // Zone arka plan renkleri
    const zoneColors = [
        { from: pct(s2), to: pct(s1),    bg: 'rgba(0,229,153,0.2)'  },  // S2-S1 destek
        { from: pct(s1), to: pct(pivot),  bg: 'rgba(0,229,153,0.1)'  },  // S1-P zayıf destek
        { from: pct(pivot), to: pct(r1),  bg: 'rgba(79,142,247,0.1)' },  // P-R1 nötr
        { from: pct(r1), to: pct(r2),     bg: 'rgba(255,77,109,0.1)' },  // R1-R2 direnç
    ];

    const fills = zoneColors.map(z =>
        `<div class="pivot-zone-fill" style="left:${z.from}%; width:${Math.max(0,z.to-z.from)}%; background:${z.bg};"></div>`
    ).join('');

    const markers = [
        { v: s2,    color: '#00e599' },
        { v: s1,    color: '#00e599' },
        { v: pivot, color: '#4f8ef7' },
        { v: r1,    color: '#ff4d6d' },
        { v: r2,    color: '#ff4d6d' },
    ].map(m =>
        `<div class="pivot-marker" style="left:${pct(m.v)}%; background:${m.color}; opacity:0.7;"></div>`
    ).join('');

    const needle = `<div class="pivot-price-needle" style="left:${pct(price)}%;"></div>`;

    const html = `<div class="pivot-bar">${fills}${markers}${needle}</div>`;

    // Zone rozeti
    const zoneInfo = {
        'near_s2':        { label: '🟢 S2 Desteğinde',    cls: 'badge-green'  },
        'near_s1':        { label: '🟢 S1 Desteğinde',    cls: 'badge-green'  },
        'between_s2_s1':  { label: '🟡 S2–S1 Arası',      cls: 'badge-yellow' },
        'below_s2':       { label: '🔴 S2 Altında',        cls: 'badge-red'    },
        'below_pivot':    { label: '🟡 Pivot Altı Destek', cls: 'badge-yellow' },
        'near_pivot':     { label: '🔵 Pivot Yakını',      cls: 'badge-blue'   },
        'above_pivot':    { label: '✅ Pivot Üstü',        cls: 'badge-blue'   },
        'near_r1':        { label: '🔴 R1 Dirençte',       cls: 'badge-red'    },
        'above_r1':       { label: '🔴 Direnç Üstü',      cls: 'badge-red'    },
        'above_r2':       { label: '🔴 R2 Üstü (Aşırı)',  cls: 'badge-red'    },
    }[s.pivot_zone] || { label: s.pivot_zone, cls: 'badge-neutral' };

    const badge = `<span class="pivot-zone-badge badge ${zoneInfo.cls}">${zoneInfo.label}</span>`;

    return { html, badge };
}

// ──────────────────────────────────────
// Lot Güncelle (bütçe değişince)
// ──────────────────────────────────────
function updateLots() {
    if (allStocks.length > 0) renderFiltered();
}
