document.addEventListener("DOMContentLoaded", () => {
    // Öneriler yükle
    fetch('/api/recommendations')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('rec-chips');
            container.innerHTML = '';
            if (data.status === 'success') {
                data.list.forEach(item => {
                    const chip = document.createElement('div');
                    chip.className = 'chip';
                    chip.innerHTML = `${item.ticker} <span style="color:var(--accent); font-size:0.85em;">⭐ ${item.score}</span>`;
                    chip.onclick = () => {
                        document.getElementById('tickerInput').value = item.ticker;
                        analyzeTicker();
                    };
                    container.appendChild(chip);
                });
            }
        })
        .catch(() => {
            document.getElementById('rec-chips').innerHTML = '<span class="chip-loading">Yüklenemedi.</span>';
        });

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

            // --- Pivot Seviyeleri ---
            document.getElementById('r2-val').innerText = `${data.r2.toFixed(2)} TL`;
            document.getElementById('r1-val').innerText = `${data.r1.toFixed(2)} TL`;
            document.getElementById('pp-val').innerText = `${data.pp.toFixed(2)} TL`;
            document.getElementById('s1-val').innerText = `${data.s1.toFixed(2)} TL`;
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
        { id: 'r2', val: r2 }, { id: 'r1', val: r1 },
        { id: 'pp', val: pp }, { id: 's1', val: s1 }, { id: 's2', val: s2 }
    ];
    levels.forEach(({ id }) => {
        document.querySelector(`.pivot-level.${id}`).style.opacity = '0.7';
    });

    // Fiyata en yakın seviyeyi parlat
    let closest = levels.reduce((a, b) => Math.abs(a.val - price) < Math.abs(b.val - price) ? a : b);
    document.querySelector(`.pivot-level.${closest.id}`).style.opacity = '1';
    document.querySelector(`.pivot-level.${closest.id}`).style.transform = 'scale(1.02)';
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
