"""Hook generation — the first line that decides whether someone stops
scrolling. Works fully offline from a curated, high-performing hook bank
(English and Pakistani Urdu); if OPENAI_API_KEY is configured it asks an
LLM for a fresh variant instead.
"""
import hashlib
import logging
import random

from social import config

logger = logging.getLogger(__name__)

# Curated copywriting hooks, grouped by signal direction. Each one is a
# template that gets filled in with live numbers so it never reads as
# generic — specificity is what makes a hook credible.
BUY_HOOKS = [
    "🚨 Gold just flashed a BUY signal at ${price} — here's the setup 👇",
    "Smart money is buying gold right now. Confidence: {confidence}%. Details inside 👇",
    "XAUUSD BUY alert: price broke structure at ${price}. Don't fade this one.",
    "While everyone's asleep, gold quietly set up a {confidence}% BUY signal.",
    "Gold bulls are back in control at ${price}. Here's exactly where to enter.",
    "This is the kind of BUY setup that prints — ${price} entry, full plan below 👇",
]

SELL_HOOKS = [
    "🚨 Gold just flashed a SELL signal at ${price} — here's the setup 👇",
    "Gold is rolling over at ${price}. {confidence}% confidence SELL — read this before the next candle.",
    "XAUUSD SELL alert: sellers just took control at ${price}.",
    "The dollar just did something gold traders needed to see. SELL setup inside 👇",
    "Gold topped out at ${price} — here's the SELL plan, entry to TP3.",
    "This SELL signal has a {confidence}% confidence score. Here's why it matters.",
]

NEUTRAL_HOOKS = [
    "Gold is coiling right now — here's what has to happen before we trade it.",
    "No trade (yet). Here's the exact level that flips this market.",
    "Patience pays: gold's sitting at a decision point. Full market read below 👇",
    "We're staying flat on gold — here's the level we're watching next.",
    "Not every setup is a trade. Here's today's XAUUSD market structure.",
]

CTA_LINES = [
    "Follow for the next signal before it moves. 🔔",
    "Turn on notifications — gold moves fast. 🔔",
    "Save this post so you have the levels handy. 📌",
    "Tag a trader who needs to see this. 👇",
    "Join the channel for real-time alerts. 🔗 link in bio",
]

# Pakistani Urdu hook bank — same specificity/urgency as the English one,
# written the way Pakistani trading channels actually talk (English
# trading terms like BUY/SELL/TP kept as-is, since that's how the local
# forex/gold community uses them even in Urdu speech).
BUY_HOOKS_UR = [
    "🚨 گولڈ میں زبردست BUY سگنل آ گیا ${price} پر — پوری تفصیل نیچے 👇",
    "بڑے کھلاڑی ابھی گولڈ خرید رہے ہیں۔ اعتماد: {confidence}%۔ مکمل تفصیل اندر 👇",
    "XAUUSD BUY الرٹ: قیمت نے ${price} پر structure توڑ دیا۔ اس سگنل کو نظر انداز نہ کریں۔",
    "جب سب سو رہے تھے، گولڈ نے خاموشی سے {confidence}% BUY سگنل بنا لیا۔",
    "گولڈ بلز نے ${price} پر دوبارہ کنٹرول سنبھال لیا — انٹری پوائنٹ یہ رہا۔",
    "یہ وہی BUY سیٹ اپ ہے جو منافع دیتا ہے — ${price} انٹری، مکمل پلان نیچے 👇",
]

SELL_HOOKS_UR = [
    "🚨 گولڈ میں زبردست SELL سگنل آ گیا ${price} پر — پوری تفصیل نیچے 👇",
    "گولڈ ${price} پر نیچے آ رہا ہے۔ {confidence}% اعتماد کے ساتھ SELL — اگلی کینڈل سے پہلے پڑھ لیں۔",
    "XAUUSD SELL الرٹ: سیلرز نے ${price} پر مکمل کنٹرول سنبھال لیا۔",
    "ڈالر نے ابھی وہی کیا جس کا گولڈ ٹریڈرز کو انتظار تھا۔ SELL سیٹ اپ اندر 👇",
    "گولڈ ${price} پر ٹاپ بنا کر واپس آیا — انٹری سے TP3 تک مکمل SELL پلان۔",
    "اس SELL سگنل کا اعتماد سکور {confidence}% ہے — وجہ یہ ہے۔",
]

NEUTRAL_HOOKS_UR = [
    "گولڈ فی الحال ایک محدود دائرے میں گھوم رہا ہے — ٹریڈ سے پہلے یہ ہونا ضروری ہے۔",
    "ابھی کوئی ٹریڈ نہیں — یہی وہ لیول ہے جو مارکیٹ کا رخ بدلے گا۔",
    "صبر کا پھل میٹھا: گولڈ ایک فیصلہ کن مقام پر ہے۔ مکمل مارکیٹ ریڈ نیچے 👇",
    "فی الحال گولڈ پر کوئی پوزیشن نہیں — اگلا اہم لیول یہ ہے۔",
    "ہر سیٹ اپ ٹریڈ نہیں ہوتا۔ آج کا XAUUSD مارکیٹ اسٹرکچر یہ ہے۔",
]

CTA_LINES_UR = [
    "اگلا سگنل مِس نہ کریں — فالو کر لیں۔ 🔔",
    "نوٹیفیکیشن آن کر لیں — گولڈ تیزی سے حرکت کرتا ہے۔ 🔔",
    "یہ پوسٹ محفوظ کر لیں تاکہ لیولز ہاتھ میں رہیں۔ 📌",
    "کسی ٹریڈر دوست کو ٹیگ کریں جسے یہ دیکھنا چاہیے۔ 👇",
    "ریئل ٹائم الرٹس کے لیے چینل جوائن کریں۔ 🔗 لنک بائیو میں",
]


def _pick(seq, seed_text):
    """Deterministic-but-varied pick so the same signal always gets the
    same hook (idempotent re-runs) while different signals rotate."""
    idx = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % len(seq)
    return seq[idx]


def _bank_for(direction, lang):
    if lang == 'ur':
        return {'BUY': BUY_HOOKS_UR, 'SELL': SELL_HOOKS_UR, 'NEUTRAL': NEUTRAL_HOOKS_UR}.get(direction, NEUTRAL_HOOKS_UR)
    return {'BUY': BUY_HOOKS, 'SELL': SELL_HOOKS, 'NEUTRAL': NEUTRAL_HOOKS}.get(direction, NEUTRAL_HOOKS)


def generate_hook(direction, price, confidence, seed=None, lang=None):
    """Return a filled-in hook line for the given signal.

    `seed` lets callers pin the choice (e.g. signal timestamp) so the same
    signal doesn't get a different hook if the pipeline retries.
    """
    lang = lang or config.SOCIAL_LANGUAGE
    seed_text = seed or f"{direction}-{price}-{confidence}"
    template = _pick(_bank_for(direction, lang), seed_text)
    hook = template.format(price=f"{price:,.2f}", confidence=confidence)

    ai_hook = _try_ai_hook(direction, price, confidence, lang)
    return ai_hook or hook


def generate_cta(seed=None, lang=None):
    lang = lang or config.SOCIAL_LANGUAGE
    seed_text = seed or str(random.random())
    return _pick(CTA_LINES_UR if lang == 'ur' else CTA_LINES, seed_text)


def _try_ai_hook(direction, price, confidence, lang):
    """Optional: use an LLM to write a fresh hook when OPENAI_API_KEY is
    set. Falls back silently to the curated bank on any failure so the
    pipeline never breaks because of a network/API issue."""
    if not config.OPENAI_API_KEY:
        return None

    try:
        import requests

        language_instruction = (
            "Write it in natural Pakistani Urdu (Urdu script), the way local gold/forex "
            "trading channels talk — it's fine to keep terms like BUY/SELL/TP in English."
            if lang == 'ur' else
            "Write it in English."
        )
        prompt = (
            "Write ONE short, scroll-stopping social media hook (max 18 words, "
            "no hashtags, no quotation marks) for a gold (XAUUSD) trading signal. "
            f"Signal: {direction}, price ${price:,.2f}, confidence {confidence}%. "
            f"{language_instruction} "
            "Make it punchy and specific, like a top finance-influencer opening line."
        )
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {config.OPENAI_API_KEY}'},
            json={
                'model': config.OPENAI_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 80,
                'temperature': 0.9,
            },
            timeout=15,
        )
        response.raise_for_status()
        text = response.json()['choices'][0]['message']['content'].strip().strip('"')
        return text or None
    except Exception as e:
        logger.warning(f'AI hook generation failed, using curated hook bank instead: {e}')
        return None
