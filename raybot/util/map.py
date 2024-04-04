from PIL import Image, ImageDraw, ImageFont
from typing import Sequence
import math
import os
import tempfile
import logging
from raybot import config
from raybot.model import Location


zooms = None
cached_tiles = {}


def deg2num(lon_deg, lat_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def get_zooms():
    global zooms
    if zooms or not os.path.exists(config.TILES):
        return zooms
    zooms = sorted([int(z) for z in os.listdir(config.TILES) if z.isdecimal()])
    return zooms


def load_tile(zoom, x, y, tilesize=256):
    k = f'{zoom},{x},{y}'
    if k in cached_tiles:
        return cached_tiles[k]
    path = os.path.join(config.TILES, str(zoom), str(x), f'{y}.png')
    tile = None
    if os.path.exists(path):
        try:
            tile = Image.open(path)
        except IOError:
            pass
    found = tile is not None
    if not found:
        tile = Image.new("RGBA", (tilesize, tilesize), color='#ffeeee')
    cached_tiles[k] = (tile, found)
    return (tile, found)


def merge_tiles(xmin, ymin, xmax, ymax, zoom, tilesize=256):
    xsize = xmax - xmin + 1
    ysize = ymax - ymin + 1
    if xsize * ysize > 20:
        logging.error(f'Too many tiles to join: {xsize} × {ysize} '
                      f'({xmin}-{xmax}, {ymin}-{ymax}, {zoom})')
        return None

    found_any = False
    image = Image.new("RGBA", (xsize * tilesize, ysize * tilesize))
    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            tile, found = load_tile(zoom, x, y)
            image.paste(tile, ((x - xmin) * tilesize, (y - ymin) * tilesize))
            if found:
                found_any = True
    return image if found_any else None


def build_basemap(minlon, minlat, maxlon, maxlat, gutter=100,
                  minsize=200, maxsize=700, maxzoom=None):
    """Finds tile numbers, checks that zoom is not too big.
    Returns an image and a function (lon, lat) -> (x, y)."""
    zooms = get_zooms()
    if not zooms:
        return None, None
    zoom = (maxzoom or zooms[-1]) + 1
    tilesize = 256
    while zoom > zooms[0]:
        zoom -= 1
        xmin, ymax = deg2num(minlon, minlat, zoom)
        xmax, ymin = deg2num(maxlon, maxlat, zoom)
        xsize = (xmax - xmin) * tilesize + gutter * 2
        ysize = (ymax - ymin) * tilesize + gutter * 2
        if xsize < maxsize and ysize < maxsize:
            break

    txmin = int(xmin - 1.0 * gutter / tilesize)
    tymin = int(ymin - 1.0 * gutter / tilesize)
    txmax = int(xmax + 1.0 * gutter / tilesize)
    tymax = int(ymax + 1.0 * gutter / tilesize)
    image = merge_tiles(txmin, tymin, txmax, tymax, zoom)
    if not image:
        return None, None

    cxmin = int((xmin - txmin) * tilesize) - gutter
    cymin = int((ymin - tymin) * tilesize) - gutter
    cxmax = int((xmax - txmin) * tilesize) + gutter
    cymax = int((ymax - tymin) * tilesize) + gutter
    image = image.crop((cxmin, cymin, cxmax, cymax))

    def get_xy(lon, lat):
        tx, ty = deg2num(lon, lat, zoom)
        return (
            round((tx - txmin) * tilesize - cxmin),
            round((ty - tymin) * tilesize - cymin)
        )
    return image, get_xy


def find_bounds(coords):
    minlon, minlat = 180.0, 180.0
    maxlon, maxlat = -180.0, -180.0
    for c in coords:
        if not c:
            continue
        if c.lon < minlon:
            minlon = c.lon
        if c.lon > maxlon:
            maxlon = c.lon
        if c.lat < minlat:
            minlat = c.lat
        if c.lat > maxlat:
            maxlat = c.lat
    return minlon, minlat, maxlon, maxlat


def get_map(coords: Sequence[Location], ref: Location = None):
    if not coords:
        return None
    minlon, minlat, maxlon, maxlat = find_bounds(coords + [ref])
    gutter = 200 if len(coords) > 1 else 300
    image, get_xy = build_basemap(minlon, minlat, maxlon, maxlat, gutter=gutter, maxzoom=17)
    if not image:
        return None

    draw = ImageDraw.Draw(image)
    draw.text((5, image.height - 15), '© OpenStreetMap', fill='#0f0f0f', anchor='ls')
    # Beware of segfault! https://github.com/python-pillow/Pillow/issues/3066
    font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), 'PTC75F.ttf'), 20)
    if len(coords) == 1:
        x, y = get_xy(coords[0].lon, coords[0].lat)
        marker = Image.open(os.path.join(os.path.dirname(__file__), 'marker-icon.png'))
        image.alpha_composite(marker, (x - 12, y - 41))
    else:
        for i, c in enumerate(coords):
            x, y = get_xy(c.lon, c.lat)
            draw.ellipse([(x - 12, y - 12), (x + 12, y + 12)], fill='#0f0f0f')
            draw.text((x + 1, y + 1), str(i + 1), font=font, fill='#f0f0f0', anchor='mm')

    if ref:
        x, y = get_xy(ref.lon, ref.lat)
        draw.ellipse([(x - 8, y - 8), (x + 8, y + 8)], outline='#F51342', fill='#ffffff')
        draw.ellipse([(x - 5, y - 5), (x + 5, y + 5)], fill='#F51342')

    fp = tempfile.NamedTemporaryFile(suffix='.jpg', prefix='raybot-map-')
    image.convert('RGB').save(fp, 'JPEG', quality=80)
    fp.seek(0)
    return fp
