"""Posts to an Instagram Business/Creator account via the Meta Graph API
(Content Publishing API).

Unlike Facebook, Instagram's API refuses raw file uploads — it only
accepts a publicly reachable `image_url` / `video_url`. That's why this
workflow ships `media_server.py`: run it (or any static file host) so
generated files are reachable at a public URL, then set:
  MEDIA_PUBLIC_BASE_URL=https://your-public-host
  IG_BUSINESS_ACCOUNT_ID=<ig business account id>
  IG_ACCESS_TOKEN=<page/IG access token with instagram_content_publish>
"""
import logging
import os
import time

import requests

from social import config

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = 'v19.0'
GRAPH_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'


def is_configured():
    return bool(config.IG_BUSINESS_ACCOUNT_ID and config.IG_ACCESS_TOKEN and config.MEDIA_PUBLIC_BASE_URL)


def _public_url(file_path):
    filename = os.path.basename(file_path)
    base = config.MEDIA_PUBLIC_BASE_URL.rstrip('/')
    return f'{base}/media/{filename}'


def _create_container(params):
    url = f'{GRAPH_BASE}/{config.IG_BUSINESS_ACCOUNT_ID}/media'
    params = dict(params)
    params['access_token'] = config.IG_ACCESS_TOKEN
    response = requests.post(url, data=params, timeout=60)
    response.raise_for_status()
    return response.json()['id']


def _publish_container(creation_id):
    url = f'{GRAPH_BASE}/{config.IG_BUSINESS_ACCOUNT_ID}/media_publish'
    response = requests.post(
        url, data={'creation_id': creation_id, 'access_token': config.IG_ACCESS_TOKEN}, timeout=60
    )
    response.raise_for_status()
    return response.json()


def _wait_until_ready(creation_id, timeout_s=180, interval_s=5):
    """Video containers process asynchronously — poll status_code until
    FINISHED (or ERROR/EXPIRED) before publishing."""
    url = f'{GRAPH_BASE}/{creation_id}'
    waited = 0
    while waited < timeout_s:
        response = requests.get(url, params={'fields': 'status_code', 'access_token': config.IG_ACCESS_TOKEN}, timeout=30)
        response.raise_for_status()
        status = response.json().get('status_code')
        if status == 'FINISHED':
            return True
        if status in ('ERROR', 'EXPIRED'):
            logger.error(f'Instagram media container failed to process: {status}')
            return False
        time.sleep(interval_s)
        waited += interval_s
    logger.error('Timed out waiting for Instagram media container to finish processing')
    return False


def publish_photo(image_path, caption):
    if not is_configured():
        logger.warning('Instagram not configured (needs IG_BUSINESS_ACCOUNT_ID, IG_ACCESS_TOKEN, MEDIA_PUBLIC_BASE_URL), skipping')
        return False
    try:
        creation_id = _create_container({'image_url': _public_url(image_path), 'caption': caption})
        _publish_container(creation_id)
        logger.info('Posted image to Instagram')
        return True
    except Exception as e:
        logger.error(f'Instagram photo post failed: {e}')
        return False


def publish_reel(video_path, caption):
    if not is_configured():
        logger.warning('Instagram not configured (needs IG_BUSINESS_ACCOUNT_ID, IG_ACCESS_TOKEN, MEDIA_PUBLIC_BASE_URL), skipping')
        return False
    try:
        creation_id = _create_container({
            'media_type': 'REELS',
            'video_url': _public_url(video_path),
            'caption': caption,
        })
        if not _wait_until_ready(creation_id):
            return False
        _publish_container(creation_id)
        logger.info('Posted reel to Instagram')
        return True
    except Exception as e:
        logger.error(f'Instagram reel post failed: {e}')
        return False
