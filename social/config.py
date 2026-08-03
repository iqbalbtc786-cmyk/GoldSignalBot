"""Environment-driven configuration for the social media workflow.

Every value is optional: a channel is simply skipped (with a log
message) if its credentials are not set. This lets the bot run with
Telegram only, then grow into Facebook/Instagram/Twitter as API keys
are added, without any code changes.
"""
import os

# --- Branding -------------------------------------------------------
BRAND_NAME = os.getenv('BRAND_NAME', 'Gold Signal Pro')
BRAND_HANDLE = os.getenv('BRAND_HANDLE', '@goldsignalpro')
PRIMARY_COLOR = os.getenv('BRAND_PRIMARY_COLOR', '#0B0F1A')   # near-black navy
GOLD_COLOR = os.getenv('BRAND_GOLD_COLOR', '#D4AF37')          # gold accent
BUY_COLOR = '#16C784'
SELL_COLOR = '#EA3943'
NEUTRAL_COLOR = '#8A93A6'

# --- Output ------------------------------------------------------------
OUTPUT_DIR = os.getenv('SOCIAL_OUTPUT_DIR', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output'))

# --- Optional AI hook writer -----------------------------------------
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_HOOK_MODEL', 'gpt-4o-mini')

# --- Telegram (reuses the existing signal bot credentials) -----------
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
# Optional separate public channel for the social feed posts (falls back
# to TELEGRAM_CHAT_ID if not set).
TELEGRAM_SOCIAL_CHANNEL_ID = os.getenv('TELEGRAM_SOCIAL_CHANNEL_ID', TELEGRAM_CHAT_ID)

# --- Facebook Page -----------------------------------------------------
FACEBOOK_PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')

# --- Instagram Business/Creator account (via Meta Graph API) ----------
IG_BUSINESS_ACCOUNT_ID = os.getenv('IG_BUSINESS_ACCOUNT_ID')
IG_ACCESS_TOKEN = os.getenv('IG_ACCESS_TOKEN', FACEBOOK_PAGE_ACCESS_TOKEN)
# Instagram's Content Publishing API requires a public URL for the
# image/video (it will not accept a raw file upload). MEDIA_PUBLIC_BASE_URL
# should point at wherever media_server.py is reachable from the internet,
# e.g. https://your-app.onrender.com
MEDIA_PUBLIC_BASE_URL = os.getenv('MEDIA_PUBLIC_BASE_URL', '')

# --- Twitter / X --------------------------------------------------------
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_SECRET = os.getenv('TWITTER_ACCESS_SECRET')

# --- Posting behaviour ---------------------------------------------------
# Master switch — set to 'false' to generate content without publishing.
SOCIAL_AUTOPOST_ENABLED = os.getenv('SOCIAL_AUTOPOST_ENABLED', 'true').lower() == 'true'
# Post a reel/video only for actionable BUY/SELL signals by default
# (set to 'true' to also render a reel for NEUTRAL market-update posts).
POST_REEL_ON_NEUTRAL = os.getenv('POST_REEL_ON_NEUTRAL', 'false').lower() == 'true'
# Minimum confidence required before the social pipeline fires at all.
SOCIAL_CONFIDENCE_THRESHOLD = int(os.getenv('SOCIAL_CONFIDENCE_THRESHOLD', '70'))
DISCLAIMER = os.getenv(
    'SOCIAL_DISCLAIMER',
    'Not financial advice. Trading involves risk — always use proper risk management.'
)


def configured_channels():
    """Return a dict of {channel: bool} describing what is ready to post."""
    return {
        'telegram': bool(TELEGRAM_TOKEN and TELEGRAM_SOCIAL_CHANNEL_ID),
        'facebook': bool(FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN),
        'instagram': bool(IG_BUSINESS_ACCOUNT_ID and IG_ACCESS_TOKEN and MEDIA_PUBLIC_BASE_URL),
        'twitter': bool(TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_SECRET),
    }
