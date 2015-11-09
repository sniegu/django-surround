from surround.django.utils import absolute_url
from django.utils import encoding
import re
import requests


ESI_INCLUDE_PATTERN = re.compile('<esi:include.+src=["\']?(\S+)["\']?".*/>')


def process_esi(request, response):

    parts = []
    remaining_index = 0
    original = response.content

    for esi_match in ESI_INCLUDE_PATTERN.finditer(original):

        url = absolute_url(request, esi_match.group(1))
        if not url.startswith('http'):
            url = ('https:' if request.is_secure() else 'http:') + url

        r = requests.get(url)
        r.encoding = 'utf-8'
        parts.append(encoding.smart_text(original[remaining_index:esi_match.start()]))
        parts.append(encoding.smart_text(r.text))
        remaining_index = esi_match.end()

    parts.append(encoding.smart_text(original[remaining_index:]))

    response.content = ''.join(parts)

