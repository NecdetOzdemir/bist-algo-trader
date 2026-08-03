document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('tickerInput').addEventListener('keypress', e => {
        if (e.key === 'Enter') analyzeTicker();
    });
});

function analyzeTicker() {
    const ticker = document.getElementById('tickerInput').value.trim().toUpperCase();
    if (!ticker) return;

    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('shakeout-panel').classList.add('hidden');

    fetch(`/api/analyze/${ticker}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('loading').classList.add('hidden');

            if (data.error) {
                alert('⚠️ ' + data.error);
                return;
            }

            // --- Üst Kart ---
            document.getElementById('tic-name').innerText = data.ticker;
            document.getElementById('price-tag').innerText = `${data.price.toFixed(2)} TL`;
            document.getElementById('date-tag').innerText = data.date + ' verisi';
            document.getElementById('action-comment').innerText = data.comment;

            const actionEl = document.getElementById('action-text');
            actionEl.innerText = data.action;
            actionEl.style.color = data.color;

            // Score animasyonu
            animateValue('score-value', 0, data.score, 900);
            const circle = document.querySelector('.score-circle');
            circle.style.borderColor = data.color;
            circle.style.boxShadow = `0 0 24px ${data.color}40`;

            // --- Shakeout Paneli ---
            if (data.shakeout_signal) {
                document.getElementById('shakeout-title').innerText = data.shakeout_signal;
                document.getElementById('shakeout-comment').innerText = data.shakeout_comment;
                const panel = document.getElementById('shakeout-panel');
                panel.classList.remove('hidden');

                // Renk: Shakeout = sarı, Gerçek Baskı = kırmızı
                if (data.shakeout_signal.includes('SHAKEOUT')) {
                    panel.style.borderLeftColor = '#ffd700';
                } else if (data.shakeout_signal.includes('GERÇEK')) {
                    panel.style.borderLeftColor = '#ff3366';
                } else {
                    panel.style.borderLeftColor = '#ff7b00';
                }
            }
            
            // --- SMC (Akıllı Para) Paneli ---
            if (data.smc_comments && data.smc_comments.length > 0) {
                const smcPanel = document.getElementById('smc-panel');
                const smcList = document.getElementById('smc-list');
                smcList.innerHTML = ''; // Temizle
                
                data.smc_comments.forEach(comment => {
                    const li = document.createElement('li');
                    li.innerText = comment;
                    smcList.appendChild(li);
                });
                
                smcPanel.classList.remove('hidden');
            } else {
                document.getElementById('smc-panel').classList.add('hidden');
            }

            // --- Pivot Seviyeleri ---
            document.getElementById('r2-val').innerText = `${data.r2.toFixed(2)} TL`;
            if (data.cam_h3) document.getElementById('camh3-val').innerText = `${data.cam_h3.toFixed(2)} TL`;
            document.getElementById('r1-val').innerText = `${data.r1.toFixed(2)} TL`;
            document.getElementById('pp-val').innerText = `${data.pp.toFixed(2)} TL`;
            document.getElementById('s1-val').innerText = `${data.s1.toFixed(2)} TL`;
            if (data.cam_l3) document.getElementById('caml3-val').innerText = `${data.cam_l3.toFixed(2)} TL`;
            document.getElementById('s2-val').innerText = `${data.s2.toFixed(2)} TL`;

            // Mevcut fiyatı pivot haritasına göre işaretle
            highlightPivot(data.price, data.r2, data.r1, data.pp, data.s1, data.s2);

            // --- Trading Planı ---
            document.getElementById('entry-val').innerText = `${data.entry.toFixed(2)} TL`;
            document.getElementById('tp-val').innerText = `${data.take_profit.toFixed(2)} TL`;
            document.getElementById('sl-val').innerText = `${data.stop_loss.toFixed(2)} TL`;
            document.getElementById('gain-pct').innerText = `+%${data.gain_pct.toFixed(2)}`;
            document.getElementById('loss-pct').innerText = `-%${data.loss_pct.toFixed(2)}`;
            document.getElementById('rr-val').innerText = `1:${data.rr_ratio.toFixed(2)}`;

            // RR rengini güncelle
            const rrVal = document.getElementById('rr-val');
            rrVal.style.color = data.rr_ratio >= 1.5 ? 'var(--green)' : data.rr_ratio >= 1.0 ? 'var(--yellow)' : 'var(--red)';

            // --- Teknik Göstergeler ---
            const rsiEl = document.getElementById('rsi-val');
            rsiEl.innerText = data.rsi;
            rsiEl.style.color = data.rsi < 30 ? 'var(--green)' : data.rsi > 70 ? 'var(--red)' : 'var(--text-main)';

            document.getElementById('macd-val').innerText = data.macd > 0 ? `+${data.macd}` : data.macd;
            document.getElementById('mfi-val').innerText = data.mfi;
            document.getElementById('vol-val').innerText = `${(data.rel_volume * 100).toFixed(0)}%`;
            document.getElementById('atr-val').innerText = `${data.atr.toFixed(2)} TL`;

            document.getElementById('result-section').classList.remove('hidden');
        })
        .catch(err => {
            document.getElementById('loading').classList.add('hidden');
            alert('Sunucuya bağlanılamadı.');
            console.error(err);
        });
}

function highlightPivot(price, r2, r1, pp, s1, s2) {
    const levels = [
        { id: 'r2-val', val: r2 }, { id: 'r1-val', val: r1 },
        { id: 'pp-val', val: pp }, { id: 's1-val', val: s1 }, { id: 's2-val', val: s2 }
    ];
    levels.forEach(({ id }) => {
        let el = document.getElementById(id);
        if(el) {
            el.parentNode.style.opacity = '0.7';
            el.parentNode.style.border = '';
        }
    });

    // Fiyata en yakın seviyeyi parlat
    let closest = levels.reduce((a, b) => Math.abs(a.val - price) < Math.abs(b.val - price) ? a : b);
    let closestEl = document.getElementById(closest.id).parentNode;
    closestEl.style.opacity = '1';
    closestEl.style.transform = 'scale(1.02)';
    closestEl.style.border = '1px solid var(--accent)';
}

function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    const range = end - start;
    const stepTime = Math.max(10, Math.floor(duration / 100));
    let current = start;
    const step = range / (duration / stepTime);

    const timer = setInterval(() => {
        current += step;
        if ((step > 0 && current >= end) || (step < 0 && current <= end)) {
            obj.innerText = Math.round(end);
            clearInterval(timer);
        } else {
            obj.innerText = Math.round(current);
        }
    }, stepTime);
}

async function fetchAllChunks(progressBtn, totalTickers = 100) {
    let allResults = [];
    let limit = 10; // Her istekte 10 hisse tara (Render timeout'a girmesin diye)
    
    for (let start = 0; start < totalTickers; start += limit) {
        progressBtn.innerHTML = `⏳ Taranıyor (${start} / ${totalTickers})... Lütfen bekleyin.`;
        try {
            let res = await fetch(`/api/scan_chunk?start=${start}&limit=${limit}`);
            if (!res.ok) throw new Error('Sunucu hatası');
            let data = await res.json();
            if (data.results) {
                allResults.push(...data.results);
            }
        } catch (e) {
            console.error("Parça tarama hatası:", e);
        }
    }
    return allResults;
}

async function scanOpportunities() {
    const btn = document.getElementById('scanBtn');
    const resultsPanel = document.getElementById('scanner-results');
    const list = document.getElementById('scanner-list');
    
    btn.disabled = true;
    resultsPanel.classList.add('hidden');
    list.innerHTML = '';

    try {
        let allData = await fetchAllChunks(btn);
        
        // Fırsat Filtresi (RSI < 40, Score > 55, Düşüş > -%5)
        let data = allData.filter(d => {
            let rsi = d.rsi || 100;
            let score = d.score || 0;
            let ret = d.return_1d || 0;
            return rsi > 20 && rsi < 40 && score > 55 && ret > -0.05;
        });
        
        // Puanlara göre sırala
        data.sort((a, b) => (b.score || 0) - (a.score || 0));
        if (data.length === 0) {
            list.innerHTML = '<p style="text-align:center; color:#a0aec0;">Şu an için (RSI < 35 ve Yüksek AI Puanı) şartlarını sağlayan hisse bulunamadı.</p>';
        } else {
            data.forEach(stock => {
                const item = document.createElement('div');
                item.className = 'scanner-item';
                item.onclick = () => {
                    document.getElementById('tickerInput').value = stock.ticker;
                    analyzeTicker();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                };
                
                item.innerHTML = `
                    <div>
                        <div class="scanner-tic">${stock.ticker}</div>
                        <div class="scanner-details">Fiyat: ${stock.price} TL | RSI: ${stock.rsi}</div>
                    </div>
                    <div style="text-align:right">
                        <div class="scanner-score">${stock.score} Puan</div>
                        <div class="scanner-details">Hedef: ${stock.take_profit.toFixed(2)} TL</div>
                    </div>
                `;
                list.appendChild(item);
            });
        }
        resultsPanel.classList.remove('hidden');
    } catch (err) {
        alert('Tarama sırasında hata oluştu.');
        console.error(err);
    } finally {
        btn.innerHTML = '🎯 BIST 100 Fırsat Tarayıcı';
        btn.disabled = false;
    }
}

async function scanTopScores() {
    const topBtn = document.getElementById('topBtn');
    const scanBtn = document.getElementById('scanBtn');
    const resultsPanel = document.getElementById('scanner-results');
    const list = document.getElementById('scanner-list');
    
    topBtn.disabled = true;
    scanBtn.disabled = true;
    resultsPanel.classList.add('hidden');
    list.innerHTML = '';

    try {
        let allData = await fetchAllChunks(topBtn);
        
        // En iyiler filtresi (Score > 55)
        let data = allData.filter(d => (d.score || 0) > 55);
        
        // Puanlara göre sırala ve ilk 10'u al
        data.sort((a, b) => (b.score || 0) - (a.score || 0));
        data = data.slice(0, 10);

        topBtn.innerHTML = '🔥 Günün En İyileri';
        topBtn.disabled = false;
        scanBtn.disabled = false;
        
        document.querySelector('#scanner-results h3').innerText = '🔥 Günün En Yüksek Puanlı Hisseleri (Kısıtlamasız)';
        
        if (data.length === 0) {
            list.innerHTML = '<p style="text-align:center; color:#a0aec0;">Şu an için 55 puanı geçen hisse bulunamadı.</p>';
        } else {
            data.forEach(stock => {
                const item = document.createElement('div');
                item.className = 'scanner-item';
                item.onclick = () => {
                    document.getElementById('tickerInput').value = stock.ticker;
                    analyzeTicker();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                };
                
                item.innerHTML = `
                    <div>
                        <div class="scanner-tic">${stock.ticker}</div>
                        <div class="scanner-details">Fiyat: ${stock.price} TL | Günlük: ${stock.return_1d > 0 ? '+' : ''}${(stock.return_1d * 100).toFixed(1)}%</div>
                    </div>
                    <div style="text-align:right">
                        <div class="scanner-score" style="color:var(--red)">${stock.score} Puan</div>
                        <div class="scanner-details">RSI: ${stock.rsi}</div>
                    </div>
                `;
                list.appendChild(item);
            });
        }
        resultsPanel.classList.remove('hidden');
    } catch (err) {
        alert('Tarama sırasında hata oluştu.');
        console.error(err);
    } finally {
        topBtn.innerHTML = '🔥 Günün En İyileri';
        topBtn.disabled = false;
        scanBtn.disabled = false;
    }
}

// ========================
// ☀️ SABAH PLANI (KUANTUM)
// ========================

let morningStocks = [];

function trendBadge(trend) {
    if (trend === 'strong_up') return '<span style="background:#00ffa322;color:#00ffa3;padding:2px 8px;border-radius:20px;font-size:0.75rem;">📈 Güçlü Trend</span>';
    if (trend === 'up')        return '<span style="background:#00d2ff22;color:#00d2ff;padding:2px 8px;border-radius:20px;font-size:0.75rem;">↗️ Yükselen Trend</span>';
    return '<span style="background:#ff4a6e22;color:#ff4a6e;padding:2px 8px;border-radius:20px;font-size:0.75rem;">↘️ Düşen Trend</span>';
}

function compBadge(comp) {
    const color = comp >= 8 ? '#00ffa3' : comp >= 6 ? '#ffd200' : comp >= 4 ? '#ff7b00' : '#ff4a6e';
    return `<span style="background:${color}22;color:${color};padding:2px 8px;border-radius:20px;font-size:0.75rem;font-weight:700;">${comp}/10 Komp.</span>`;
}

async function scanMorningPlan() {
    const btn   = document.getElementById('morningBtn');
    const panel = document.getElementById('morning-panel');
    const list  = document.getElementById('morning-list');
    btn.disabled = true;
    panel.classList.remove('hidden');
    list.innerHTML = '<p style="color:#a0aec0;text-align:center;">Taranıyor, lütfen bekleyin...</p>';
    try {
        let allData = await fetchAllChunks(btn);

        // Filtre: SMA50 üzerinde + Composite Score >= 5 + EV pozitif
        let filtered = allData.filter(d =>
            (d.sma_trend === 'strong_up' || d.sma_trend === 'up') &&
            (d.composite_score || 0) >= 5 &&
            (d.ev_pct || 0) > 0
        );
        // Composite Score'a göre sırala, eşit olunca EV'ye bak
        filtered.sort((a, b) => {
            if ((b.composite_score || 0) !== (a.composite_score || 0))
                return (b.composite_score || 0) - (a.composite_score || 0);
            return (b.ev_pct || 0) - (a.ev_pct || 0);
        });
        morningStocks = filtered.slice(0, 10);

        if (morningStocks.length === 0) {
            list.innerHTML = '<p style="color:#a0aec0;text-align:center;">Bugün kriterleri karşılayan hisse bulunamadı. (SMA Trend ↑ + Comp ≥5 + EV>0)</p>';
            return;
        }
        renderMorningList();
    } catch (err) {
        list.innerHTML = '<p style="color:#ff4a6e;text-align:center;">Tarama sırasında hata oluştu.</p>';
        console.error(err);
    } finally {
        btn.innerHTML = '☀️ Sabah Planım';
        btn.disabled = false;
    }
}

function renderMorningList() {
    const list     = document.getElementById('morning-list');
    const budget   = parseFloat(document.getElementById('budgetInput').value) || 0;
    const n        = morningStocks.length;

    document.getElementById('budget-info').innerText = budget > 0
        ? `→ ${n} pozisyon | Her biri: ${Math.floor(budget/n).toLocaleString('tr-TR')} TL`
        : '';

    list.innerHTML = '';
    morningStocks.forEach((s, i) => {
        const perStock = budget > 0 ? Math.floor(budget / n) : 0;
        // Kelly önerisi (budget varsa)
        const kellyTL  = budget > 0 ? Math.round(budget * (s.kelly_half || 0) / 100) : 0;
        const lots     = perStock > 0 && s.price > 0 ? Math.floor(perStock / s.price) : null;
        const evColor  = (s.ev_pct || 0) > 0 ? '#00ffa3' : '#ff4a6e';
        const evSign   = (s.ev_pct || 0) > 0 ? '+' : '';

        const card = document.createElement('div');
        card.style.cssText = 'background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:14px;padding:16px;margin-bottom:12px;cursor:pointer;transition:all 0.2s;';
        card.onmouseenter = () => card.style.background = 'rgba(255,255,255,0.09)';
        card.onmouseleave = () => card.style.background = 'rgba(255,255,255,0.05)';
        card.onclick = () => { document.getElementById('tickerInput').value = s.ticker; analyzeTicker(); window.scrollTo({ top: 0, behavior: 'smooth' }); };

        card.innerHTML = `
            <!-- Başlık satırı -->
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
                <div>
                    <span style="font-size:1.15rem;font-weight:800;color:#fff;">${i+1}. ${s.ticker}</span>
                    &nbsp;${trendBadge(s.sma_trend)}&nbsp;${compBadge(s.composite_score || 0)}
                    <div style="color:#a0aec0;font-size:0.8rem;margin-top:5px;">
                        Fiyat: <b style="color:#fff;">${s.price} TL</b>
                        &nbsp;·&nbsp; SMA50: <b>${s.sma50} TL</b>
                        &nbsp;·&nbsp; SMA200: <b>${s.sma200} TL</b>
                    </div>
                    ${lots !== null ? `<div style="color:#ffd200;font-size:0.8rem;margin-top:3px;">Eşit bölüm → ~${lots} lot &nbsp;|&nbsp; Kelly önerisi → ${kellyTL.toLocaleString('tr-TR')} TL</div>` : ''}
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.72rem;color:#a0aec0;">EV (Beklenen Değer)</div>
                    <div style="font-size:1.2rem;font-weight:800;color:${evColor};">${evSign}${(s.ev_pct || 0).toFixed(2)}%</div>
                    <div style="font-size:0.7rem;color:#a0aec0;margin-top:2px;">Kazanma ~%${s.win_rate_est || 50}</div>
                </div>
            </div>
            <!-- Stop / Hedef satırı (ATR bazlı) -->
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <div style="flex:1;background:rgba(0,255,163,0.08);border:1px solid rgba(0,255,163,0.2);border-radius:10px;padding:10px;text-align:center;">
                    <div style="font-size:0.7rem;color:#a0aec0;">✅ HEDEF (ATR×3)</div>
                    <div style="font-size:1rem;font-weight:700;color:#00ffa3;">${s.atr_tp} TL</div>
                    <div style="font-size:0.72rem;color:#00ffa3;">+%${(s.atr_tp_pct || 0).toFixed(1)}</div>
                </div>
                <div style="flex:1;background:rgba(255,74,110,0.08);border:1px solid rgba(255,74,110,0.2);border-radius:10px;padding:10px;text-align:center;">
                    <div style="font-size:0.7rem;color:#a0aec0;">🛑 STOP (ATR×1.5)</div>
                    <div style="font-size:1rem;font-weight:700;color:#ff4a6e;">${s.atr_stop} TL</div>
                    <div style="font-size:0.72rem;color:#ff4a6e;">-%${(s.atr_stop_pct || 0).toFixed(1)}</div>
                </div>
                <div style="flex:1;background:rgba(255,210,0,0.06);border:1px solid rgba(255,210,0,0.18);border-radius:10px;padding:10px;text-align:center;">
                    <div style="font-size:0.7rem;color:#a0aec0;">⚖️ RR / KELLY</div>
                    <div style="font-size:1rem;font-weight:700;color:#ffd200;">1:2</div>
                    <div style="font-size:0.72rem;color:#ffd200;">%${(s.kelly_half || 0).toFixed(1)} Kelly</div>
                </div>
            </div>`;
        list.appendChild(card);
    });
}

function recalcBudget() { if (morningStocks.length > 0) renderMorningList(); }
