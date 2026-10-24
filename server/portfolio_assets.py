"""Bounded, immutable local media storage. Never serve this directory wholesale."""
import base64
import binascii
import hashlib
import io
import math
import re
import subprocess
import warnings
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

MAX_IMAGE = 5 * 1024 * 1024
MAX_VIDEO = 12 * 1024 * 1024
MAX_VIDEO_SECONDS = 300
MAX_PIXELS = 16_000_000


def digest(value):
    return hashlib.sha256(value).hexdigest()


def decode(encoded, limit):
    if not isinstance(encoded, str) or len(encoded) > (limit * 4 // 3 + 16):
        raise ValueError('Media exceeds the allowed size.')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Media encoding is invalid.') from None
    if not 0 < len(raw) <= limit:
        raise ValueError('Media is empty or too large.')
    return raw


class MediaStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, raw, extension):
        key = digest(raw) + '.' + extension
        path = self.root / key
        if not path.exists():
            # Exclusive create protects immutable content-addressed blobs.
            try:
                with path.open('xb') as stream:
                    stream.write(raw)
            except FileExistsError:
                pass
        return key

    def read(self, key):
        if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{64}\.(png|mp4|wav)', key):
            raise ValueError('Unknown media key.')
        path = self.root / key
        if not path.is_file():
            raise ValueError('Media is unavailable.')
        return path.read_bytes()

    def image(self, encoded):
        raw = decode(encoded, MAX_IMAGE)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format not in ('PNG', 'JPEG') or image.width * image.height > MAX_PIXELS:
                        raise ValueError('Use a PNG/JPEG image up to 16 megapixels.')
                    image.load()
                    display = ImageOps.exif_transpose(image).convert('RGB')
                    display.thumbnail((2400, 2400))
                    output = io.BytesIO()
                    display.save(output, format='PNG', optimize=True)
                    normal = output.getvalue()
                    if len(normal) > MAX_IMAGE:
                        raise ValueError('The normalized image exceeds 5 MB. Resize or simplify the image and upload again.')
                    return dict(key=self.put(normal, 'png'), sha256=digest(normal),
                                mime='image/png', width=display.width, height=display.height,
                                size=len(normal), duration=0)
        except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValueError('The image could not be safely decoded.') from None

    def video(self, encoded):
        raw = decode(encoded, MAX_VIDEO)
        if len(raw) < 16 or raw[4:8] != b'ftyp':
            raise ValueError('Use an MP4 video, at most 12 MB and 5 minutes.')
        try:
            import imageio_ffmpeg
        except ImportError:
            raise ValueError('Install the pinned imageio-ffmpeg dependency for video tours.') from None
        # Inspect an uncommitted temporary file; invalid videos must not leave
        # permanent content-addressed blobs behind.
        with tempfile.NamedTemporaryFile(dir=self.root, suffix='.mp4', delete=False) as stream:
            stream.write(raw)
            temporary = Path(stream.name)
        try:
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner',
                                     '-protocol_whitelist', 'file,pipe', '-enable_drefs', '0', '-use_absolute_path', '0', '-i', str(temporary),
                                     '-t', '0.1', '-frames:v', '1', '-f', 'null', '-'],
                                    capture_output=True, timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            info = result.stderr.decode('utf-8', errors='replace')
            duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', info)
            dimensions = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', info)
            if result.returncode or not duration or not dimensions:
                raise ValueError('Video decoding failed. Export a standard MP4 and retry.')
            hours, minutes, seconds = map(float, duration.groups())
            length = hours * 3600 + minutes * 60 + seconds
            width, height = map(int, dimensions.groups())
            if not math.isfinite(length) or not 0 < length <= MAX_VIDEO_SECONDS or width * height > 3840 * 2160:
                raise ValueError('Videos must be at most 5 minutes and 3840×2160 pixels.')
            return dict(key=self.put(raw, 'mp4'), sha256=digest(raw), mime='video/mp4', width=width,
                        height=height, size=len(raw), duration=length)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Video inspection timed out or is unavailable.') from None
        finally:
            temporary.unlink(missing_ok=True)
