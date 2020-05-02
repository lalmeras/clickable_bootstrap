#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

from __future__ import print_function, unicode_literals

#
# Global warning: use explicitly-indexed .format() ({0}, {1}) so
# that script is compatible with python 2.6.
#

import argparse
import io
import logging
import os
import os.path
import pipes
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback


COMMAND_DESCRIPTION = """
boostrap.py install a working conda environment.
"""
MINICONDA_INSTALLER_URL = \
  'https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh'
ENV_BOOTSTRAP_NAME = 'BOOTSTRAP_NAME'
ENV_BOOTSTRAP_CONDA_ENVYML = 'BOOTSTRAP_CONDA_ENVYML'
ENV_BOOTSTRAP_CONDA_PREFIX = 'BOOTSTRAP_CONDA_PREFIX'
ENV_BOOTSTRAP_PROFILE_DIR = 'BOOTSTRAP_PROFILE_DIR'
ENV_BOOTSTRAP_COMMAND = 'BOOTSTRAP_COMMAND'
ENV_BOOTSTRAP_PATH = 'BOOTSTRAP_PATH'


# from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ  = "\033[1m"


class CustomStreamHandler(logging.StreamHandler):
    def __init__(self, *args, **kwargs):
        logging.StreamHandler.__init__(self, *args, **kwargs)

    def _mapColor(self, levelno):
        if levelno in (logging.CRITICAL, logging.ERROR):
            return RED
        elif levelno in (logging.WARN,):
            return YELLOW
        elif levelno in (logging.INFO,):
            return GREEN
        elif levelno in (logging.DEBUG,):
            return BLUE
        else:
            return None

    def _filterMethod(self, record):
        if record.levelno in (logging.CRITICAL, logging.ERROR, logging.WARN,
                logging.INFO):
            return ""
        else:
            return " (%s)" % record.name

    def emit(self, record):
        if sys.stderr.isatty():
            color = self._mapColor(record.levelno)
        else:
            color = None
        if color is None:
            record.c_level = '[%(levelname)s]' % {"levelname": record.levelname}
        else:
            record.c_level = '%(color)s[%(levelname)s]%(reset)s' % \
                {
                    "color": COLOR_SEQ % (30 + color),
                    "levelname": record.levelname,
                    "reset": RESET_SEQ
                }
        record.x_method = self._filterMethod(record)
        logging.StreamHandler.emit(self, record)


def _initLogger():
    # python2.6: stream named argument unsupported
    ch = CustomStreamHandler(sys.stderr)
    # [level colored] (method) message...
    # (method) included only for debug
    ch.setFormatter(logging.Formatter('%(c_level)s%(x_method)s %(message)s', None))
    logging.root.addHandler(ch)
    logging.root.setLevel(logging.INFO)
    out = logging.StreamHandler(sys.stdout)
    out.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger('stdout').addHandler(out)
    logging.getLogger('stdout').setLevel(logging.INFO)
    logging.getLogger('stdout').propagate = False


class Logger(object):
    def __init__(self):
        pass

    def __getattr__(self, name):
        try:
            # extract caller method name
            logger_name = traceback.extract_stack()[-2][2]
        except:
            logger_name = "none"
        return getattr(logging.getLogger(logger_name), name)


stdout = logging.getLogger('stdout')
logger = Logger()


def _run(args, **subprocess_args):
    """Run a command, with stdout and stderr connected to the current terminal.
    """
    # python2.6: isEnabledFor not available
    debug = logging.root.getEffectiveLevel() == logging.DEBUG
    if debug:
        command = ' '.join([pipes.quote(i) for i in args])
        logger.debug(command)
        env = subprocess_args.get('env', None)
        if env:
            # print current environment
            env_str = ' '.join(['%s=%s' % (k, pipes.quote(v))
                                for k, v in env.items()])
            logger.debug('env:%s', env_str)
    # call command
    subprocess.check_call(args, **subprocess_args)


def _download(url, _tmpdir=None):
    """Download a file and return tuple of (fd, abspath).
    Caller is responsible for deleting file.
    Exception if download cannot be performed.

    _tmpdir argument is intended for testing purpose.
    """
    # Miniconda script raise an error if script is not called something.sh
    (handle, abspath) = tempfile.mkstemp(prefix='bootstrap', suffix='.sh',
                                         dir=_tmpdir)
    os.close(handle)
    # python2.6: isEnabledFor not available
    debug = logger.getEffectiveLevel() == logging.DEBUG
    try:
        # -L follow redirect
        args = ['curl', '-L', '-v' if debug else None, '-o', abspath, url]
        args = [i for i in args if i]
        _run(args)
    except Exception as e:
        if not debug:
            try:
                os.remove(abspath)
            except Exception:
                logger.error('Failing to delete %s', abspath)
        else:
            logger.debug('Keeping file %s', abspath)
        raise Exception('Failed to download {0}. {1}'.format(url, str(e)))
    return (handle, abspath)


def _command(conda_prefix, command, *args):
    """Build command path (conda_prefix + /bin/ + command) and return a command
    list [command, *args] that can be used by subprocess API."""
    result = [os.path.join(conda_prefix, 'bin', command)]
    result.extend(args)
    return result


def _prepare_conda(prefix, reset_conda):
    """Prepare 'prefix' parent directories. Remove any existing installation
    if reset_conda=True.
    """
    prefix_parent = os.path.dirname(prefix)
    if not os.path.exists(prefix_parent):
        try:
            logger.info("Creating directory %s", prefix_parent)
            os.makedirs(prefix_parent)
        except Exception:
            raise Exception("Error creating %s" % (prefix_parent,))
    if reset_conda:
        if os.path.exists(prefix):
            logger.info("Destroying existing env %s", prefix)
            shutil.rmtree(prefix)


def _skip_env_install(environment):
    """Check file 'environment'; return None if file does not exist."""
    if not os.path.exists(environment):
        logger.warning("Environment file %s missing; env will be created " +
               "but install will be skipped", environment)
        return None
    return environment


def _skip_miniconda(prefix):
    """Return true if miniconda env located in 'prefix' already exists."""
    if os.path.exists(prefix):
        logger.info("%s already exists; use --reset-conda to destroy " +
               "and recreate it.", prefix)
        return True
    return False


def _subprocess_capture(*args, **kwargs):
    try:
        updated_kwargs = dict(kwargs.items())
        updated_kwargs['stderr'] = subprocess.STDOUT
        updated_kwargs['stdout'] = subprocess.PIPE
        p = subprocess.Popen(*args, **updated_kwargs)
        out = p.communicate()[0]
        return (p.returncode, out)
    except OSError:
        pass


def _env_exists(prefix, name):
    """Check if environment named 'name' exists."""
    env_exists = False
    output = None
    # TODO: check env is deactivated before removal
    returncode, output = _subprocess_capture(
        _command(prefix, 'conda', 'list', '-n', name))
    if returncode != 0:
        # python2.6: isEnabledFor not available
        debug = logger.getEffectiveLevel() == logging.DEBUG
        if debug:
            logger.debug("Trigger %s creation as conda list failed: %s",
                         name, output)
    else:
        env_exists = True
    return env_exists


def _env_remove(prefix, name):
    """Remove an existing conda environment named 'name'."""
    logger.info("Removing %s", name)
    returncode, output = _subprocess_capture(
        _command(prefix, 'conda',
                 'env', 'remove', '-n', name, '-y'))
    if returncode != 0:
        raise Exception("[FATAL] Error removing %s: %s" %
                        (name, output))


def _env_create(prefix, name):
    """Create a new Conda environment named 'name'."""
    logger.info("Creating %s", name)
    returncode, output = _subprocess_capture(
        _command(prefix, 'conda', 'create', '-n', name, '-y'))
    if returncode != 0:
        raise Exception("[FATAL] Error creating %s: %s" %
                        (name, output))


def _env_install(prefix, name, environment):
    """Use a environment.yml file to initialize 'name' environment."""
    logger.info("Installing %s", name)
    returncode, output = _subprocess_capture(
        _command(prefix, 'conda', 'env', 'update', '-n', name,
                 '--file', environment))
    if returncode != 0:
        raise Exception("[FATAL] Error installing %s: %s" %
                        (name, output))


def _handle_env(prefix, name, environment, reset_env):
    """Reset env if needed, then create and initialize environment."""
    env_exists = _env_exists(prefix, name)
    if reset_env and env_exists:
        _env_remove(prefix, name)
        env_exists = False
    elif env_exists:
        logger.info("Env %s already exists; use --reset-env to " +
               "destroy and recreate it.", name)

    if not env_exists:
        _env_create(prefix, name)

    if environment is not None:
        _env_install(prefix, name, environment)


def _handle_bootstrap_command(prefix, name):
    """Run BOOTSTRAP_COMMAND in the Conda environment prefix:name."""
    command = os.getenv(ENV_BOOTSTRAP_COMMAND, None)
    if command is not None:
        logger.info("Running in env %s > %s", name, command)
        activate_conda = ['.', os.path.join(prefix, 'bin/activate')]
        activate_env = ['conda', 'activate', pipes.quote(name)]
        whole_command = ' '.join(activate_conda +
                                 ['&&'] + activate_env +
                                 ['&&'] + [command])
        returncode, output = _subprocess_capture(whole_command, shell=True)
        if returncode != 0:
            raise Exception("[FATAL] Error running %s: %s" %
                            (command, output))


def _miniconda_install(prefix, removals=None):
    """Download and install miniconda in prefix, append downloaded file
    in removals if list is initialized"""
    # Conda's python needs libcrypt.so.1 that needs libxcrypt.so.1
    script = """
if [ -x /bin/dnf ]; then
    [ -f /usr/lib64/libcrypt.so.1 ] || sudo dnf install -y libxcrypt-compat
fi
"""
    subprocess.check_call(script, shell=True)
    # Download Miniconda
    (_, miniconda_script) = _download(MINICONDA_INSTALLER_URL)
    if removals is not None:
        removals.append(miniconda_script)
    # Run Miniconda
    miniconda_args = ['/bin/bash', miniconda_script,
                      '-u', '-b', '-p', prefix]
    _run(miniconda_args)


#: .format(bootstrap_d_path) ; activate script
BOOTSTRAP_ACTIVATE_SCRIPT = """
# Reload all environment files
bootstrap-reload () {{
    if compgen -G "{0}/*.conf" > /dev/null; then
        for item in "{0}/"*.conf; do
          source "$item"
        done
    fi
}}

# Function that performs a reload before
# loading environment given as first and unique
# parameter
bootstrap-activate () {{
    bootstrap-reload
    'activate-'"$1"
}}
bootstrap-deactivate () {{
    if [ -z "$BOOTSTRAP_ENV" ]; then
        echo "No env set; deactivate failed"
        return 1
    fi
    deactivate-"$BOOTSTRAP_ENV"
}}

# Preload all environments
bootstrap-reload

# Flag bootstrap functions as loaded
export BOOTSTRAP_ACTIVATE=1
"""

#: .format(activate_script, env_name) ; conda activate
ACTIVATE_SCRIPT = """
activate-{1} () {{
    if [ -n "$BOOTSTRAP_ENV" ]; then
        if [ "$BOOTSTRAP_ENV" == {1} ]; then
            echo "$BOOTSTRAP_ENV already loaded"
            return 1
        else
            echo "Another env $BOOTSTRAP_ENV is loaded; cannot load "{1}
            return 1
        fi
    fi
    source {0} && conda activate {1}
    BOOTSTRAP_ENV="{1}"
}}
deactivate-{1} () {{
    conda deactivate
    unset BOOTSTRAP_ENV
}}
"""
#: command to activate conda env (bootstrap script non found)
ACTIVATE_CONDA_COMMAND = "source {0} && conda activate {1}"
#! command to activate conda env
ACTIVATE_BOOTSTRAP_COMMAND = "source {0} && bootstrap-activate {1}"


def _print_activate_command(prefix, name, bootstrap_conf_path, skip_activate_script):
    # -> .profile.d/boostrap.conf.d/
    bootstrap_conf_d_path = os.path.expanduser('{0}.d'.format(bootstrap_conf_path))
    # -> .profile.d/boostrap.conf.d/activate-[NAME].conf
    activate_path = os.path.join(bootstrap_conf_d_path, 'activate-{0}.conf'.format(name))
    activate_script = ACTIVATE_SCRIPT.format(
        pipes.quote(os.path.join(prefix, 'bin', 'activate')),
        pipes.quote(name)
    )
    bootstrap_script = BOOTSTRAP_ACTIVATE_SCRIPT.format(
        bootstrap_conf_d_path
    )
    activate_script_fails = False
    if not skip_activate_script:
        try:
            # profile_dir may include not resolved '~'
            real_bootstrap_conf_path = os.path.expanduser(bootstrap_conf_path)
            if not os.path.exists(bootstrap_conf_d_path):
                os.makedirs(bootstrap_conf_d_path)
            with io.open(real_bootstrap_conf_path, 'w', encoding='utf-8') as f:
                f.write(bootstrap_script)
            with io.open(activate_path, 'w', encoding='utf-8') as f:
                f.write(activate_script)
        except Exception as e:
            logger.error("activate script creation fails: %s".format(e))
    logger.info("Env %s initialized.", prefix)
    bootstrap_activate_enabled = False
    bootstrap_activate_loadable = False
    if skip_activate_script or activate_script_fails:
        pass
    else:
        # detect bootstrap-activate
        if os.getenv('BOOTSTRAP_ACTIVATE', None) == '1':
            bootstrap_activate_enabled = True
        else:
            try:
                check_command = ['/bin/bash', '-l', '-c', 'echo -n $BOOTSTRAP_ACTIVATE']
                bootstrap_activate_loadable = (
                    subprocess.check_output(check_command) == '1')
            except Exception as e:
                logger.warning('Error checking if bootstrap.conf is sourced. '
                      'Assuming it is not sourced.')
    activate_command = None
    if bootstrap_activate_enabled:
        activate_command = 'bootstrap-activate {0}'.format(pipes.quote(name))
        deactivate_command = 'bootstrap-deactivate'
    elif not skip_activate_script:
        activate_command = ACTIVATE_BOOTSTRAP_COMMAND.format(
            pipes.quote(real_bootstrap_conf_path), pipes.quote(name))
        deactivate_command = 'bootstrap-deactivate'
    else:
        activate_command = ACTIVATE_CONDA_COMMAND.format(
            pipes.quote(os.path.join(prefix, 'bin', 'activate')),
            pipes.quote(name)
        )
        deactivate_command = 'conda deactivate; conda deactivate'
    # print activation command-line
    stdout.info("Run this command to load/unload your env:\n\n" +
         "# Activate environment\n" +
         "%s\n" +
         "# Deactivate environment\n" +
         "%s\n"
         "\n", activate_command, deactivate_command)


def _bootstrap(prefix, name, environment, args,
               reset_conda=False, reset_env=False,
               profile_dir='', skip_activate_script=False,
               verbose=0):
    """Delete existing Miniconda if reset_conda=True.
    Print verbose output (stderr of commands and debug messages) if verbose > 1.
    """
    debug = verbose > 1
    logging.root.setLevel(logging.DEBUG if debug else logging.INFO)
    name = _fix_bootstrap_name(name, warn=True)
    # handle ~/ paths
    prefix = os.path.expanduser(prefix)
    environment = os.path.expanduser(environment)

    # some logging
    logger.info("Using %s as conda prefix", prefix)
    logger.info("Using %s as environment name", name)
    logger.info("Using %s as environment file", environment)

    environment = _skip_env_install(environment)
    # prepare parent folders, reset conda if asked to
    _prepare_conda(prefix, reset_conda)
    # check if conda install is needed
    skip_miniconda = _skip_miniconda(prefix)

    try:
        # Conda installation
        tmp_removals = []
        if not skip_miniconda:
            _miniconda_install(prefix, removals=tmp_removals)

        # Conda env reset, creation and initialization
        _handle_env(prefix, name, environment, reset_env)
        _handle_bootstrap_command(prefix, name)

        # Print commands to activate Miniconda env
        _print_activate_command(prefix, name, profile_dir, skip_activate_script)
        if args:
            logger.info('Use remaining args as command: %s', ' '.join(args))
            # Launch command
            while args[0] == '--':
                args = args[1:]
            # update PATH as we need to launch commands
            env = dict(os.environ)
            env.update({'PATH': '{}:{}'.format(
                os.path.join(prefix, 'envs', name, 'bin'),
                env['PATH']
            )})
            env.update({
                'PKG_CONFIG_PATH':
                  os.path.join(prefix, 'envs', name, 'lib', 'pkgconfig')
            })
            subprocess.check_call(_command(
                os.path.join(prefix, 'envs', name), # env path
                args[0],                            # command
                *args[1:]                           # args
            ), env=env)
    except Exception as e:
        logger.error('Bootstrap failure: %s', str(e))
        # python2.6: isEnabledFor not available
        debug = logger.getEffectiveLevel() == logging.DEBUG
        if not debug:
            if tmp_removals:
                for tmp_removal in tmp_removals:
                    try:
                        os.remove(tmp_removal)
                    except Exception:
                        logger.error('Failing to delete %s', tmp_removal)
        else:
            if tmp_removals:
                for tmp_removal in tmp_removals:
                    logger.debug('Keeping file %s', tmp_removal)


def _default_bootstrap_name(bootstrap_path):
    """Traverse directories from bootstrap_path to find the name to use
    for environment"""
    name = os.path.basename(bootstrap_path)
    path = bootstrap_path
    # ignore bootstrap directory when present
    # stop when at root folder
    while name == 'bootstrap' and path != os.path.dirname(path):
        path = os.path.dirname(path)
        name = os.path.basename(path)
    if not name or name == 'bootstrap':
        return 'default'
    else:
        return _fix_bootstrap_name(name, warn=False)


def _fix_bootstrap_name(bootstrap_name, warn=False):
    bootstrap_name_sub = re.sub(r"[^0-9a-zA-Z-]", "_", bootstrap_name)
    if bootstrap_name != bootstrap_name_sub:
        if warn:
            logger.warning("Environment renamed %s from %s to remove special"
                  " characters", bootstrap_name_sub, bootstrap_name)
        bootstrap_name = bootstrap_name_sub
    return bootstrap_name


def _parser():
    """Command line parsing"""
    # path for environment/pyproject.toml and determining bootstrap_name
    # is not provided
    default_bootstrap_path = os.getenv(ENV_BOOTSTRAP_PATH, os.getcwd())
    default_profile_dir = os.getenv(ENV_BOOTSTRAP_PROFILE_DIR,
                                    '~/.profile.d/bootstrap.conf')
    # default bootstrap_name
    default_bootstrap_name = os.getenv(
        ENV_BOOTSTRAP_NAME,
        _default_bootstrap_name(default_bootstrap_path))
    # default conda prefix
    default_conda_prefix = os.getenv(ENV_BOOTSTRAP_CONDA_PREFIX,
                                     '~/.miniconda2')
    # default environment.yml path
    default_environment_yml = \
        os.getenv(ENV_BOOTSTRAP_CONDA_ENVYML,
                  os.path.join(default_bootstrap_path, 'environment.yml'))
    cmd = argparse.ArgumentParser(description=COMMAND_DESCRIPTION)
    cmd.add_argument('--name',
                     dest='name', default=default_bootstrap_name,
                     help='Name for your conda environment.')
    cmd.add_argument('--environment',
                     dest='environment',
                     default=default_environment_yml,
                     help='environment.yml for your conda environment.')
    cmd.add_argument('--reset-conda',
                     dest='reset_conda', action='store_true', default=False,
                     help='Delete existing conda install (DANGER).')
    cmd.add_argument('--reset-env',
                     dest='reset_env', action='store_true', default=False,
                     help='Delete existing conda environment.')
    cmd.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                     help='Enable verbose output')
    cmd.add_argument('--prefix',
                     dest='prefix', default=default_conda_prefix,
                     help='Prefix for conda environment.')
    cmd.add_argument('--profile-dir',
                     dest='profile_dir', default=default_profile_dir,
                     help='Default path for bootstrap.conf and activate-* scripts')
    cmd.add_argument('--skip-activate-script', dest='skip_activate_script',
                     action='store_true', default=False,
                     help='Do not create activate-[NAME] script')
    cmd.add_argument('args', nargs=argparse.REMAINDER,
                     help='Command launched in environment (ex: powo-roles install --help).')
    return cmd


if __name__ == '__main__':
    _initLogger()
    args = _parser().parse_args()
    _bootstrap(**vars(args))
