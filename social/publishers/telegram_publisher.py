"""Posts the generated image/reel to a Telegram channel or chat.

Reuses the same bot token the signal bot already uses — this is the
one channel in the workflow that works with zero extra setup.
"""
import logging

import requests

from social import config

logger = logging.getLogger(__name__)

API_BASE = 'https://api.telegram.org/bot{token}/{method}'


def is_configured():
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_SOCIAL_CHANNEL_ID)


def _post(method, data=None, files=None):
    url = API_BASE.format(token=config.TELEGRAM_TOKEN, method=method)
    response = requests.post(url, data=data, files=files, timeout=60)
    if response.status_code != 200:
        logger.error(f'Telegram {method} failed: {response.text}')
        return None
    return response.json()


def publish_photo(image_path, caption):
    if not is_configured():
        logger.warning('Telegram social channel not configured, skipping photo post')
        return False
    with open(image_path, 'rb') as f:
        result = _post(
            'sendPhoto',
            data={'chat_id': config.TELEGRAM_SOCIAL_CHANNEL_ID, 'caption': caption[:1024]},
            files={'photo': f},
        )
    if result and result.get('ok'):
        logger.info('Posted image to Telegram')
        return True
    return False


def publish_video(video_path, caption):
    if not is_configured():
        logger.warning('Telegram social channel not configured, skipping video post')
        return False
    with open(video_path, 'rb') as f:
        result = _post(
            'sendVideo',
            data={'chat_id': config.TELEGRAM_SOCIAL_CHANNEL_ID, 'caption': caption[:1024], 'supports_streaming': True},
            files={'video': f},
        )
    if result and result.get('ok'):
        logger.info('Posted reel to Telegram')
        return True
    return False
