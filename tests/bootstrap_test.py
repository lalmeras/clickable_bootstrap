#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

import logging
import os
import py
import pytest
import re
import shutil
import stat
import subprocess
import sys

from mock import patch
from shellescape import quote

try:
    from collections import OrderedDict
except ImportError:
    # Python 2.6
    from ordereddict import OrderedDict


class EnvOverrides(object):
    """This class allows to register environment modification so that it
    can be resetted when test ends"""
    def __init__(self):
        self._orig = dict()
        self._reset = []

    def __getitem__(self, key):
        return os.environ[key]

    def __setitem__(self, key, data):
        if key in os.environ and not key in self._orig:
            self._orig[key] = os.environ[key]
        elif key not in self._orig:
            self._reset.append(key)
        os.environ[key] = data

    def __delitem__(self, key):
        if key in os.environ and not key in self._orig:
            self._orig[key] = os.environ[key]
        del os.environ[key]

    def restore(self):
        for key in self._reset:
            if key in os.environ:
                del os.environ[key]
        for key, value in self._orig.items():
            os.environ[key] = value

@pytest.fixture(scope="function")
def environment():
    """This fixture provides a variable to modify environment variables; when
    test finishes, modifications are erased"""
    environment = EnvOverrides()
    yield environment
    environment.restore()

@pytest.fixture()
def chdir():
    import tempfile
    newpath = tempfile.mkdtemp()
    origpath = os.getcwd()
    os.chdir(newpath)
    yield py.path.local(newpath)
    os.chdir(origpath)
    shutil.rmtree(newpath)

def _out(capture):
    """pytest for python 2.6 uses tuple instead of attributes"""
    try:
        return capture.out
    except:
        return capture[0]

def _err(capture):
    """pytest for python 2.6 uses tuple instead of attributes"""
    try:
        return capture.err
    except:
        return capture[1]

def test_run_standard(capfd, caplog):
    """Run a command, no extra args (success)"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    _run(args)
    captured = capfd.readouterr()
    assert 'hello world' == _out(captured)
    assert len(caplog.records) == 0

def test_run_stderr(capfd, caplog):
    """Run a command with output on stderr (success)"""
    from bootstrap import _run
    args = ' '.join(['>&2', 'echo', '-n', 'hello', 'world'])
    _run(args, shell=True)
    captured = capfd.readouterr()
    assert 'hello world' == _err(captured)
    assert len(caplog.records) == 0

def test_run_env(capfd, caplog):
    """Run a command that print a var from environment"""
    from bootstrap import _run
    args = ['printenv', 'TEST']
    _run(args, env={'TEST': 'VALUE'})
    captured = capfd.readouterr()
    assert 'VALUE\n' == _out(captured)
    assert len(caplog.records) == 0

def test_run_debug(capfd, caplog):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    logging.root.setLevel(logging.DEBUG)
    _run(args)
    records = caplog.records
    captured = capfd.readouterr()
    assert 'echo -n hello world' == records[0].message
    assert 'hello world' == _out(captured)
    assert len(records) == 1

def test_run_debug_env(capfd, caplog):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    import collections
    # use an ordered dict so that debug output is deterministic
    values = [['TEST1', 'VALUE1'], ['TEST2', 'VALUE2']]
    env = OrderedDict(values)
    logging.root.setLevel(logging.DEBUG)
    _run(args, env=env)
    records = caplog.records
    captured = capfd.readouterr()
    assert 'echo -n hello world' == records[0].message
    assert 'env:TEST1=VALUE1 TEST2=VALUE2' == records[1].message
    assert 'hello world' == _out(captured)
    assert len(records) == 2

def test_download_success(capfd, caplog, tmpdir):
    """check that download can be done, and the location of
    provided file"""
    from bootstrap import _download
    logging.root.setLevel(logging.INFO)
    handle = _download('http://google.fr',
                       _tmpdir=str(tmpdir))
    # check that only one file is created in tempdir 
    assert len(tmpdir.listdir()) == 1
    # check that download file is child of tempdir
    assert tmpdir.common(py.path.local(handle[1])) == tmpdir
    captured = capfd.readouterr()
    #assert '' == _err(captured) #curl is verbose
    assert '' == _out(captured)
    assert len(caplog.records) == 0
    shutil.rmtree(str(tmpdir))

def test_download_error(capfd, caplog, tmpdir):
    from bootstrap import _download
    logging.root.setLevel(logging.INFO)
    def f():
        _download('http://notexistingdomain.not',
                  _tmpdir=str(tmpdir))
    pytest.raises(Exception, f)
    # check that no file is created
    assert len(tmpdir.listdir()) == 0
    captured = capfd.readouterr()
    #assert '' == _err(captured) #curl is verbose
    assert '' == _out(captured)
    records = caplog.records
    assert len(records) == 0
    shutil.rmtree(str(tmpdir))

def test_command():
    from bootstrap import _command
    assert ['/prefix/bin/command', 'param1', 'param2'] == \
            _command('/prefix', 'command', 'param1', 'param2')

def test_prepare_conda_not_existing(caplog, tmpdir):
    """If provided prefix is not existing, but parent of prefix exists,
    then nothing is done (prefix does not exist and parent directory is
    untouched)."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda')
    assert not conda.exists()
    _prepare_conda(str(conda), False)
    assert not conda.exists()
    assert len(caplog.records) == 0
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_existing(caplog, tmpdir):
    """If provided prefix exists, nothhing is done (prefix does not exist
    and parent directory is untouched)."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda').mkdir()
    _prepare_conda(str(conda), False)
    assert conda.exists()
    assert conda.isdir()
    assert len(caplog.records) == 0
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_subdir(caplog, tmpdir):
    """If prefix' parent directory does not exist, it is created. Prefix
    is not created."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda/subdir')
    _prepare_conda(str(conda), False)
    assert not conda.exists()
    assert conda.join('/..').isdir()
    records = caplog.records
    assert 'Creating directory {0}'.format(str(conda.join('/..'))) == records[0].message
    assert len([i for i in records if i.name == 'stdout']) == 0
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_reset_existing(caplog, tmpdir):
    """If existing conda prefix exists and reset=True, it is deleted."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda').mkdir()
    _prepare_conda(str(conda), True)
    assert not conda.exists() and conda.join('/..').exists()
    records = caplog.records
    assert 'Destroying existing env {0}'.format(str(conda)) == records[0].message
    assert len([i for i in records if i.name == 'stdout']) == 0
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_reset_invalid(caplog, tmpdir):
    """If existing conda prefix exists and reset=True, but cannot be deleted,
    an exception is raised."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda')
    conda.mkdir()
    os.chmod(str(tmpdir), ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    def f():
        _prepare_conda(str(conda), True)
    pytest.raises(Exception, f)
    records = caplog.records
    assert 'Destroying existing env {0}'.format(str(conda)) == records[0].message
    assert len([i for i in records if i.name == 'stdout']) == 0
    os.chmod(str(tmpdir), stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_parent_invalid(caplog, tmpdir):
    """If existing conda prefix and parent does not exist, but cannot be
    deleted, an exception is raised."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda/subdir')
    os.chmod(str(tmpdir), ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    def f():
        _prepare_conda(str(conda), False)
    pytest.raises(Exception, f)
    assert not conda.exists()
    assert not conda.join('/..').exists()
    assert tmpdir.exists()
    records = caplog.records
    assert 'Creating directory {0}'.format(str(conda.join('/..'))) == records[0].message
    assert len([i for i in records if i.name == 'stdout']) == 0
    shutil.rmtree(str(tmpdir))

def test_skip_env_install_skip(caplog, tmpdir):
    """If no environment file, install is skipped"""
    from bootstrap import _skip_env_install
    env = tmpdir.join('environment')
    assert None == _skip_env_install(str(env))
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('Environment file .* missing', records[0].message)
    shutil.rmtree(str(tmpdir))

def test_skip_env_install_not_skip(caplog, tmpdir):
    """If environment file, return file path"""
    from bootstrap import _skip_env_install
    env = tmpdir.join('environment')
    env.ensure(file=True)
    assert str(env) == _skip_env_install(str(env))
    assert len(caplog.records) == 0
    shutil.rmtree(str(tmpdir))

def test_skip_miniconda_skip(caplog, tmpdir):
    """If miniconda prefix exists, return True"""
    from bootstrap import _skip_miniconda
    assert True == _skip_miniconda(str(tmpdir))
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('--reset-conda', records[0].message)
    assert None != re.search('already exists', records[0].message)
    shutil.rmtree(str(tmpdir))

def test_skip_miniconda_skip(caplog, tmpdir):
    """If miniconda prefix exists, return True"""
    from bootstrap import _skip_miniconda
    prefix = tmpdir.join('prefix')
    assert False == _skip_miniconda(str(prefix))
    records = caplog.records
    assert len(records) == 0
    shutil.rmtree(str(tmpdir))

def test_env_exists_yes(caplog, tmpdir):
    """If environment is listed by conda, return True"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    assert True == _env_exists(str(tmpdir), 'test')
    records = caplog.records
    assert len(records) == 0
    shutil.rmtree(str(tmpdir))

def test_env_exists_no(caplog, tmpdir):
    """If environment is not listed by conda, return False"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    assert False == _env_exists(str(tmpdir), 'test')
    records = caplog.records
    shutil.rmtree(str(tmpdir))

def test_env_exists_no_debug(caplog, tmpdir):
    """If environment is not listed by conda, return False"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    logging.root.setLevel(logging.DEBUG)
    assert False == _env_exists(str(tmpdir), 'test')
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('Trigger .* creation', records[0].message)
    assert None != re.search('error_str', records[0].message)
    shutil.rmtree(str(tmpdir))

def test_env_remove_ok(caplog, tmpdir):
    from bootstrap import _env_remove
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_remove(str(tmpdir), 'test')
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('removing', records[0].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_remove_nok(caplog, tmpdir):
    from bootstrap import _env_remove
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_remove(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('removing', records[0].message, flags=re.I)
    assert None != re.search('error removing', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_create_ok(caplog, tmpdir):
    from bootstrap import _env_create
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_create(str(tmpdir), 'test')
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('creating', records[0].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_create_nok(caplog, tmpdir):
    from bootstrap import _env_create
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_create(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('creating', records[0].message, flags=re.I)
    assert None != re.search('error creating', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_install_ok(caplog, tmpdir):
    from bootstrap import _env_install
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_install(str(tmpdir), 'test', 'fakearg')
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('installing', records[0].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_install_nok(caplog, tmpdir):
    from bootstrap import _env_install
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_install(str(tmpdir), 'test', 'fakearg')
    e = pytest.raises(Exception, f)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('installing', records[0].message, flags=re.I)
    assert None != re.search('error installing', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_no_reset(caplog, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 1, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', False)
    records = caplog.records
    records = [r for r in caplog.records if r.levelno > logging.DEBUG]
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None == re.search('removing', records[0].message, flags=re.I)
    assert None == re.search('--reset-env', records[0].message, flags=re.I)
    assert None != re.search('creating', records[0].message, flags=re.I)
    assert None != re.search('installing', records[1].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_reset(caplog, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 0, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', True)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('removing', records[0].message, flags=re.I)
    assert None == re.search('--reset-env', records[1].message, flags=re.I)
    assert None != re.search('creating', records[1].message, flags=re.I)
    assert None != re.search('installing', records[2].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_exists(caplog, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 0, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', False)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None == re.search('removing', records[0].message, flags=re.I)
    assert None != re.search('--reset-env', records[0].message, flags=re.I)
    assert None == re.search('creating', records[1].message, flags=re.I)
    assert None != re.search('installing', records[1].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_no_environment_file(caplog, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 1, 0, 0)
    _handle_env(str(tmpdir), 'test', None, False)
    records = [r for r in caplog.records if r.levelno > logging.DEBUG]
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None == re.search('removing', records[0].message, flags=re.I)
    assert None == re.search('--reset-env', records[0].message, flags=re.I)
    assert None != re.search('creating', records[0].message, flags=re.I)
    assert None == re.search('installing', records[0].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_bootstrap_command(caplog, tmpdir, environment):
    from bootstrap import _handle_bootstrap_command
    command = 'echo bootstrap'
    environment['BOOTSTRAP_COMMAND'] = command
    activate = tmpdir.join('bin/activate')
    _fake_activate_script(activate)
    _handle_bootstrap_command(str(tmpdir), 'test')
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('running', records[0].message, flags=re.I)
    assert None != re.search(command, records[0].message, flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_bootstrap_command_ko(caplog, tmpdir, environment):
    from bootstrap import _handle_bootstrap_command
    command = 'false'
    environment['BOOTSTRAP_COMMAND'] = command
    activate = tmpdir.join('bin/activate')
    _fake_activate_script(activate)
    def f():
        _handle_bootstrap_command(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    records = caplog.records
    assert len([i for i in records if i.name == 'stdout']) == 0
    assert None != re.search('running', records[0].message, flags=re.I)
    assert None != re.search(command, records[0].message, flags=re.I)
    assert None != re.search('error running', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

@patch('bootstrap._run')
@patch('bootstrap._download')
def test_miniconda_install(download, run, capfd, caplog, tmpdir, environment):
    """Miniconda install; download is mocked to return a fake success script"""
    import bootstrap
    from bootstrap import _miniconda_install
    miniconda_fake = tmpdir.join('miniconda.sh')
    _success_script(miniconda_fake)
    download.return_value = (None, str(miniconda_fake))
    removals = []
    _miniconda_install(str(tmpdir), removals=removals)
    captured = capfd.readouterr()
    # install script is flag for removal
    assert str(miniconda_fake) in removals
    download.assert_called_with(bootstrap.MINICONDA_INSTALLER_URL)
    # no direct output
    # (output is either from download - mocked -
    # or miniconda install script - replaced with a fake script, and not run)
    assert len(caplog.records) == 0
    shutil.rmtree(str(tmpdir))

def test_bootstrap_activate(capfd, tmpdir):
    """Test bootstrap-activate ENV command by:
    * initialising scripts from BOOTSTRAP_* strings (one common file and
      one file by environment
    * using a custom 'conda activate' mock that prints the env name passed
      as parameter
    * checking the BOOTSTRAP_ENV environment variable"""
    import bootstrap
    name = 'env-name'
    # fake conda script; just the activated env name
    conda_fake = tmpdir.join('conda')
    _fake_activate_script(conda_fake)
    # prepare profile.d/bootstrap.d folders
    profile_d = tmpdir.join('profile.d').mkdir()
    bootstrap_d = profile_d.join('bootstrap.d').mkdir()
    # profile.d/bootstrap.sh -> common file
    bootstrap_sh = profile_d.join('bootstrap.sh')
    bootstrap_sh.write(
            bootstrap.BOOTSTRAP_ACTIVATE_SCRIPT.format(bootstrap_d))
    # env related file: profile.d/bootstrap.d/ENV.conf
    bootstrap_d.join('{0}.conf'.format(name)).write(
            bootstrap.ACTIVATE_SCRIPT.format(str(conda_fake), name))
    # activate environment
    command = 'source {bootstrap_source};\
               bootstrap-activate {name};\
               echo current env: $BOOTSTRAP_ENV;'.format(
            bootstrap_source=str(bootstrap_sh),
            name=name)
    p = subprocess.Popen(command, shell=True, executable='/bin/bash')
    p.communicate()
    captured = capfd.readouterr()
    # result of 'conda activate env-name' call
    assert None != re.search('env {0} activated\n'.format(name), _out(captured))
    # check that BOOTSTRAP_ENV is initialised
    assert None != re.search('current env: {0}\n'.format(name), _out(captured))
    assert 0 == p.returncode
    shutil.rmtree(str(tmpdir))

def test_fix_bootstrap_name():
    """Only a-zA-Z0-9-_ kept for env name; replace all others chars by _"""
    from bootstrap import _fix_bootstrap_name
    assert 'envname' == _fix_bootstrap_name('envname')
    assert 'EnvName' == _fix_bootstrap_name('EnvName')
    assert 'envname0' == _fix_bootstrap_name('envname0')
    assert '0envname' == _fix_bootstrap_name('0envname')
    assert 'env_name' == _fix_bootstrap_name('env_name')
    assert 'env-name' == _fix_bootstrap_name('env-name')
    assert 'env_name' == _fix_bootstrap_name('env,name')
    assert 'env_name' == _fix_bootstrap_name('env name')

def test_print_activate_command(caplog, tmpdir):
    """Check env activation command"""
    from bootstrap import _print_activate_command
    bootstrap_conf_path = tmpdir.join('bootstrap.conf')
    _print_activate_command(str(tmpdir), 'env-name', str(bootstrap_conf_path),
                            False)
    assert tmpdir.join('bootstrap.conf.d').isdir()
    assert tmpdir.join('bootstrap.conf.d').join('activate-env-name.conf').isfile()
    records = caplog.records
    assert None != re.search('source {0}'.format(str(bootstrap_conf_path)),
                             records[0].message)
    assert None != re.search('bootstrap-activate {0}'.format('env-name'),
                             records[0].message)
    assert None != re.search('bootstrap-deactivate'.format('env-name'),
                             records[0].message)
    assert len([i for i in records if i.name == 'stdout']) == 1
    shutil.rmtree(str(tmpdir))

def test_print_activate_command(caplog, tmpdir, environment):
    """Check env activation command if bootstrap is detected as loaded"""
    environment['BOOTSTRAP_ACTIVATE'] = '1'
    from bootstrap import _print_activate_command
    bootstrap_conf_path = tmpdir.join('bootstrap.conf')
    _print_activate_command(str(tmpdir), 'env-name', str(bootstrap_conf_path),
                            False)
    assert tmpdir.join('bootstrap.conf.d').isdir()
    assert tmpdir.join('bootstrap.conf.d').join('activate-env-name.conf').isfile()
    records = caplog.records
    assert None == re.search('source {0}'.format(str(bootstrap_conf_path)),
                             records[1].message)
    assert None != re.search('bootstrap-activate {0}'.format('env-name'),
                             records[1].message)
    assert None != re.search('bootstrap-deactivate'.format('env-name'),
                             records[1].message)
    assert len([i for i in records if i.name == 'stdout']) == 1
    shutil.rmtree(str(tmpdir))

def test_print_activate_command_conda(caplog, tmpdir):
    """Check env activation command if bootstrap scripts are skipped"""
    from bootstrap import _print_activate_command
    bootstrap_conf_path = tmpdir.join('bootstrap.conf')
    _print_activate_command(str(tmpdir), 'env-name', str(bootstrap_conf_path),
                            True)
    assert not tmpdir.join('bootstrap.conf.d').isdir()
    assert not tmpdir.join('bootstrap.conf.d').join('activate-env-name.conf').isfile()
    records = caplog.records
    assert None == re.search(str(bootstrap_conf_path),
                             records[1].message)
    assert None != re.search(str(tmpdir.join('bin/activate')),
                             records[1].message)
    assert None != re.search('conda activate {0}'.format('env-name'),
                             records[1].message)
    assert None != re.search('conda deactivate'.format('env-name'),
                             records[1].message)
    assert len([i for i in records if i.name == 'stdout']) == 1
    shutil.rmtree(str(tmpdir))

def test_parser_env_bootstrap_path(environment, tmpdir):
    """Test BOOTSTRAP_PATH related args"""
    from bootstrap import _parser
    environment['BOOTSTRAP_PATH'] = str(tmpdir)
    p = _parser()
    args = p.parse_args([])
    # default name is defined from BOOTSTRAP_PATH basename
    assert tmpdir.basename == vars(args)['name']
    # default environment is defined from BOOTSTRAP_PATH basename
    assert str(tmpdir.join('environment.yml')) == vars(args)['environment']
    shutil.rmtree(str(tmpdir))

def test_parser_other_env(environment):
    """Test defaults from env for not interacting value"""
    from bootstrap import _parser
    environment['BOOTSTRAP_CONDA_PREFIX'] = 'fake-prefix'
    environment['BOOTSTRAP_CONDA_ENVYML'] = 'fake-environment.yml'
    environment['BOOTSTRAP_NAME'] = 'env-name'
    p = _parser()
    args = p.parse_args([])
    assert 'env-name' == vars(args)['name']
    assert 'fake-environment.yml' == vars(args)['environment']
    assert 'fake-prefix' == vars(args)['prefix']

def test_parser_defaults():
    from bootstrap import _parser
    p = _parser()
    args = p.parse_args([])
    assert False == vars(args)['reset_conda']
    assert False == vars(args)['reset_env']
    assert '~/.miniconda2' == vars(args)['prefix']
    assert '~/.profile.d/bootstrap.conf' == vars(args)['profile_dir']
    assert False == vars(args)['skip_activate_script']

def test_default_bootstrap_name(tmpdir):
    from bootstrap import _default_bootstrap_name
    # bootstrap name is bootstrap path basename
    assert tmpdir.basename == _default_bootstrap_name(str(tmpdir))
    # 'bootstrap' folders are ignored to search bootstrap name
    bootstrap = tmpdir.join('bootstrap')
    bootstrap.mkdir()
    assert tmpdir.basename == _default_bootstrap_name(str(bootstrap))
    shutil.rmtree(str(tmpdir))

# TODO: test basic conda commands

def _success_script(lpath):
    lpath.write("#! /bin/bash\nexit 0\n", ensure=True)
    lpath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

def _error_script(lpath):
    lpath.write("#! /bin/bash\necho error_str\nexit 1\n",
                ensure=True)
    lpath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

def _fake_conda_script(lpath, create_status, list_status, install_status,
                       remove_status):
    lpath.write("""#! /bin/bash
[ "$1" == "create" ] && exit {0};
[ "$1" == "list" ] && exit {1};
[ "$2" == "update" ] && exit {2};
[ "$2" == "remove" ] && exit {2};
""".format(create_status, list_status, install_status), ensure=True)
    lpath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

def _fake_activate_script(lpath):
    lpath.write("""#! /bin/bash
conda () {{
    if [ "$1" == "activate" ]; then
        echo "env $2 activated"
        return 0;
    fi
}}
""".format(), ensure=True)
    lpath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
