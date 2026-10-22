"""Explicit synthetic connection diagnostic; never prints credentials."""
import json
import urllib.request
import urllib.error
from server.gemini import GeminiSettings

if __name__ == '__main__':
    settings = GeminiSettings.load()
    print(settings.public_status())
    request = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/' + settings.model + ':generateContent',
        data=json.dumps({'contents': [{'parts': [{'text': 'Say connection verified.'}]}]}).encode(),
        headers={'x-goog-api-key': settings.api_key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        print({'success': bool(result.get('candidates'))})
    except urllib.error.HTTPError as error:
        try:
            detail = json.load(error).get('error', {}).get('message', 'No detail')
            print({'http_status': error.code, 'detail': str(detail).replace(settings.api_key, '[REDACTED]')[:800]})
        except (ValueError, AttributeError):
            print({'http_status': error.code})
