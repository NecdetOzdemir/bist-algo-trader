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

function scanOpportunities() {
    const btn = document.getElementById('scanBtn');
    const resultsPanel = document.getElementById('scanner-results');
    const list = document.getElementById('scanner-list');
    
    // UI Yükleniyor Durumu
    btn.innerHTML = '⏳ Taranıyor (100 Hisse)... Lütfen bekleyin.';
    btn.disabled = true;
    resultsPanel.classList.add('hidden');
    list.innerHTML = '';

    fetch('/api/scan')
        .then(response => {
            if (response.status === 503) {
                return response.json().then(data => { throw new Error(data.message || 'Tarama yapılıyor...'); });
            }
            return response.json();
        })
        .then(data => {
            btn.innerHTML = '🎯 BIST 100 Fırsat Tarayıcı';
            btn.disabled = false;
            
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
        })
        .catch(err => {
            btn.innerHTML = '🎯 BIST 100 Fırsat Tarayıcı';
            btn.disabled = false;
            
            // Eğer hata 503 kaynaklıysa (arka plan botu çalışıyorsa) kullanıcıya kibarca bildir
            if (err.message && err.message.includes('tarama')) {
                alert('⏳ ' + err.message);
            } else {
                alert('Tarama sırasında sunucu hatası oluştu.');
                console.error(err);
            }
        });
}

function scanTopScores() {
    const topBtn = document.getElementById('topBtn');
    const scanBtn = document.getElementById('scanBtn');
    const resultsPanel = document.getElementById('scanner-results');
    const list = document.getElementById('scanner-list');
    
    // UI Yükleniyor Durumu
    topBtn.innerHTML = '🔥 Taranıyor... Lütfen bekleyin.';
    topBtn.disabled = true;
    scanBtn.disabled = true;
    resultsPanel.classList.add('hidden');
    list.innerHTML = '';

    fetch('/api/top_scores')
        .then(response => {
            if (response.status === 503) {
                return response.json().then(data => { throw new Error(data.message || 'Tarama yapılıyor...'); });
            }
            return response.json();
        })
        .then(data => {
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
        })
        .catch(err => {
            topBtn.innerHTML = '🔥 Günün En İyileri';
            topBtn.disabled = false;
            scanBtn.disabled = false;
            
            if (err.message && err.message.includes('tarama')) {
                alert('⏳ ' + err.message);
            } else {
                alert('Tarama sırasında hata oluştu.');
                console.error(err);
            }
        });
}
