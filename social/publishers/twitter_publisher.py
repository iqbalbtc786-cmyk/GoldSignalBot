"""Posts to Twitter/X via the official `tweepy` client.

Media upload still requires the v1.1 endpoint (tweepy.API), while the
tweet itself is created through the v2 endpoint (tweepy.Client) —
that's simply how X's API is split today. Needs a developer app with
read+write permissions:
  TWITTER_API_KEY / TWITTER_API_SECRET        (consumer keys)
  TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET (user access tokens)
"""
import logging

from social import config

logger = logging.getLogger(__name__)


def is_configured():
    return bool(
        config.TWITTER_API_KEY and config.TWITTER_API_SECRET
        and config.TWITTER_ACCESS_TOKEN and config.TWITTER_ACCESS_SECRET
    )


def _clients():
    import tweepy

    auth = tweepy.OAuth1UserHandler(
        config.TWITTER_API_KEY, config.TWITTER_API_SECRET,
        config.TWITTER_ACCESS_TOKEN, config.TWITTER_ACCESS_SECRET,
    )
    api_v1 = tweepy.API(auth)
    client_v2 = tweepy.Client(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_SECRET,
    )
    return api_v1, client_v2


def _post_with_media(media_path, text, media_category=None):
    api_v1, client_v2 = _clients()
    kwargs = {'media_category': media_category} if media_category else {}
    media = api_v1.media_upload(filename=media_path, **kwargs)
    client_v2.create_tweet(text=text, media_ids=[media.media_id])


def publish_photo(image_path, caption):
    if not is_configured():
        logger.warning('Twitter/X not configured, skipping photo post')
        return False
    try:
        _post_with_media(image_path, caption)
        logger.info('Posted image to Twitter/X')
        return True
    except Exception as e:
        logger.error(f'Twitter/X photo post failed: {e}')
        return False


def publish_video(video_path, caption):
    if not is_configured():
        logger.warning('Twitter/X not configured, skipping video post')
        return False
    try:
        _post_with_media(video_path, caption, media_category='tweet_video')
        logger.info('Posted reel to Twitter/X')
        return True
    except Exception as e:
        logger.error(f'Twitter/X video post failed: {e}')
        return False
