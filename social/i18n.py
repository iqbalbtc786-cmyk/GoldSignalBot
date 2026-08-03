"""Language support for the social pipeline.

Two things live here:
1. `shape(text)` — Urdu/Arabic-script text is stored and passed to
   Telegram/Instagram/etc. in normal logical order (that's what every
   platform's own renderer expects). But Pillow draws text as a flat
   left-to-right glyph run with no script shaping, so text rasterized
   directly onto the image/reel needs to be pre-reshaped (contextual
   letter joining) and reordered (right-to-left) before `draw.text()`.
   Only call `shape()` for the copy that gets drawn onto a graphic —
   never for text handed to a platform API as a caption.
2. Small label dictionaries so image_card.py / video_reel.py can print
   "ENTRY" or "انٹری" for the same field without branching all over the
   layout code.
"""
import arabic_reshaper
from bidi.algorithm import get_display

LABELS = {
    'en': {
        'no_trade': 'NO TRADE',
        'confidence': 'Confidence: {pct}%',
        'entry': 'ENTRY',
        'stop_loss': 'STOP LOSS',
        'tp1': 'TP1',
        'tp2': 'TP2',
        'tp3': 'TP3',
    },
    'ur': {
        'no_trade': 'ٹریڈ نہیں',
        'confidence': 'اعتماد: {pct}%',
        'entry': 'انٹری',
        'stop_loss': 'اسٹاپ لاس',
        'tp1': 'ٹارگٹ 1',
        'tp2': 'ٹارگٹ 2',
        'tp3': 'ٹارگٹ 3',
    },
}


def label(key, lang, **kwargs):
    text = LABELS.get(lang, LABELS['en'])[key]
    return text.format(**kwargs) if kwargs else text


def shape(text, lang):
    """Reshape + bidi-reorder for direct rendering onto an image/video
    frame. A no-op for English (and safe to call on mixed Urdu/English/
    number strings — the bidi algorithm keeps embedded LTR runs, like a
    price or "BUY", in reading order)."""
    if lang != 'ur':
        return text
    return get_display(arabic_reshaper.reshape(text))
