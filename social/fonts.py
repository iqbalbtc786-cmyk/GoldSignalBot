"""Shared font lookup for image/video generation.

Tries common DejaVu/Liberation TrueType locations first (installed via
apt in the Dockerfile, or already present on most Linux dev boxes), and
falls back to Pillow's built-in bitmap font so nothing ever crashes for
lack of a .ttf file — it just looks plainer.
"""
import logging
from PIL import ImageFont

logger = logging.getLogger(__name__)

_BOLD_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
]
_REGULAR_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
]

_cache = {}


def _load(path_list, size):
    key = (tuple(path_list), size)
    if key in _cache:
        return _cache[key]
    for path in path_list:
        try:
            font = ImageFont.truetype(path, size)
            _cache[key] = font
            return font
        except (OSError, IOError):
            continue
    logger.warning('No TrueType font found, falling back to default bitmap font')
    font = ImageFont.load_default()
    _cache[key] = font
    return font


def bold(size):
    return _load(_BOLD_CANDIDATES, size)


def regular(size):
    return _load(_REGULAR_CANDIDATES, size)
