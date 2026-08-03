"""Tiny static file server that exposes the `output/` folder at
`/media/<filename>`.

Instagram's Content Publishing API will only accept a publicly
reachable URL for the image/video it's asked to post (it does not take
a raw file upload), so this process needs to run somewhere with a
public hostname and MEDIA_PUBLIC_BASE_URL needs to point at it.

On its own this only serves media. `app.py` is the recommended way to
run this in production: it runs this Flask app *and* the trading/social
bot's scheduler in the same process, so both share one filesystem and
one public URL — see that file for why a separate worker + web service
(e.g. two Render services) doesn't work for Instagram publishing.

Run standalone with: python media_server.py
"""
import os

from flask import Flask, abort, send_from_directory

from social import config

app = Flask(__name__)


@app.route('/')
def status():
    channels = config.configured_channels()
    return {
        'status': 'ok',
        'service': config.BRAND_NAME,
        'social_channels_configured': channels,
    }


@app.route('/media/<path:filename>')
def media(filename):
    if not os.path.isfile(os.path.join(config.OUTPUT_DIR, filename)):
        abort(404)
    return send_from_directory(config.OUTPUT_DIR, filename)


@app.route('/healthz')
def healthz():
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', port=port, threaded=True)
