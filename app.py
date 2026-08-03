"""Single-process entrypoint recommended for cloud deploys (Render,
Railway, etc.).

Runs the trading/social bot's scheduler loop in a background thread and
the media status/file server (media_server.py) in the foreground, in
one process. That matters because a platform like Render only shares a
filesystem within a single service — if bot.py (generating images into
output/) and media_server.py (serving output/ publicly for Instagram)
were deployed as two separate services (a "worker" and a "web"), the
web service would never see the files the worker generated. Running
both in this one process means there's exactly one `output/` directory,
and the service's own public URL doubles as MEDIA_PUBLIC_BASE_URL for
Instagram (auto-detected from Render's RENDER_EXTERNAL_URL).

If you don't need Instagram (no public media URL required), you can
still deploy bot.py alone as a plain background worker instead — see
README.md.
"""
import logging
import os
import threading

from bot import GoldSignalBot
from media_server import app as flask_app

logger = logging.getLogger(__name__)


def _run_bot():
    try:
        GoldSignalBot().start()
    except Exception as e:
        logger.error(f'Bot scheduler thread crashed: {e}')


if __name__ == '__main__':
    threading.Thread(target=_run_bot, daemon=True, name='gold-signal-bot').start()
    port = int(os.getenv('PORT', '8000'))
    flask_app.run(host='0.0.0.0', port=port, threaded=True)
