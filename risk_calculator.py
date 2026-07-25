"""
Risk ve Pozisyon Büyüklüğü Hesaplayıcı
Andrew Aziz Ch.7: "2% Kuralı" — tek işlemde max sermayenin %2'si riske atılır.
"""


def calculate_position(
    account_size: float,
    entry_price: float,
    stop_price: float,
    risk_pct: float = 2.0
) -> dict:
    """
    Pozisyon büyüklüğü hesapla.
    
    Args:
        account_size: Toplam hesap büyüklüğü (TL)
        entry_price:  Giriş fiyatı (TL)
        stop_price:   Stop-loss fiyatı (TL)
        risk_pct:     Riske atılacak sermaye yüzdesi (varsayılan %2)
    
    Returns:
        Pozisyon büyüklüğü ve risk metrikleri
    """
    if account_size <= 0 or entry_price <= 0 or stop_price <= 0:
        return _error_result("Geçersiz değerler girildi.")

    if stop_price >= entry_price:
        return _error_result("Stop fiyatı giriş fiyatından yüksek olamaz.")

    # Max riske atılacak TL
    max_risk_tl = account_size * (risk_pct / 100)

    # Hisse başına risk
    risk_per_share = entry_price - stop_price

    if risk_per_share <= 0:
        return _error_result("Stop fiyatı giriş fiyatından düşük olmalı.")

    # Alınacak lot sayısı
    shares = int(max_risk_tl / risk_per_share)
    shares = max(0, shares)

    # KRİTİK SINIRLAMA: Toplam yatırım hesap büyüklüğünü geçemez!
    # (Stop çok yakın olduğunda lot sayısı patlamasını önler)
    max_affordable = int(account_size / entry_price)
    if shares > max_affordable:
        shares = max_affordable

    # Toplam yatırım
    total_investment = shares * entry_price

    # Gerçek risk (hepsi stop'a giderse)
    actual_risk = shares * risk_per_share
    actual_risk_pct = (actual_risk / account_size) * 100 if account_size > 0 else 0

    # Hesap büyüklüğüne oranı
    investment_pct = (total_investment / account_size) * 100 if account_size > 0 else 0

    # Uyarılar
    warnings = []
    if investment_pct > 50:
        warnings.append(f"Hesabınızın %{investment_pct:.0f}'ini tek hisseye koymak riskli. Çeşitlendirmeyi düşün.")



    if shares == 0:
        warnings.append("Hesap büyüklüğünüz bu stop mesafesi için çok küçük. Daha az lot deneyin.")

    return {
        'error': False,
        'account_size':      round(account_size, 2),
        'risk_pct':          risk_pct,
        'max_risk_tl':       round(max_risk_tl, 2),
        'entry_price':       round(entry_price, 2),
        'stop_price':        round(stop_price, 2),
        'risk_per_share':    round(risk_per_share, 2),
        'shares':            shares,
        'total_investment':  round(total_investment, 2),
        'actual_risk':       round(actual_risk, 2),
        'actual_risk_pct':   round(actual_risk_pct, 2),
        'investment_pct':    round(investment_pct, 2),
        'warnings':          warnings,
    }


def calculate_with_target(
    account_size: float,
    entry_price: float,
    stop_price: float,
    target_price: float,
    risk_pct: float = 2.0
) -> dict:
    """
    Hedef fiyatla birlikte hesapla — potansiyel kazancı göster.
    """
    result = calculate_position(account_size, entry_price, stop_price, risk_pct)

    if result.get('error'):
        return result

    if target_price <= entry_price:
        result['target_warnings'] = ["Hedef fiyat giriş fiyatından yüksek olmalı."]
        return result

    shares = result['shares']
    reward_per_share = target_price - entry_price
    potential_profit = shares * reward_per_share
    rr_ratio = reward_per_share / result['risk_per_share'] if result['risk_per_share'] > 0 else 0

    result['target_price']     = round(target_price, 2)
    result['reward_per_share'] = round(reward_per_share, 2)
    result['potential_profit']  = round(potential_profit, 2)
    result['rr_ratio']          = round(rr_ratio, 2)
    result['profit_on_account'] = round((potential_profit / account_size) * 100, 2)

    # R/R uyarısı
    if rr_ratio < 1.5:
        result['rr_warning'] = f"R/R oranı {rr_ratio:.1f} çok düşük. En az 1:2 önerilir."
    elif rr_ratio >= 2.0:
        result['rr_ok'] = f"R/R oranı 1:{rr_ratio:.1f} — İyi!"

    return result


def daily_loss_limit(account_size: float, current_loss: float) -> dict:
    """
    Günlük zarar limiti kontrolü.
    Andrew Aziz: Günlük %2 kayıptan sonra trade'i bırak.
    """
    daily_limit = account_size * 0.02
    remaining   = max(0, daily_limit - abs(current_loss))
    pct_used    = (abs(current_loss) / daily_limit) * 100 if daily_limit > 0 else 0

    should_stop = abs(current_loss) >= daily_limit

    return {
        'account_size':  account_size,
        'daily_limit':   round(daily_limit, 2),
        'current_loss':  round(current_loss, 2),
        'remaining':     round(remaining, 2),
        'pct_used':      round(pct_used, 2),
        'should_stop':   should_stop,
        'message': (
            "🔴 Günlük zarar limitine ulaştın! Bugünkü trade'leri durdur." if should_stop
            else f"✅ Günlük limitin %{pct_used:.0f}'ini kullandın. Kalan: {remaining:,.0f} TL"
        )
    }


def _error_result(message: str) -> dict:
    return {
        'error': True,
        'message': message,
    }
