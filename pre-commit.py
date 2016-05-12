#!/usr/bin/python
"""
no more embarrasing "removed pdb, sorry" commits
checks for prints
uses git grep, be careful to check the docs since some regex patterns will not
apply.

install
-------

save or link as .git/hooks/pre-commit giving +x permission
notice the exclusion of the .py extension
"""

import re
import sys
from collections import namedtuple, defaultdict
from subprocess import Popen, PIPE


# Specific validation type parsers
def parse_git_grep(validation):
    '''
    parses "git parse" commands
    '''
    vname, regex, flags = validation

    pargs = ['-{f}'.format(f=f) for f in flags] if flags else []
    pargs.append(regex)

    return vname, pargs


def parse_git_grep_errors(errors, cname, vname, regex):
    details = []
    error_msg = "\033{vname} error:\n".format(vname=vname)

    for error in errors.split('\n'):
        match = regex.findall(error)
        if match:
            match = [msg.strip() for msg in match[0]]
            detail = {}
            detail['filename'] = match[0]
            detail['lineno'] = match[1]
            detail['error'] = match[2]
        details.append(detail)

    return error_msg, details


# Validation types
VALIDATION_TYPES = ('git_grep', )

# Validation classes
GitGrepPCall = namedtuple('GitGrepPCall', ['name', 'regex', 'flags'])


# Validation type -> validations grouping
"""
Ideally there should be more rexes to match special cases.
ie: begining of string, commented out statements, etc
It's better to have several small rexes than a greedy complex one
The threshold should be ~500 steps per regex, max or maybe less.
"""
VALIDATIONS = {
    'git_grep': (
        GitGrepPCall(
            'traceback_check',
            "i?pdb[ .;]",
            'En'),

        GitGrepPCall(
            'print_check_py2_literal',
            "print[\'\" ]{1,3}[a-zA-Z]+[\'\"]{1,3}",
            'En'),
        GitGrepPCall(
            'print_check_py2_var',
            "#?print [a-zA-Z0-9_]+$",
            'En'),

        GitGrepPCall(
            'print_check_py3_literal',
            "print\([\'\"]{1,3}[a-zA-Z0-9_ ]+[\'\"]{1,3}\)",
            'En'),
        GitGrepPCall(
            'print_check_py3_var',
            "print\([a-zA-Z0-9_]+\)",
            'En'),
        )
    }

# Validation type -> command parsing
COMMANDS = {
    'git_grep': (
        'git',
        'grep',
        ),
    }

# Validation type -> parser mapping
PARSERS = {
    'git_grep': parse_git_grep,
    }

ERROR_PARSERS = {
    'git_grep': (
            parse_git_grep_errors,
            re.compile(
                r"(?P<filename>[\w]+.[\w]+):(?P<lno>[\d]+):(?P<error>.+)"
            ),
        )
    }

REPORT_FORMAT = "File {filename} line {lineno}: {error}"


# Integrity validation, dont even run the script if something is missing
def integrity_validation():
    '''
    Perform quick checks.
    If any of these don't work abort the script
    '''
    for vtype in VALIDATION_TYPES:
        assert vtype in VALIDATIONS, 'Missing validation'
        assert vtype in COMMANDS, 'Missing command'
        assert vtype in PARSERS, 'Missing parser'
integrity_validation()


def parse_pcall(commands, validations, parsers):
    '''
    generate process calls from validations
    '''
    for cname, cargs in commands.iteritems():
        for validation in validations[cname]:
            parser = parsers[cname]
            vname, vargs = parser(validation)

            pargs = []
            pargs.extend(cargs)
            pargs.extend(vargs)

            yield cname, vname, pargs


report = defaultdict(list)

for cname, vname, pargs in parse_pcall(COMMANDS, VALIDATIONS, PARSERS):
    process = Popen(pargs, stdout=PIPE)
    pdb_check, _ = process.communicate()

    error_found = process.returncode == 0

    if error_found:
        error_parser, error_regex = ERROR_PARSERS[cname]
        msg, details = error_parser(pdb_check, cname, vname, error_regex)

        if details:
            report[msg] = details


# TODO: Make a proper report
# https://goo.gl/T53Ifq

if report:
    report_format = REPORT_FORMAT
    print "Please fix the following issues before commiting:\n"
    for msg, details in report.iteritems():
        sys.stdout.write('=' * 30 + '\n')
        sys.stdout.write(msg)
        sys.stdout.write('=' * 30 + '\n')

        for detail in details:
            detail = report_format.format(**detail)
            sys.stdout.write(detail + '\n')
        sys.stdout.write('\n\n')

sys.exit(-1)
