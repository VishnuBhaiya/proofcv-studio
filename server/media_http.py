"""Single byte ranges for local audio/video seeking; not a filesystem router."""
import re


def media_response(raw, mime, range_header=None):
    if not mime.startswith(('video/', 'audio/')):
        return 200, raw, {}
    headers = {'Accept-Ranges': 'bytes'}
    # Multiple or malformed ranges may be ignored; never construct multipart data.
    match = re.fullmatch(r'bytes=(\d{0,20})-(\d{0,20})', range_header or '')
    if not match or not any(match.groups()):
        return 200, raw, headers
    first, last = match.groups()
    size = len(raw)
    if first:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    else:
        start, end = max(0, size - int(last)), size - 1
    if not size or start >= size or end < start or (not first and int(last) == 0):
        return 416, b'', {**headers, 'Content-Range': f'bytes */{size}'}
    return 206, raw[start:end + 1], {**headers, 'Content-Range': f'bytes {start}-{end}/{size}'}
