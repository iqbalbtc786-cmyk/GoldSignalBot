"""Tiny static file server that exposes the `output/` folder at
`/media/<filename>`.

Instagram's Content Publishing API will only accept a publicly
reachable URL for the image/video it's asked to post (it does not take
a raw file upload), so this process needs to run somewhere with a
public hostname (e.g. as a second Procfile process type on Render/
Railway/Heroku) and MEDIA_PUBLIC_BASE_URL needs to point at it.

Run with: python media_server.py
"""
import os

from flask import Flask, abort, send_from_directory

from social import config

app = Flask(__name__)


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
    app.run(host='0.0.0.0', port=port)
