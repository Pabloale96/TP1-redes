import os
import sys


class Logger:
    def __init__(self, verbose=False, quiet=False):
        self.verbose = bool(verbose)
        self.quiet = bool(quiet)

    def set_verbose(self, v: bool):
        self.verbose = bool(v)

    def set_quiet(self, q: bool):
        self.quiet = bool(q)

    def vprint(self, *args, **kwargs):
        if self.quiet:
            return
        if self.verbose:
            print(*args, **kwargs)

    def info(self, *args, **kwargs):
        if not self.quiet:
            print(*args, **kwargs)


def _detect_default_verbose() -> bool:
    env = os.environ.get('TP1_VERBOSE')
    if env is not None:
        if env.lower() in ('1', 'true', 'yes', 'on'):
            return True
        return False

    for a in sys.argv[1:]:
        if a in ('-v', '--verbose'):
            return True

    return False


def _detect_default_quiet() -> bool:
    env = os.environ.get('TP1_QUIET')
    if env is not None:
        if env.lower() in ('1', 'true', 'yes', 'on'):
            return True
        return False

    for a in sys.argv[1:]:
        if a in ('-q', '--quiet'):
            return True

    return False

logger = Logger(verbose=_detect_default_verbose(), quiet=_detect_default_quiet())
