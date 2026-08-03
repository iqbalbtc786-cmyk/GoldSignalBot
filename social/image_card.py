"""Generates a branded, on-theme signal image card with Pillow.

Produces two sizes from the same layout engine:
- feed card: 1080x1080 (Instagram/Facebook/Twitter feed post)
- story card: 1080x1920 (Instagram/Facebook Story, also used as the
  first frame / cover of the auto-generated reel)

Supports Urdu (`config.SOCIAL_LANGUAGE == 'ur'`, the default): text gets
routed through `social.i18n.shape()` for correct letter-joining/RTL
order and drawn with the bundled Noto Naskh Arabic font, and
label/value order in the levels grid mirrors for right-to-left reading.
"""
import hashlib
import os
import re

import numpy as np
from PIL import Image, ImageDraw

from social import config, i18n
from social.fonts import bold, regular, urdu_bold, urdu_regular

# The bundled DejaVu/Liberation fonts have no color-emoji glyphs, so any
# emoji drawn on the canvas renders as a "tofu" box. Captions sent as text
# (Instagram/Twitter/Telegram) keep their emoji — this strip is only for
# text rasterized onto the image itself.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⭐❤️]+"
)


def _strip_emoji(text):
    return _EMOJI_RE.sub('', text).strip()


def _hex(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _direction_color(direction):
    return {
        'BUY': _hex(config.BUY_COLOR),
        'SELL': _hex(config.SELL_COLOR),
    }.get(direction, _hex(config.NEUTRAL_COLOR))


def _fonts_for(lang):
    return (urdu_bold, urdu_regular) if lang == 'ur' else (bold, regular)


def _vertical_gradient(size, top_color, bottom_color):
    w, h = size
    top = np.array(top_color, dtype=float)
    bottom = np.array(bottom_color, dtype=float)
    ramp = np.linspace(0, 1, h)[:, None]
    row = top[None, :] * (1 - ramp) + bottom[None, :] * ramp
    arr = np.repeat(row[:, None, :], w, axis=1).astype('uint8')
    return Image.fromarray(arr, mode='RGB')


def _wrap_text(draw, text, font, max_width, lang='en'):
    """Word-wrap `text` so each line fits within max_width pixels.
    Measures using the shaped (post-reshape/bidi) width for Urdu, since
    that's what actually gets drawn."""
    words = text.split()
    lines, current = [], ''
    for word in words:
        trial = f'{current} {word}'.strip()
        measured = i18n.shape(trial, lang)
        if draw.textlength(measured, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return [i18n.shape(line, lang) for line in lines]


def _draw_centered_text(draw, text, y, font, fill, canvas_width):
    w = draw.textlength(text, font=font)
    draw.text(((canvas_width - w) / 2, y), text, font=font, fill=fill)


def _draw_paragraph(draw, text, y, font, fill, canvas_width, pad, lang, line_height, max_lines=4):
    """Draw a left-aligned (English) or right-aligned (Urdu) wrapped
    paragraph, returning the y position after the last line."""
    lines = _wrap_text(draw, text, font, canvas_width - 2 * pad, lang)[:max_lines]
    for line in lines:
        if lang == 'ur':
            line_w = draw.textlength(line, font=font)
            draw.text((canvas_width - pad - line_w, y), line, font=font, fill=fill)
        else:
            draw.text((pad, y), line, font=font, fill=fill)
        y += line_height
    return y


def _add_candlestick_texture(img, size, seed_text, color):
    """Faint decorative candlestick strip across the full canvas so the
    story/reel format (taller than the content) never looks like empty
    dead space at the bottom."""
    w, h = size
    rng = np.random.default_rng(int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % (2 ** 32))
    overlay = Image.new('RGBA', size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    n = 28
    slot = w / n
    price = 0.5
    for i in range(n):
        price += rng.uniform(-0.15, 0.15)
        price = min(max(price, 0.1), 0.9)
        body_h = rng.uniform(0.05, 0.16) * h
        cy = h * price
        x0 = i * slot + slot * 0.2
        x1 = (i + 1) * slot - slot * 0.2
        up = rng.random() > 0.5
        fill = color + (26,) if up else (110, 116, 132, 22)
        odraw.rectangle([x0, cy - body_h / 2, x1, cy + body_h / 2], fill=fill)
        odraw.line([( x0 + x1) / 2, cy - body_h, (x0 + x1) / 2, cy + body_h], fill=fill, width=max(1, int(w / 400)))
    img.paste(Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB'), (0, 0))


def render_card(signal, hook, size=(1080, 1080)):
    w, h = size
    scale = w / 1080.0
    lang = config.SOCIAL_LANGUAGE
    font_bold, font_regular = _fonts_for(lang)

    bg_top = _hex(config.PRIMARY_COLOR)
    bg_bottom = tuple(min(255, c + 18) for c in bg_top)
    img = _vertical_gradient(size, bg_top, bg_bottom)
    _add_candlestick_texture(img, size, signal.get('id', 'x'), _hex(config.GOLD_COLOR))
    draw = ImageDraw.Draw(img)

    gold = _hex(config.GOLD_COLOR)
    white = (245, 246, 248)
    muted = (150, 158, 176)
    direction = signal['direction']
    dcolor = _direction_color(direction)

    pad = int(64 * scale)

    # Top accent bar
    draw.rectangle([0, 0, w, int(10 * scale)], fill=gold)

    # Brand row (brand name/handle are proper nouns — kept as configured, not translated)
    brand_font = bold(int(34 * scale))
    handle_font = regular(int(26 * scale))
    draw.text((pad, int(40 * scale)), config.BRAND_NAME.upper(), font=brand_font, fill=gold)
    handle_w = draw.textlength(config.BRAND_HANDLE, font=handle_font)
    draw.text((w - pad - handle_w, int(48 * scale)), config.BRAND_HANDLE, font=handle_font, fill=muted)

    # Hook headline
    hook_font = font_bold(int(46 * scale))
    y = int(130 * scale)
    y = _draw_paragraph(draw, _strip_emoji(hook), y, hook_font, white, w, pad, lang, int(58 * scale))

    y += int(20 * scale)

    # Direction badge (BUY/SELL kept in English — universal trading shorthand)
    badge_text = i18n.shape(i18n.label('no_trade', lang), lang) if direction == 'NEUTRAL' else direction
    badge_font = font_bold(int(64 * scale))
    badge_w = draw.textlength(badge_text, font=badge_font) + int(80 * scale)
    badge_h = int(96 * scale)
    badge_x = (w - badge_w) / 2
    draw.rounded_rectangle(
        [badge_x, y, badge_x + badge_w, y + badge_h],
        radius=int(20 * scale), fill=dcolor
    )
    _draw_centered_text(draw, badge_text, y + int(16 * scale), badge_font, (255, 255, 255), w)
    y += badge_h + int(30 * scale)

    # Price + confidence
    price_font = bold(int(72 * scale))
    price_text = f"${signal['price']:,.2f}"
    _draw_centered_text(draw, price_text, y, price_font, white, w)
    y += int(90 * scale)

    conf_font = font_regular(int(32 * scale))
    conf_text = i18n.shape(i18n.label('confidence', lang, pct=signal['confidence']), lang)
    _draw_centered_text(draw, conf_text, y, conf_font, muted, w)
    y += int(46 * scale)

    # Confidence bar
    bar_w = w - 2 * pad
    bar_h = int(18 * scale)
    bar_x = pad
    draw.rounded_rectangle([bar_x, y, bar_x + bar_w, y + bar_h], radius=bar_h // 2, fill=(40, 46, 64))
    fill_w = max(int(bar_h), int(bar_w * (signal['confidence'] / 100.0)))
    draw.rounded_rectangle([bar_x, y, bar_x + fill_w, y + bar_h], radius=bar_h // 2, fill=dcolor)
    y += bar_h + int(50 * scale)

    # Levels grid (skip for NEUTRAL) — label/value sides mirror for Urdu (RTL)
    if direction != 'NEUTRAL':
        t = signal['targets']
        rows = [
            (i18n.label('entry', lang), f"${t['entry']:.2f}", gold),
            (i18n.label('stop_loss', lang), f"${t['stop_loss']:.2f}", dcolor),
            (i18n.label('tp1', lang), f"${t['tp1']:.2f}", _hex(config.BUY_COLOR)),
            (i18n.label('tp2', lang), f"${t['tp2']:.2f}", _hex(config.BUY_COLOR)),
            (i18n.label('tp3', lang), f"${t['tp3']:.2f}", _hex(config.BUY_COLOR)),
        ]
        label_font = font_regular(int(26 * scale))
        value_font = bold(int(38 * scale))
        row_h = int(72 * scale)
        card_x0, card_x1 = pad, w - pad
        inset = int(26 * scale)
        for label, value, color in rows:
            label = i18n.shape(label, lang)
            draw.rounded_rectangle(
                [card_x0, y, card_x1, y + row_h - int(12 * scale)],
                radius=int(14 * scale), fill=(30, 35, 51), outline=(60, 68, 90), width=2
            )
            val_w = draw.textlength(value, font=value_font)
            if lang == 'ur':
                # RTL: label on the right, value on the left.
                label_w = draw.textlength(label, font=label_font)
                draw.text((card_x1 - inset - label_w, y + int(18 * scale)), label, font=label_font, fill=muted)
                draw.text((card_x0 + inset, y + int(10 * scale)), value, font=value_font, fill=color)
            else:
                draw.text((card_x0 + inset, y + int(18 * scale)), label, font=label_font, fill=muted)
                draw.text((card_x1 - inset - val_w, y + int(10 * scale)), value, font=value_font, fill=color)
            y += row_h
        y += int(10 * scale)
    else:
        y += int(60 * scale)

    # Footer disclaimer
    footer_font = font_regular(int(22 * scale))
    footer_lines = _wrap_text(draw, config.DISCLAIMER, footer_font, w - 2 * pad, lang)
    footer_y = h - int(50 * scale) * len(footer_lines) - int(30 * scale)
    for line in footer_lines:
        _draw_centered_text(draw, line, footer_y, footer_font, muted, w)
        footer_y += int(30 * scale)

    return img


def _ensure_output_dir():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    return config.OUTPUT_DIR


def generate_feed_image(signal, hook, filename=None):
    img = render_card(signal, hook, size=(1080, 1080))
    out_dir = _ensure_output_dir()
    filename = filename or f"{signal['id']}_feed.jpg"
    path = os.path.join(out_dir, filename)
    img.convert('RGB').save(path, quality=92)
    return path


def generate_story_image(signal, hook, filename=None):
    img = render_card(signal, hook, size=(1080, 1920))
    out_dir = _ensure_output_dir()
    filename = filename or f"{signal['id']}_story.jpg"
    path = os.path.join(out_dir, filename)
    img.convert('RGB').save(path, quality=92)
    return path
