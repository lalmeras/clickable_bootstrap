#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab ai

from __future__ import print_function, unicode_literals

#
# Global warning: use explicitly-indexed .format() ({0}, {1}) so
# that script is compatible with python 2.6.
#

import argparse
import os
import os.path
import pipes
import shlex
import shutil
import subprocess
import sys
import tempfile

description = \
"""
boostrap.py install a working conda environment.
"""


MINICONDA_INSTALLER_URL = 'https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh'


def run(args, debug=False, env=None):
  """Run a command, with stdout and stderr connected to the current terminal.
  Log command if debug=True.
  """
  if debug:
    # python2.6: index is mandatory
    print('[cmd] {0}'.format(' '.join([pipes.quote(i) for i in args])), file=sys.stderr)
    if env:
      # python2.6: index is mandatory
      print('[cmd] env={0}'.format(' '.join(['{0}={1}'.format(k, v) for k,v in env])), file=sys.stderr)
  subprocess.check_call(args, env=env)


def download(url, debug=False):
  """Download a file and return tuple of (fd, abspath).
  Caller is responsible for deleting file.
  Exception if download cannot be done.
  """
  # Miniconda script raise an error if script is not called something.sh
  (handle, abspath) = tempfile.mkstemp(prefix='bootstrap', suffix='.sh')
  os.close(handle)
  try:
    args = ['curl', '-v' if debug else None, '-o', abspath, url]
    args = [i for i in args if i]
    run(args, debug=debug)
  except Exception as e:
    if not debug:
      try:
        os.remove(abspath)
      except:
        # python2.6: index is mandatory
        print('[ERROR] Failing to delete {0}'.format(abspath), file=sys.stderr)
    else:
      # python2.6: index is mandatory
      print('[DEBUG] Keeping file 0{}'.format(abspath), file=sys.stderr)
    raise Exception('Failed to download {0}. {1}'.format(url, str(e)))
  return (handle, abspath)


def bootstrap(prefix, name, environment, reset_conda=False, reset_env=False, debug=False):
  """Delete existing Miniconda if reset_conda=True.
  Print verbose output (stderr of commands and debug messages) if debug=True.
  """
  script_path = os.getcwd()
  # python2.6: index is mandatory
  print("[INFO] Using {0} as script directory".format(script_path), file=sys.stderr)

  if name is None:
    print("[INFO] Environment name computed from script directory", file=sys.stderr)
    name = os.path.basename(script_path)
  # python2.6: index is mandatory
  print("[INFO] Using {0} as environment name".format(name), file=sys.stderr)

  if environment is None:
    print("[INFO] Environment file computed from script directory", file=sys.stderr)
    environment = os.path.join(script_path, 'environment.yml')
  # python2.6: index is mandatory
  print("[INFO] Using {0} as environment file".format(environment), file=sys.stderr)

  skip_install = False
  if not os.path.exists(environment):
    # python2.6: index is mandatory
    print("[WARN] Environment file {0} missing; install will be skipped".format(environment), file=sys.stderr)
    skip_install = True

  # handle ~/ paths
  prefix = os.path.expanduser(prefix)
  prefix_parent = os.path.dirname(prefix)
  if not os.path.exists(prefix_parent):
    try:
      # python2.6: index is mandatory
      print("[INFO] Creating directory {0}".format(prefix_parent), file=sys.stderr)
      os.makedirs(prefix_parent)
    except Exception as e:
      # python2.6: index is mandatory
      raise Exception("Error creating {0}".format(prefix_parent), file=sys.stderr)
  if reset_conda:
    if os.path.exists(prefix):
      # python2.6: index is mandatory
      print("[INFO] Destroying existing env: {0}.".format(prefix), file=sys.stderr)
      shutil.rmtree(prefix)
  miniconda_script = None
  miniconda_install = True
  if os.path.exists(prefix):
    # python2.6: index is mandatory
    print("[INFO] Env {0} already exists; use --reset-conda to destroy and recreate it.".format(prefix),
        file=sys.stderr)
    miniconda_install = False
  try:
    if miniconda_install:
      # Download Miniconda
      (_, miniconda_script) = download(MINICONDA_INSTALLER_URL, debug=debug)
      # Run Miniconda
      miniconda_args = ['/bin/bash', miniconda_script, '-u', '-b', '-p', prefix]
      run(miniconda_args, debug=debug)
    # Upgrade pip
    pip_upgrade_args = [os.path.join(prefix, 'bin', 'pip'), 'install', '--upgrade', 'pip']
    run(pip_upgrade_args, debug=debug)

    env_exists = False
    try:
      subprocess.check_output([os.path.join(prefix, 'bin', 'conda'), 'list', '-n', name],
          stderr=subprocess.STDOUT)
      env_exists = True
    except subprocess.CalledProcessError as e:
      if debug:
        # python2.6: index is mandatory
        print("[DEBUG] Trigger {0} creation as conda list failed: {1}".format(name, e.output),
            file=sys.stderr)

    if reset_env and env_exists:
      # python2.6: index is mandatory
      print("[INFO] Removing {0} ".format(name), file=sys.stderr)
      try:
        subprocess.check_output([os.path.join(prefix, 'bin', 'conda'), 'env', 'remove', '-n', name, '-y'],
          stderr=subprocess.STDOUT)
        env_exists = False
      except subprocess.CalledProcessError as e:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error removing {0}: {1}".format(name, e.output))
    elif env_exists:
      # python2.6: index is mandatory
      print("[INFO] Env {0} already exists; use --reset-env to destroy and recreate it.".format(name),
        file=sys.stderr)

    if not env_exists:
      # python2.6: index is mandatory
      print("[INFO] Creating {0} ".format(name), file=sys.stderr)
      try:
        subprocess.check_output([os.path.join(prefix, 'bin', 'conda'), 'create', '-n', name, '-y'],
          stderr=subprocess.STDOUT)
      except subprocess.CalledProcessError as e:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error creating {0}: {1}".format(name, e.output))

    if not skip_install:
      # python2.6: index is mandatory
      print("[INFO] Installing {0} ".format(name), file=sys.stderr)
      try:
        subprocess.check_output([os.path.join(prefix, 'bin', 'conda'), 'env', 'update', '-n', name, '--file', environment],
          stderr=subprocess.STDOUT)
      except subprocess.CalledProcessError as e:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error installing {0}: {1}".format(name, e.output))
 
    command = os.getenv('BOOTSTRAP_COMMAND', None)
    if command is not None:
      # python2.6: index is mandatory
      print("[INFO] Running {0} in env {1}".format(command, name), file=sys.stderr)
      try:
        activate_conda = ['.', os.path.join(prefix, 'bin/activate')]
        activate_env = ['conda', 'activate', name]
        whole_command = ' '.join(activate_conda + ['&&'] + activate_env + ['&&'] + [command])
        subprocess.check_call(whole_command, shell=True, stderr=subprocess.STDOUT)
      except subprocess.CalledProcessError as e:
        # python2.6: index is mandatory
        raise Exception("[FATAL] Error running {0}: {1}".format(command, e.output))

    # Activate Miniconda env
    # python2.6: index is mandatory
    print("[INFO] Env {0} initialized.".format(prefix), file=sys.stderr)
    # TODO: env activation (?)
  except Exception as e:
    # python2.6: index is mandatory
    print('[ERROR] Bootstrap failure: {0}'.format(str(e)), file=sys.stderr)
    if not debug:
      if miniconda_script:
        try:
          os.remove(miniconda_script)
        except:
          # python2.6: index is mandatory
          print('[ERROR] Failing to delete {0}'.format(miniconda_script), file=sys.stderr)
    else:
      if miniconda_script:
        # python2.6: index is mandatory
        print('[DEBUG] Keeping file {0}'.format(miniconda_script), file=sys.stderr)


def parser():
  """Command line parsing"""
  cmd = argparse.ArgumentParser(description='Initialize a conda environment.')
  cmd.add_argument('--reset-conda', dest='reset_conda', action='store_true', default=False,
      help='Delete existing conda install')
  cmd.add_argument('--reset-env', dest='reset_env', action='store_true', default=False,
      help='Delete existing conda environment')
  cmd.add_argument('--debug', dest='debug', action='store_true', default=False,
      help='Activate debug output')
  cmd.add_argument('--prefix', dest='prefix', default='~/.miniconda2',
      help='Prefix for conda environment')
  cmd.add_argument('--name', dest='name', default=None,
      help='Name for your conda environment; if not provided use parent directory basename')
  cmd.add_argument('--environment', dest='environment', default=None,
      help='environment.yml for your conda environment; if not provided use SCRIPT_PATH/environment.yml')
  return cmd


if __name__ == '__main__':
  args = parser().parse_args()
  bootstrap(**vars(args))
