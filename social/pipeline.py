"""Orchestrates the full auto-posting workflow for one signal:

    signal dict -> hook + captions -> image card + reel -> publish
    everywhere that's configured (Telegram/Facebook/Instagram/Twitter).

Call `run(signal)` once per generated trading signal. Every step is
wrapped so a single channel failing (bad token, network hiccup) never
stops the others from posting.
"""
import logging

from social import config
from social.captions import build_all_captions
from social.hooks import generate_cta, generate_hook
from social.image_card import generate_feed_image
from social.publishers import facebook_publisher, instagram_publisher, telegram_publisher, twitter_publisher
from social.video_reel import generate_reel

logger = logging.getLogger(__name__)


def _safe(step_name, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.error(f'Social pipeline step "{step_name}" failed: {e}')
        return None


def run(signal):
    """signal = {
        'id': str,               # unique per signal, e.g. a timestamp
        'direction': 'BUY' | 'SELL' | 'NEUTRAL',
        'price': float,
        'confidence': int,
        'targets': {'entry', 'stop_loss', 'tp1', 'tp2', 'tp3'} or None,
    }
    """
    if not config.SOCIAL_AUTOPOST_ENABLED:
        logger.info('Social auto-posting disabled (SOCIAL_AUTOPOST_ENABLED=false), skipping')
        return {}

    if signal['confidence'] < config.SOCIAL_CONFIDENCE_THRESHOLD and signal['direction'] != 'NEUTRAL':
        logger.info('Signal below social posting threshold, skipping auto-post')
        return {}

    channels = config.configured_channels()
    if not any(channels.values()):
        logger.warning('No social channels configured — set TELEGRAM_*, FACEBOOK_*, IG_* or TWITTER_* env vars')
        return {}

    logger.info(f"Generating social content for {signal['direction']} signal ({signal['confidence']}%)")

    hook = generate_hook(signal['direction'], signal['price'], signal['confidence'], seed=signal.get('id'))
    cta = generate_cta(seed=signal.get('id'))
    captions = build_all_captions(signal)

    feed_image = _safe('generate_feed_image', generate_feed_image, signal, hook)

    want_reel = signal['direction'] != 'NEUTRAL' or config.POST_REEL_ON_NEUTRAL
    reel_video = _safe('generate_reel', generate_reel, signal, hook, cta) if want_reel else None

    results = {}

    if channels['telegram'] and feed_image:
        results['telegram_photo'] = _safe(
            'telegram_photo', telegram_publisher.publish_photo, feed_image, captions['telegram']
        )
    if channels['telegram'] and reel_video:
        results['telegram_video'] = _safe(
            'telegram_video', telegram_publisher.publish_video, reel_video, captions['telegram']
        )

    if channels['facebook'] and feed_image:
        results['facebook_photo'] = _safe(
            'facebook_photo', facebook_publisher.publish_photo, feed_image, captions['facebook']
        )
    if channels['facebook'] and reel_video:
        results['facebook_video'] = _safe(
            'facebook_video', facebook_publisher.publish_video, reel_video, captions['facebook']
        )

    if channels['instagram'] and feed_image:
        results['instagram_photo'] = _safe(
            'instagram_photo', instagram_publisher.publish_photo, feed_image, captions['instagram']
        )
    if channels['instagram'] and reel_video:
        results['instagram_reel'] = _safe(
            'instagram_reel', instagram_publisher.publish_reel, reel_video, captions['instagram']
        )

    if channels['twitter'] and feed_image:
        results['twitter_photo'] = _safe(
            'twitter_photo', twitter_publisher.publish_photo, feed_image, captions['twitter']
        )

    logger.info(f'Social pipeline results: {results}')
    return results
