"""Builds the actual post text for each platform from a signal + hook.

Each platform has different constraints (Twitter's length limit, IG's
hashtag culture, Telegram's HTML formatting) so captions are built per
platform rather than reusing one blob of text everywhere. Body text
follows `config.SOCIAL_LANGUAGE` (Urdu by default); hashtags stay in
English/Roman script since that's how they're actually searched and
used even by Urdu-speaking trading audiences.
"""
from social import config
from social.hooks import generate_hook, generate_cta

HASHTAGS = (
    "#Gold #XAUUSD #GoldTrading #ForexSignals #Forex #TradingSignals "
    "#GoldPrice #Investing #Trader #DayTrading"
)


def _signal_lines(signal, lang):
    direction = signal['direction']
    if lang == 'ur':
        if direction == 'NEUTRAL':
            return f"📊 XAUUSD: فی الحال کوئی ٹریڈ نہیں — تصدیق کا انتظار\nاعتماد: {signal['confidence']}%"
        t = signal['targets']
        direction_ur = 'خریداری (BUY)' if direction == 'BUY' else 'فروخت (SELL)'
        return (
            f"📈 سمت: {direction_ur}\n"
            f"💪 اعتماد: {signal['confidence']}%\n\n"
            f"💰 انٹری: ${t['entry']:.2f}\n"
            f"🛑 اسٹاپ لاس: ${t['stop_loss']:.2f}\n"
            f"🎯 ٹارگٹ 1: ${t['tp1']:.2f}\n"
            f"🎯 ٹارگٹ 2: ${t['tp2']:.2f}\n"
            f"🎯 ٹارگٹ 3: ${t['tp3']:.2f}"
        )

    if direction == 'NEUTRAL':
        return f"📊 XAUUSD: No trade — waiting for confirmation\nConfidence: {signal['confidence']}%"
    t = signal['targets']
    return (
        f"📈 Direction: {direction}\n"
        f"💪 Confidence: {signal['confidence']}%\n\n"
        f"💰 Entry: ${t['entry']:.2f}\n"
        f"🛑 Stop Loss: ${t['stop_loss']:.2f}\n"
        f"🎯 TP1: ${t['tp1']:.2f}\n"
        f"🎯 TP2: ${t['tp2']:.2f}\n"
        f"🎯 TP3: ${t['tp3']:.2f}"
    )


def build_instagram_caption(signal):
    lang = config.SOCIAL_LANGUAGE
    hook = generate_hook(signal['direction'], signal['price'], signal['confidence'], seed=signal.get('id'))
    cta = generate_cta(seed=signal.get('id'))
    return (
        f"{hook}\n\n"
        f"{_signal_lines(signal, lang)}\n\n"
        f"{cta}\n\n"
        f"⚠️ {config.DISCLAIMER}\n\n"
        f"{HASHTAGS}"
    )


def build_facebook_caption(signal):
    # Same structure as Instagram; Facebook doesn't need as many hashtags.
    lang = config.SOCIAL_LANGUAGE
    hook = generate_hook(signal['direction'], signal['price'], signal['confidence'], seed=signal.get('id'))
    cta = generate_cta(seed=signal.get('id'))
    return (
        f"{hook}\n\n"
        f"{_signal_lines(signal, lang)}\n\n"
        f"{cta}\n\n"
        f"⚠️ {config.DISCLAIMER}\n\n"
        f"#Gold #XAUUSD #ForexSignals"
    )


def build_twitter_caption(signal):
    """Twitter/X captions must stay compact — keep it under ~270 chars
    so it never gets silently truncated by a client."""
    lang = config.SOCIAL_LANGUAGE
    hook = generate_hook(signal['direction'], signal['price'], signal['confidence'], seed=signal.get('id'))
    direction = signal['direction']

    if lang == 'ur':
        if direction == 'NEUTRAL':
            body = f"XAUUSD: ابھی کوئی ٹریڈ نہیں۔ اعتماد {signal['confidence']}%۔"
        else:
            t = signal['targets']
            body = (
                f"XAUUSD {direction} | انٹری ${t['entry']:.2f} | SL ${t['stop_loss']:.2f} | "
                f"TP1 ${t['tp1']:.2f} TP2 ${t['tp2']:.2f} | اعتماد {signal['confidence']}%"
            )
    elif direction == 'NEUTRAL':
        body = f"XAUUSD: no trade yet. Confidence {signal['confidence']}%."
    else:
        t = signal['targets']
        body = (
            f"XAUUSD {direction} | Entry ${t['entry']:.2f} | SL ${t['stop_loss']:.2f} | "
            f"TP1 ${t['tp1']:.2f} TP2 ${t['tp2']:.2f} | Conf {signal['confidence']}%"
        )

    text = f"{hook}\n\n{body}\n\n#Gold #XAUUSD #Forex"
    if len(text) > 275:
        text = text[:272] + "..."
    return text


def build_telegram_caption(signal):
    lang = config.SOCIAL_LANGUAGE
    hook = generate_hook(signal['direction'], signal['price'], signal['confidence'], seed=signal.get('id'))
    cta = generate_cta(seed=signal.get('id'))
    return (
        f"{hook}\n\n"
        f"{_signal_lines(signal, lang)}\n\n"
        f"{cta}\n\n"
        f"⚠️ {config.DISCLAIMER}"
    )


def build_all_captions(signal):
    return {
        'instagram': build_instagram_caption(signal),
        'facebook': build_facebook_caption(signal),
        'twitter': build_twitter_caption(signal),
        'telegram': build_telegram_caption(signal),
    }
