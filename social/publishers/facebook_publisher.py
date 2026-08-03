"""Posts directly to a Facebook Page via the Graph API.

Unlike Instagram, Facebook Page photo/video endpoints accept a raw
multipart file upload — no public URL hosting required.

Setup: create a Meta app, generate a long-lived Page Access Token with
`pages_manage_posts` + `pages_read_engagement`, and set:
  FACEBOOK_PAGE_ID=<page id>
  FACEBOOK_PAGE_ACCESS_TOKEN=<page access token>
"""
import logging

import requests

from social import config

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = 'v19.0'
GRAPH_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'


def is_configured():
    return bool(config.FACEBOOK_PAGE_ID and config.FACEBOOK_PAGE_ACCESS_TOKEN)


def publish_photo(image_path, caption):
    if not is_configured():
        logger.warning('Facebook Page not configured, skipping photo post')
        return False
    url = f'{GRAPH_BASE}/{config.FACEBOOK_PAGE_ID}/photos'
    try:
        with open(image_path, 'rb') as f:
            response = requests.post(
                url,
                data={'caption': caption, 'access_token': config.FACEBOOK_PAGE_ACCESS_TOKEN},
                files={'source': f},
                timeout=60,
            )
        response.raise_for_status()
        logger.info('Posted image to Facebook Page')
        return True
    except Exception as e:
        logger.error(f'Facebook photo post failed: {e}')
        return False


def publish_video(video_path, caption):
    if not is_configured():
        logger.warning('Facebook Page not configured, skipping video post')
        return False
    url = f'{GRAPH_BASE}/{config.FACEBOOK_PAGE_ID}/videos'
    try:
        with open(video_path, 'rb') as f:
            response = requests.post(
                url,
                data={'description': caption, 'access_token': config.FACEBOOK_PAGE_ACCESS_TOKEN},
                files={'source': f},
                timeout=180,
            )
        response.raise_for_status()
        logger.info('Posted reel to Facebook Page')
        return True
    except Exception as e:
        logger.error(f'Facebook video post failed: {e}')
        return False
