#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

from __future__ import print_function, unicode_literals

#
# Global warning: use explicitly-indexed .format() ({0}, {1}) so
# that script is compatible with python 2.6.
#

import argparse
import os
import os.path
import pipes
import re
import shutil
import stat
import subprocess
import sys
import tempfile

COMMAND_DESCRIPTION = """
boostrap-repository.py checkout and install a clickable repository.
"""


def _bootstrap(git_command, git_url, repository_path, ref, args,
               reset_git=False, reset_env=False, reset_conda=False,
               reset_pipenv=False):
    """Checkout `git_url` with provided `git_command`. Working copy *parent* path
    is `repository_path` . Folder name is built from `git_url`.

    If reset_git is true, target path is
    """
    repository_path = os.path.expanduser(repository_path)
    target_path = os.path.join(repository_path,
        os.path.splitext(os.path.basename(git_url))[0])
    # protect some commons path
    if os.path.realpath(target_path) == os.path.realpath(repository_path) \
            or os.path.realpath(target_path) == '/' \
            or os.path.realpath(target_path) == os.path.realpath(os.path.expanduser('~')):
        print('[FATAL] Target path {0} is protected; aborted.'.format(target_path))
    print('[INFO] Using {0} as target repository.'.format(target_path), file=sys.stderr)
    if not os.path.exists(git_command):
        print('[FATAL] Missing command {0}; aborted.'.format(git_command), file=sys.stderr)
        os.exit(1)
    try:
        if not os.path.exists(repository_path):
            print('[INFO] Creating {0}.'.format(repository_path), file=sys.stderr)
            os.makedirs(repository_path)
        if reset_git and os.path.exists(target_path) and target_path:
            print('[WARN ] Deleting existing clone: {0}.'.format(target_path))
            shutil.rmtree(target_path)
        if not os.path.exists(target_path):
            print('[INFO] Cloning {0} in {1}.'.format(git_url, target_path), file=sys.stderr)
            subprocess.check_call(_command(git_command, 'clone', git_url, target_path))
        print('[INFO] Switching/refreshing reference {0}.'.format(ref), file=sys.stderr)
        subprocess.check_call(_command(git_command, 'fetch'), cwd=target_path)
        subprocess.check_call(_command(git_command, 'clean', '-df'), cwd=target_path)
        subprocess.check_call(_command(git_command, 'checkout', ref), cwd=target_path)
        subprocess.check_call(_command(git_command, 'pull'), cwd=target_path)
        subprocess.check_call(_command(git_command, 'submodule', 'update', '--init'),
                              cwd=target_path)
        if os.path.exists(os.path.join(target_path, 'Pipfile')):
            print('[INFO] Running pipenv phase', file=sys.stderr)
            try:
                subprocess.check_call(['pipenv', '--version'])
            except Exception as pipenv_not_found:
                raise Exception("[FATAL] pipenv not installed; install pipenv with 'dnf install pipenv' or 'apt-get install pipenv': {0}"
                                .format(pipenv_not_found))
            if reset_pipenv:
                print('[INFO] Cleaning pipenv', file=sys.stderr)
                if subprocess.call(['pipenv', '--venv'], cwd=target_path) == 0:
                    subprocess.check_call(['pipenv', '--rm'], cwd=target_path)
                if os.path.exists(os.path.join(target_path, 'Pipfile.lock')):
                    os.remove(os.path.join(target_path, 'Pipfile.lock'))
            subprocess.check_call(['pipenv', 'install'], cwd=target_path)
            subprocess.check_call(['pipenv', 'run'] + args, cwd=target_path)
        else:
            print('[INFO] Running bootstrap phase', file=sys.stderr)
            bootstrap_path = os.path.join(target_path, './bootstrap/bootstrap.sh')
            bootstrap_arguments = []
            if reset_env:
                bootstrap_arguments.append('--reset-env')
            if reset_conda:
                bootstrap_arguments.append('--reset-conda')
            bootstrap_arguments.append('--')
            bootstrap_arguments.extend(args)
            subprocess.check_call(_command(bootstrap_path, *bootstrap_arguments), cwd=target_path)
    except subprocess.CalledProcessError as e:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error running {0}: {1}"
                        .format(e.cmd, e.output))
    except Exception as e1:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error: {0}".format(e1))


def _command(command, *args):
    """Build command path (prefix + /bin/ + command) and return a command
    list [command, *args] that can be used by subprocess API."""
    result = [command]
    result.extend(args)
    return result


def _parser():
    """Command line parsing"""
    # path for clone
    default_git_command = os.getenv('BOOTSTRAP_GIT_COMMAND', '/bin/git')
    # path for clone
    default_repository_path = os.getenv('BOOTSTRAP_REPOSITORY_PATH', '~/git/tools')
    # git clone url
    default_git_url = os.getenv('BOOTSTRAP_GIT_URL', None)
    # git checkout ref
    default_ref = os.getenv('BOOTSTRAP_REF', 'master')
    cmd = argparse.ArgumentParser(description=COMMAND_DESCRIPTION)
    cmd.add_argument('git_url', default=default_git_url,
                     help='Repository git url.')
    cmd.add_argument('--repository-path',
                     dest='repository_path',
                     default=default_repository_path,
                     help='Parent path for the cloned git working directory.')
    cmd.add_argument('--ref',
                     dest='ref', default=default_ref,
                     help='Git reference to checkout.')
    cmd.add_argument('--reset-git',
                     dest='reset_git', action='store_true', default=False,
                     help='Remove existing repository before cloning.')
    cmd.add_argument('--reset-env',
                     dest='reset_env', action='store_true', default=False,
                     help='Remove target environment.')
    cmd.add_argument('--reset-conda',
                     dest='reset_conda', action='store_true', default=False,
                     help='Remove conda installation.')
    cmd.add_argument('--reset-pipenv',
                     dest='reset_pipenv', action='store_true', default=False,
                     help='Remove pipenv installation.')
    cmd.add_argument('--git-command',
                     dest='git_command', default=default_git_command,
                     help='Path for git command.')
    cmd.add_argument('args', nargs=argparse.REMAINDER, help='Bootstrap arguments.')
    return cmd


if __name__ == '__main__':
    args = _parser().parse_args()
    _bootstrap(**vars(args))
