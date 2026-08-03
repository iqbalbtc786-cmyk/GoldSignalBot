"""Generates a short vertical (9:16) reel/video for a signal using
MoviePy + Pillow. No system ffmpeg install is required — moviepy pulls
in `imageio-ffmpeg`, which ships a portable ffmpeg binary in the wheel.

The reel reuses the same visual language as the static image card
(social/image_card.py) but reveals the hook, badge, confidence bar and
price levels in sequence so it plays like a fast, punchy trade recap —
the format that performs best as an Instagram/TikTok/YouTube Short.
Language follows `config.SOCIAL_LANGUAGE` the same way image_card does.
"""
import logging
import os

import numpy as np
from PIL import Image, ImageDraw

from social import config, i18n
from social.fonts import bold, regular
from social.image_card import (
    _add_candlestick_texture,
    _direction_color,
    _draw_centered_text,
    _draw_paragraph,
    _fonts_for,
    _hex,
    _strip_emoji,
    _vertical_gradient,
    _wrap_text,
)

logger = logging.getLogger(__name__)

SIZE = (1080, 1920)
FPS = 24


def _progress(t, start, duration):
    if duration <= 0:
        return 1.0 if t >= start else 0.0
    return max(0.0, min(1.0, (t - start) / duration))


def _ease_out(p):
    return 1 - (1 - p) ** 2


class _ReelTimeline:
    """Precomputes when each element appears so build_clip and the
    duration calculation always agree."""

    def __init__(self, signal):
        self.signal = signal
        self.is_trade = signal['direction'] != 'NEUTRAL'

        self.hook_start = 0.0
        self.hook_fade = 0.8

        self.badge_start = 1.0
        self.badge_fade = 0.7

        self.price_start = 1.3
        self.price_fade = 0.7

        self.conf_start = 2.1
        self.conf_fade = 1.1

        rows_start = 3.5
        row_gap = 0.85
        row_fade = 0.45
        n_rows = 5 if self.is_trade else 0
        self.rows_start = rows_start
        self.row_gap = row_gap
        self.row_fade = row_fade
        self.n_rows = n_rows

        if self.is_trade:
            levels_end = rows_start + max(0, n_rows - 1) * row_gap + row_fade
        else:
            levels_end = self.conf_start + self.conf_fade

        self.cta_start = levels_end + 0.4
        self.cta_fade = 0.6
        self.duration = self.cta_start + self.cta_fade + 2.2


def _base_static_layer(signal, size=SIZE):
    """Background gradient + candlestick texture + top accent bar +
    brand row + footer disclaimer: identical on every frame, so it is
    rendered once and copied per-frame instead of redrawn."""
    w, h = size
    lang = config.SOCIAL_LANGUAGE
    _, font_regular = _fonts_for(lang)
    bg_top = _hex(config.PRIMARY_COLOR)
    bg_bottom = tuple(min(255, c + 18) for c in bg_top)
    img = _vertical_gradient(size, bg_top, bg_bottom)
    _add_candlestick_texture(img, size, signal.get('id', 'x'), _hex(config.GOLD_COLOR))
    draw = ImageDraw.Draw(img)

    gold = _hex(config.GOLD_COLOR)
    muted = (150, 158, 176)
    pad = 64

    draw.rectangle([0, 0, w, 10], fill=gold)
    brand_font = bold(34)
    handle_font = regular(26)
    draw.text((pad, 40), config.BRAND_NAME.upper(), font=brand_font, fill=gold)
    handle_w = draw.textlength(config.BRAND_HANDLE, font=handle_font)
    draw.text((w - pad - handle_w, 48), config.BRAND_HANDLE, font=handle_font, fill=muted)

    footer_font = font_regular(22)
    footer_lines = _wrap_text(draw, config.DISCLAIMER, footer_font, w - 2 * pad, lang)
    footer_y = h - 50 * len(footer_lines) - 40
    for line in footer_lines:
        _draw_centered_text(draw, line, footer_y, footer_font, muted, w)
        footer_y += 30

    return img.convert('RGBA')


def _paste_faded(base_rgba, draw_fn, alpha, y_offset=0):
    """Render `draw_fn(overlay_draw)` onto a transparent layer, apply a
    global alpha, optionally shift it vertically, and composite it onto
    `base_rgba` (mutating a copy, which is returned)."""
    if alpha <= 0:
        return base_rgba
    overlay = Image.new('RGBA', base_rgba.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    draw_fn(odraw)
    if alpha < 255:
        r, g, b, a = overlay.split()
        a = a.point(lambda v: int(v * alpha / 255))
        overlay = Image.merge('RGBA', (r, g, b, a))
    if y_offset:
        shifted = Image.new('RGBA', overlay.size, (0, 0, 0, 0))
        shifted.paste(overlay, (0, int(y_offset)))
        overlay = shifted
    return Image.alpha_composite(base_rgba, overlay)


def _render_frame(t, timeline, hook, cta, base_layer):
    signal = timeline.signal
    direction = signal['direction']
    lang = config.SOCIAL_LANGUAGE
    font_bold, font_regular = _fonts_for(lang)
    dcolor = _direction_color(direction)
    white = (245, 246, 248)
    muted = (150, 158, 176)
    gold = _hex(config.GOLD_COLOR)
    w, h = SIZE
    pad = 64

    frame = base_layer.copy()
    scratch = ImageDraw.Draw(Image.new('RGBA', (1, 1)))

    # Hook headline
    hook_p = _ease_out(_progress(t, timeline.hook_start, timeline.hook_fade))
    if hook_p > 0:
        hook_font = font_bold(46)

        def draw_hook(d):
            _draw_paragraph(d, _strip_emoji(hook), 130, hook_font, white, w, pad, lang, 58)

        frame = _paste_faded(frame, draw_hook, int(255 * hook_p), y_offset=(1 - hook_p) * 20)

    # Direction badge (BUY/SELL kept in English — universal trading shorthand)
    badge_p = _ease_out(_progress(t, timeline.badge_start, timeline.badge_fade))
    badge_text = i18n.shape(i18n.label('no_trade', lang), lang) if direction == 'NEUTRAL' else direction
    if badge_p > 0:
        badge_font = font_bold(64)
        badge_w = scratch.textlength(badge_text, font=badge_font) + 80
        badge_h = 96
        badge_y = 330

        def draw_badge(d):
            badge_x = (w - badge_w) / 2
            d.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
                                 radius=20, fill=dcolor)
            tw = d.textlength(badge_text, font=badge_font)
            d.text((badge_x + (badge_w - tw) / 2, badge_y + 16), badge_text, font=badge_font, fill=(255, 255, 255))

        frame = _paste_faded(frame, draw_badge, int(255 * badge_p), y_offset=(1 - badge_p) * 20)

    y_after_badge = 330 + 96 + 30

    # Price
    price_p = _ease_out(_progress(t, timeline.price_start, timeline.price_fade))
    if price_p > 0:
        price_font = bold(72)
        price_text = f"${signal['price']:,.2f}"

        def draw_price(d):
            _draw_centered_text(d, price_text, y_after_badge, price_font, white, w)

        frame = _paste_faded(frame, draw_price, int(255 * price_p), y_offset=(1 - price_p) * 20)

    y_after_price = y_after_badge + 90

    # Confidence label + animated bar
    conf_p = _progress(t, timeline.conf_start, timeline.conf_fade)
    if conf_p > 0:
        conf_font = font_regular(32)
        conf_text = i18n.shape(i18n.label('confidence', lang, pct=signal['confidence']), lang)
        bar_w, bar_h, bar_x = w - 2 * pad, 18, pad
        bar_y = y_after_price + 46

        def draw_conf(d):
            _draw_centered_text(d, conf_text, y_after_price, conf_font, muted, w)
            d.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=bar_h // 2, fill=(40, 46, 64))
            fill_w = max(bar_h, int(bar_w * _ease_out(conf_p) * (signal['confidence'] / 100.0)))
            d.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=bar_h // 2, fill=dcolor)

        frame = _paste_faded(frame, draw_conf, 255, y_offset=0)

    y_rows = y_after_price + 46 + 18 + 50

    # Levels rows (staggered reveal) — label/value sides mirror for Urdu (RTL)
    if timeline.is_trade:
        t_targets = signal['targets']
        rows = [
            (i18n.label('entry', lang), f"${t_targets['entry']:.2f}", gold),
            (i18n.label('stop_loss', lang), f"${t_targets['stop_loss']:.2f}", dcolor),
            (i18n.label('tp1', lang), f"${t_targets['tp1']:.2f}", _hex(config.BUY_COLOR)),
            (i18n.label('tp2', lang), f"${t_targets['tp2']:.2f}", _hex(config.BUY_COLOR)),
            (i18n.label('tp3', lang), f"${t_targets['tp3']:.2f}", _hex(config.BUY_COLOR)),
        ]
        label_font = font_regular(26)
        value_font = bold(38)
        row_h = 72
        for i, (label, value, color) in enumerate(rows):
            row_p = _ease_out(_progress(t, timeline.rows_start + i * timeline.row_gap, timeline.row_fade))
            if row_p <= 0:
                continue
            ry = y_rows + i * row_h
            label = i18n.shape(label, lang)

            def draw_row(d, label=label, value=value, color=color, ry=ry, label_font=label_font, value_font=value_font):
                d.rounded_rectangle([pad, ry, w - pad, ry + row_h - 12], radius=14,
                                     fill=(30, 35, 51), outline=(60, 68, 90), width=2)
                val_w = d.textlength(value, font=value_font)
                if lang == 'ur':
                    label_w = d.textlength(label, font=label_font)
                    d.text((w - pad - 26 - label_w, ry + 18), label, font=label_font, fill=muted)
                    d.text((pad + 26, ry + 10), value, font=value_font, fill=color)
                else:
                    d.text((pad + 26, ry + 18), label, font=label_font, fill=muted)
                    d.text((w - pad - 26 - val_w, ry + 10), value, font=value_font, fill=color)

            frame = _paste_faded(frame, draw_row, int(255 * row_p), y_offset=(1 - row_p) * 16)

    # CTA
    cta_p = _ease_out(_progress(t, timeline.cta_start, timeline.cta_fade))
    if cta_p > 0:
        cta_font = font_bold(38)
        cta_lines = _wrap_text(scratch, _strip_emoji(cta), cta_font, w - 2 * pad, lang)[:2]

        def draw_cta(d):
            cy = h - 220 - (len(cta_lines) - 1) * 48
            for line in cta_lines:
                _draw_centered_text(d, line, cy, cta_font, gold, w)
                cy += 48

        frame = _paste_faded(frame, draw_cta, int(255 * cta_p), y_offset=(1 - cta_p) * 16)

    return np.array(frame.convert('RGB'))


def generate_reel(signal, hook, cta, filename=None, music_path=None):
    """Render the MP4 reel and return its filesystem path."""
    from moviepy import VideoClip, AudioFileClip

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    filename = filename or f"{signal['id']}_reel.mp4"
    path = os.path.join(config.OUTPUT_DIR, filename)

    timeline = _ReelTimeline(signal)
    base_layer = _base_static_layer(signal)

    def make_frame(t):
        return _render_frame(t, timeline, hook, cta, base_layer)

    clip = VideoClip(make_frame, duration=timeline.duration).with_fps(FPS)

    music_path = music_path or os.getenv('REEL_MUSIC_PATH')
    if music_path and os.path.exists(music_path):
        try:
            audio = AudioFileClip(music_path).subclipped(0, timeline.duration).with_volume_scaled(0.25)
            clip = clip.with_audio(audio)
        except Exception as e:
            logger.warning(f'Could not attach background music, rendering silent reel instead: {e}')

    clip.write_videofile(path, codec='libx264', audio_codec='aac' if clip.audio else None,
                          fps=FPS, logger=None, preset='medium', threads=2)
    return path
