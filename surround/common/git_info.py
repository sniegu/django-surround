# coding: utf-8

from os.path import join
from re import match
from os.path import dirname, exists, join
from datetime import datetime
import functools
from collections import namedtuple
import re


class ChangeLogException(Exception):
    pass

class OnlyLocalException(Exception):
    pass

def real_repo_only(method):

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):

        if not self.has_repo():
            raise OnlyLocalException()

        return method(self, *args, **kwargs)

    return wrapped


class GitInfo(object):

    _git_info = None
    repo_path = dirname(dirname(__file__))
    dump_path = join(dirname(__file__), 'git_info.pickled')

    @classmethod
    def has_repo(cls):
        return exists(join(cls.repo_path, '.git'))

    @classmethod
    def get_repo(cls):
        import git
        return git.Repo(cls.repo_path)


    def __init__(self):
        repo = self.get_repo()
        self.full_hash = repo.head.commit.sha
        self.root = repo.working_dir
        try:
            try:
                self.branch_name = repo.active_branch.name
            except TypeError as e:
                self.branch_name = [b for b in repo.remotes[0].refs if b.commit == repo.head.commit][0].name
        except Exception:
            self.branch_name = '[detached]' #repo.head.commit.sha[0:7]


        # print(self.branch_name)
        self.history = [self.full_hash] + [p.sha for p in repo.head.commit.iter_parents()]
        # self.short_hash = local('git rev-parse --short HEAD', capture=True).stdout

        if self.branch_name == 'master':
            self.tag = repo.git.describe(match='v*.*.*.*')
            # local('git describe --match "v*.*.*.*"', capture=True).stdout
            matcher = match(r'^(v((\d+)\.(\d+)\.(\d+))\.(\d+))(-.*)?$', self.tag)
            if matcher is None:
                abort('invalid tag: %s' % self.tag)
            self.short_tag = matcher.group(1)
            self.nice_short_version = matcher.group(2)
        else:
            self.tag = None
            self.short_tag = None
            self.nice_short_version = self.short_hash

        self.timestamp = datetime.now().strftime("%d/%m/%y %H:%M:%S")
        self._changelog = []

    @property
    def short_hash(self):
        return self.full_hash[0:7]

    @property
    def nice_version(self):
        return self.branch_name + '-' + self.nice_short_version

    def make_tag_nice(self, tag):
        if tag == 'HEAD':
            return 'dostępne po aktualizacji'

        from django.conf import settings
        return re.sub(settings.SURROUND_CHANGELOG_PATTERN, settings.SURROUND_CHANGELOG_NICE_VERSION, tag)

    def filter_changelog(self, mode):
        batches = []
        issue_matcher = re.compile(r'^' + '|'.join(mode[1]) + '-')
        for b in self.changelog:
            entries = []
            for e in b.entries:
                if e.category in mode[0]:
                    entries.append(ChangeLogEntry(e.category, list(filter(lambda i: issue_matcher.match(i.key), e.issues)), e.text))

            batches.append(ChangeLogBatch(b.tag, b.nice_name, entries))
        return batches


    @property
    def changelog(self):
        if not self._changelog:
            from django.conf import settings
            for number in settings.SURROUND_CHANGELOG_BATCHES:
                try:
                    self._changelog.append(self.changelog_between_versions(settings.SURROUND_CHANGELOG_PATTERN, self.make_tag_nice, number))
                except ChangeLogException:
                    pass

        return self._changelog

    def dump(self):
        import pickle
        force_fetch = self.changelog
        with open(self.dump_path, 'w') as f:
            pickle.dump(self, f)

    @real_repo_only
    def get_commit(self, sha):
        commits = [c for c in self.get_repo().iter_commits('--all') if c.sha == sha]
        return commits[0] if commits else None

    @real_repo_only
    def changelog_between_commits(self, begin, end):
        import subprocess
        out = subprocess.check_output(['git', 'diff', '--diff-filter=AM', '--unified=0', '%s..%s' % (begin, end), '--', join(self.repo_path, 'changelog.txt')]).split('\n')
        changes = []
        for add in out[5:]:
            m = CHANGELOG_ENTRY_REGEX.match(add)
            if m:
                changes.append(ChangeLogEntry(m.group('category'), map(ChangeLogIssue, m.group('issues').split(',')), m.group('text')))

        return changes

    @real_repo_only
    def get_sorted_tags(self, pattern):
        """
        pattern - for production: r'^v(\d+)\.(\d+)\.(\d+)\.0'

        all groups from pattern will be converted to integers, and tags will be compared using the resulting tuple
        """
        matcher = re.compile(pattern)
        tags = []
        for tag in self.get_repo().git.tag().split('\n'):
            m = matcher.match(tag)
            if m:
                numbers = []
                for k, v in m.groupdict().items():
                    if k.startswith('cmp'):
                        numbers.append((int(k[3:]), int(v)))
                numbers.sort()

                tags.append((tag, numbers))
        return map(lambda t: t[0], sorted(tags, key=lambda t: t[1], reverse=True))


    @real_repo_only
    def changelog_between_versions(self, pattern, converter=lambda t: t, start=0, length=1):
        tags = self.get_sorted_tags(pattern)
        tags.insert(0, 'HEAD')
        try:
            tag = tags[start]
            return ChangeLogBatch(tag, converter(tag), self.changelog_between_commits(tags[start + length], tags[start]))
        except IndexError:
            raise ChangeLogException('invalid changelog batch number')


    @classmethod
    def get(cls):

        if cls._git_info is None:

            if cls.has_repo():
                cls._git_info = cls()
            else:
                repo = None
                import pickle
                with open(cls.dump_path, 'r') as f:
                    cls._git_info = pickle.load(f)

        return cls._git_info


CHANGELOG_ENTRY_REGEX = re.compile(r'^\+(?P<category>\w+)\ (?P<issues>(\w+-\d+(,?))+)\ (?P<text>.*)$')

class ChangeLogIssue():

    def __init__(self, key):
        self.key = key

    def get_absolute_url(self):
        return "https://jira.man.poznan.pl/jira/browse/" + self.key


ChangeLogEntry = namedtuple('ChangeLogEntry', ['category', 'issues', 'text'])
ChangeLogBatch = namedtuple('ChangeLogBatch', ['tag', 'nice_name', 'entries'])





