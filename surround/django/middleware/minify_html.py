import re
from django.conf import settings
from django.utils.html import strip_spaces_between_tags

RE_MULTISPACE = re.compile(r'\s{2,}')

OMIT_TAG_PATTERNS = [re.compile(r'(<pre[\s|\S]*pre>)'),
                     re.compile(r'(<div data-preprocess="notminify"[\s|\S]*div>)'),
                     re.compile(r'(<textarea[\s|\S]*textarea>)'),
                     re.compile(r'(<script[\s|\S]*script>)')]


class SliceObj(object):
    def __init__(self, pattern, content):
        self.pattern = pattern
        self.content = content

    def __str__(self):
        return '%s - %s' % (self.pattern, self.content)


class MinifyHTMLMiddleware(object):
    def __init__(self):
        self.minify = getattr(settings, 'MINIFY_HTML', not settings.DEBUG)
        self.exclude_subdomains_regexes = [re.compile(r'^%s\.' % sub) for sub in getattr(settings, 'MINIFY_HTML_EXCLUDE_SUBDOMAINS', [])]

    def process_response(self, request, response):
        if response.streaming:
            return response
        if not self.minify:
            return response
        if response.status_code != 200 or ('text/html' not in response.get('Content-Type', '')):
            return response

        host = request.get_host()
        for r in self.exclude_subdomains_regexes:
            if r.match(host):
                return response

        # Simple workaround - do not minify elements which match OMMIT_TAG_PATTERNS
        response.content = strip_spaces_between_tags(response.content.strip())
        sliced_content = [SliceObj('', response.content)]
        for pattern in OMIT_TAG_PATTERNS:
            new_content = []
            for slice_of_content in sliced_content:
                if slice_of_content.pattern is '':
                    for to_parser in pattern.split(slice_of_content.content):
                        if pattern.match(to_parser):
                            s_obj = SliceObj(pattern.pattern, to_parser)
                        else:
                            s_obj = SliceObj('', to_parser)

                        new_content.append(s_obj)
                else:
                    new_content.append(slice_of_content)
            sliced_content = new_content
        response.content = ''.join(
            [s.content if s.pattern is not '' else RE_MULTISPACE.sub(' ', s.content) for s in sliced_content])

        return response

