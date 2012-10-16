#!/usr/bin/env python

import os
import re
import sys

# The tests require that the environment is currently set to C, to avoid
# translated strings and use the default date/number/currency formatting
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'
os.environ['LANGUAGE'] = 'C'

import nose
from nose.plugins import Plugin

if 'STOQ_USE_GI' in os.environ:
    from stoq.lib import gicompat
    gicompat.enable()


class Stoq(Plugin):
    # This is a little hack to make sure that Stoq's database configuration
    # is properly setup. If we import tests.base before Cover.setup() in the
    # coverage plugin is called the statistics will skip the modules imported
    # by tests.base
    def begin(self):
        import tests.base
        tests.base  # pyflakes


ATTRIBUTES = dict(bold=1, dark=2, underline=4, blink=5,
                  reverse=7, concealed=8)
COLORS = dict(grey=30, red=31, green=32, yellow=33, blue=34,
              magenta=35, cyan=36, white=37)
RESET = '\033[0m'


def colored(text, color=None, attrs=None):
    if os.getenv('ANSI_COLORS_DISABLED') is None:
        fmt_str = '\033[%dm%s'
        if color is not None:
            text = fmt_str % (COLORS[color], text)

        if attrs is not None:
            for attr in attrs:
                text = fmt_str % (ATTRIBUTES[attr], text)

        text += RESET
    return text


class ColorStream(object):

    _colors = {
        "green": ("OK", "ok", "."),
        "red": ("ERROR", "FAILED", "errors", "E"),
        "yellow": ("FAILURE", "FAIL", "failures", "F"),
        "magenta": ("SKIP", "S"),
        "blue": ("-" * 70, "=" * 70),
        }

    def __init__(self, stream):
        self._stream = stream
        self._color_map = {}
        self._patten_map = {}
        for color, labels in self._colors.items():
            for label in labels:
                self._color_map[label] = color
                if len(label) > 1:
                    self._patten_map[label] = re.compile("%s=\d+" % label)

    def __getattr__(self, key):
        return getattr(self._stream, key)

    def _colorize(self, string, color=None):
        if not string or color is not None:
            return string

        color = self._color_map.get(string)
        if color is None:
            for key in self._color_map:
                # looking for a test failure as LABEL: str(test)
                if string.startswith(key + ":"):
                    segments = string.split(":")
                    label = self._colorize(segments[0] + ":",
                                           self._color_map[key])
                    desc = ":".join(segments[1:])
                    if desc.startswith(" Failure: "):
                        desc = colored(desc, self._color_map[key])
                    return label + desc
            for key, key_color in self._color_map.items():
                # looking for label=number in the summary
                pattern = self._patten_map.get(key)
                if pattern is not None:
                    for match in pattern.findall(string):
                        string = string.replace(
                            match, self._colorize(match, key_color))
        if color is not None:
            string = colored(string, color, attrs=("bold",))
        return string

    def write(self, string):
        self._stream.write(self._colorize(string))

    def writeln(self, string=""):
        self._stream.writeln(self._colorize(string))


class YANC(Plugin):
    """Yet another nose colorer"""

    name = "yanc"

    def options(self, parser, env):
        super(YANC, self).options(parser, env)

    def configure(self, options, conf):
        super(YANC, self).configure(options, conf)
        self.color = (
            hasattr(self.conf, "stream") and
            hasattr(self.conf.stream, "isatty") and
            self.conf.stream.isatty())

    def begin(self):
        if self.color:
            self.conf.stream = ColorStream(self.conf.stream)

    def finalize(self, result):
        if self.color:
            self.conf.stream = self.conf.stream._stream

if '--sql' in sys.argv:
    sys.argv.remove('--sql')
    from stoqlib.database.orm import orm_enable_debugging
    orm_enable_debugging()

argv = sys.argv[:] + [
    # Disable capturing of stdout, we often use this for print debugging
    '--nocapture',
    # Disable logging capture, kiwi is quite verbose and doesn't give
    # a lot of useful information
    '--nologcapture',
    # Be verbose, one line per test instead of just a dot (like trial)
    '--verbose',
    # Detailed errors, useful for tracking down assertEquals
    '--detailed-errors',
    # Enable color output
    '--with-yanc',
    # Stoq integration plugin, must be the last
    # provided option, specifically, after the --with-coverage module
    # when coverage is enabled
    '--with-stoq',
    ]

nose.main(argv=argv, addplugins=[Stoq(), YANC()])
