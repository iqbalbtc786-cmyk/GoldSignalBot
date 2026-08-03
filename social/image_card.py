"""Generates a branded, on-theme signal image card with Pillow.

Produces two sizes from the same layout engine:
- feed card: 1080x1080 (Instagram/Facebook/Twitter feed post)
- story card: 1080x1920 (Instagram/Facebook Story, also used as the
  first frame / cover of the auto-generated reel)
"""
import hashlib
import os
import re

import numpy as np
from PIL import Image, ImageDraw

from social import config
from social.fonts import bold, regular

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


def _vertical_gradient(size, top_color, bottom_color):
    w, h = size
    top = np.array(top_color, dtype=float)
    bottom = np.array(bottom_color, dtype=float)
    ramp = np.linspace(0, 1, h)[:, None]
    row = top[None, :] * (1 - ramp) + bottom[None, :] * ramp
    arr = np.repeat(row[:, None, :], w, axis=1).astype('uint8')
    return Image.fromarray(arr, mode='RGB')


def _wrap_text(draw, text, font, max_width):
    """Word-wrap `text` so each line fits within max_width pixels."""
    words = text.split()
    lines, current = [], ''
    for word in words:
        trial = f'{current} {word}'.strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_centered_text(draw, text, y, font, fill, canvas_width):
    w = draw.textlength(text, font=font)
    draw.text(((canvas_width - w) / 2, y), text, font=font, fill=fill)


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

    # Brand row
    brand_font = bold(int(34 * scale))
    handle_font = regular(int(26 * scale))
    draw.text((pad, int(40 * scale)), config.BRAND_NAME.upper(), font=brand_font, fill=gold)
    handle_w = draw.textlength(config.BRAND_HANDLE, font=handle_font)
    draw.text((w - pad - handle_w, int(48 * scale)), config.BRAND_HANDLE, font=handle_font, fill=muted)

    # Hook headline
    hook_font = bold(int(46 * scale))
    y = int(130 * scale)
    for line in _wrap_text(draw, _strip_emoji(hook), hook_font, w - 2 * pad)[:4]:
        draw.text((pad, y), line, font=hook_font, fill=white)
        y += int(58 * scale)

    y += int(20 * scale)

    # Direction badge
    badge_text = 'NO TRADE' if direction == 'NEUTRAL' else direction
    badge_font = bold(int(64 * scale))
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

    conf_font = regular(int(32 * scale))
    conf_text = f"Confidence: {signal['confidence']}%"
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

    # Levels grid (skip for NEUTRAL)
    if direction != 'NEUTRAL':
        t = signal['targets']
        rows = [
            ('ENTRY', f"${t['entry']:.2f}", gold),
            ('STOP LOSS', f"${t['stop_loss']:.2f}", dcolor),
            ('TP1', f"${t['tp1']:.2f}", _hex(config.BUY_COLOR)),
            ('TP2', f"${t['tp2']:.2f}", _hex(config.BUY_COLOR)),
            ('TP3', f"${t['tp3']:.2f}", _hex(config.BUY_COLOR)),
        ]
        label_font = regular(int(26 * scale))
        value_font = bold(int(38 * scale))
        row_h = int(72 * scale)
        card_x0, card_x1 = pad, w - pad
        for label, value, color in rows:
            draw.rounded_rectangle(
                [card_x0, y, card_x1, y + row_h - int(12 * scale)],
                radius=int(14 * scale), fill=(30, 35, 51), outline=(60, 68, 90), width=2
            )
            draw.text((card_x0 + int(26 * scale), y + int(18 * scale)), label, font=label_font, fill=muted)
            val_w = draw.textlength(value, font=value_font)
            draw.text((card_x1 - int(26 * scale) - val_w, y + int(10 * scale)), value, font=value_font, fill=color)
            y += row_h
        y += int(10 * scale)
    else:
        y += int(60 * scale)

    # Footer disclaimer
    footer_font = regular(int(22 * scale))
    footer_lines = _wrap_text(draw, config.DISCLAIMER, footer_font, w - 2 * pad)
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
