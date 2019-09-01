#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

import os
import py
import pytest
import re
import shutil
import stat

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
        for key, value in self._orig:
            os.environ[key] = value

@pytest.fixture(scope="function")
def environment():
    """This fixture provides a variable to modify environment variables; when
    test finishes, modifications are erased"""
    environment = EnvOverrides()
    yield environment
    environment.restore()

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

def test_run_standard(capfd):
    """Run a command, no extra args (success)"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    _run(args)
    captured = capfd.readouterr()
    assert 'hello world' == _out(captured)

def test_run_stderr(capfd):
    """Run a command with output on stderr (success)"""
    from bootstrap import _run
    args = ' '.join(['>&2', 'echo', '-n', 'hello', 'world'])
    _run(args, shell=True)
    captured = capfd.readouterr()
    assert 'hello world' == _err(captured)

def test_run_env(capfd):
    """Run a command that print a var from environment"""
    from bootstrap import _run
    args = ['printenv', 'TEST']
    _run(args, env={'TEST': 'VALUE'})
    captured = capfd.readouterr()
    assert 'VALUE\n' == _out(captured)

def test_run_debug(capfd):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    debug = True
    _run(args, debug=debug)
    captured = capfd.readouterr()
    assert '[cmd] echo -n hello world\n' == _err(captured)
    assert 'hello world' == _out(captured)

def test_run_debug_env(capfd):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    debug = True
    import collections
    # use an ordered dict so that debug output is deterministic
    values = [['TEST1', 'VALUE1'], ['TEST2', 'VALUE2']]
    try:
        env = collections.OrderedDict(values)
    except AttributeError:
        # Python 2.6
        import ordereddict
        env = ordereddict.OrderedDict(values)
    _run(args, debug=debug, env=env)
    captured = capfd.readouterr()
    assert '[cmd] echo -n hello world\n' \
            + '[cmd] env:TEST1=VALUE1 TEST2=VALUE2\n' == _err(captured)
    assert 'hello world' == _out(captured)

def test_download_success(capfd, tmpdir):
    """check that download can be done, and the location of
    provided file"""
    from bootstrap import _download
    handle = _download('http://google.fr',
                       _tmpdir=str(tmpdir))
    # check that only one file is created in tempdir 
    assert len(tmpdir.listdir()) == 1
    # check that download file is child of tempdir
    assert tmpdir.common(py.path.local(handle[1])) == tmpdir
    captured = capfd.readouterr()
    #assert '' == _err(captured) #curl is verbose
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_download_error(capfd, tmpdir):
    from bootstrap import _download
    def f():
        _download('http://notexistingdomain.not',
                  _tmpdir=str(tmpdir))
    pytest.raises(Exception, f)
    # check that no file is created
    assert len(tmpdir.listdir()) == 0
    captured = capfd.readouterr()
    #assert '' == _err(captured) #curl is verbose
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_command():
    from bootstrap import _command
    assert ['/prefix/bin/command', 'param1', 'param2'] == \
            _command('/prefix', 'command', 'param1', 'param2')

def test_prepare_conda_not_existing(capfd, tmpdir):
    """If provided prefix is not existing, but parent of prefix exists,
    then nothing is done (prefix does not exist and parent directory is
    untouched)."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda')
    assert not conda.exists()
    _prepare_conda(str(conda), False)
    assert not conda.exists()
    captured = capfd.readouterr()
    assert '' == _err(captured)
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_existing(capfd, tmpdir):
    """If provided prefix exists, nothhing is done (prefix does not exist
    and parent directory is untouched)."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda').mkdir()
    _prepare_conda(str(conda), False)
    assert conda.exists()
    assert conda.isdir()
    captured = capfd.readouterr()
    assert '' == _err(captured)
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_subdir(capfd, tmpdir):
    """If prefix' parent directory does not exist, it is created. Prefix
    is not created."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda/subdir')
    _prepare_conda(str(conda), False)
    assert not conda.exists()
    assert conda.join('/..').isdir()
    captured = capfd.readouterr()
    assert '[INFO] Creating directory {0}\n'.format(str(conda.join('/..'))) == _err(captured)
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_reset_existing(capfd, tmpdir):
    """If existing conda prefix exists and reset=True, it is deleted."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda').mkdir()
    _prepare_conda(str(conda), True)
    assert not conda.exists() and conda.join('/..').exists()
    captured = capfd.readouterr()
    assert '[INFO] Destroying existing env {0}\n'.format(str(conda)) == _err(captured)
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_reset_invalid(capfd, tmpdir):
    """If existing conda prefix exists and reset=True, but cannot be deleted,
    an exception is raised."""
    from bootstrap import _prepare_conda
    conda = tmpdir.join('conda')
    conda.mkdir()
    os.chmod(str(tmpdir), ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    def f():
        _prepare_conda(str(conda), True)
    pytest.raises(Exception, f)
    captured = capfd.readouterr()
    assert '[INFO] Destroying existing env {0}\n'.format(str(conda)) == _err(captured)
    assert '' == _out(captured)
    os.chmod(str(tmpdir), stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
    shutil.rmtree(str(tmpdir))

def test_prepare_conda_parent_invalid(capfd, tmpdir):
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
    captured = capfd.readouterr()
    assert '[INFO] Creating directory {0}\n'.format(str(conda.join('/..'))) == _err(captured)
    assert '' == _out(captured)
    shutil.rmtree(str(tmpdir))

def test_skip_env_install_skip(capfd, tmpdir):
    """If no environment file, install is skipped"""
    from bootstrap import _skip_env_install
    env = tmpdir.join('environment')
    assert None == _skip_env_install(str(env))
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('Environment file .* missing', _err(captured))
    shutil.rmtree(str(tmpdir))

def test_skip_env_install_not_skip(capfd, tmpdir):
    """If environment file, return file path"""
    from bootstrap import _skip_env_install
    env = tmpdir.join('environment')
    env.ensure(file=True)
    assert str(env) == _skip_env_install(str(env))
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert '' == _err(captured)
    shutil.rmtree(str(tmpdir))

def test_skip_miniconda_skip(capfd, tmpdir):
    """If miniconda prefix exists, return True"""
    from bootstrap import _skip_miniconda
    assert True == _skip_miniconda(str(tmpdir))
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('--reset-conda', _err(captured))
    assert None != re.search('already exists', _err(captured))
    shutil.rmtree(str(tmpdir))

def test_skip_miniconda_skip(capfd, tmpdir):
    """If miniconda prefix exists, return True"""
    from bootstrap import _skip_miniconda
    prefix = tmpdir.join('prefix')
    assert False == _skip_miniconda(str(prefix))
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert '' == _err(captured)
    shutil.rmtree(str(tmpdir))

def test_env_exists_yes(capfd, tmpdir):
    """If environment is listed by conda, return True"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    assert True == _env_exists(str(tmpdir), 'test')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert '' == _err(captured)
    shutil.rmtree(str(tmpdir))

def test_env_exists_no(capfd, tmpdir):
    """If environment is not listed by conda, return False"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    assert False == _env_exists(str(tmpdir), 'test')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert '' == _err(captured)
    shutil.rmtree(str(tmpdir))

def test_env_exists_no_debug(capfd, tmpdir):
    """If environment is not listed by conda, return False"""
    from bootstrap import _env_exists
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    assert False == _env_exists(str(tmpdir), 'test', debug=True)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('Trigger .* creation', _err(captured))
    assert None != re.search('error_str', _err(captured))
    shutil.rmtree(str(tmpdir))

def test_env_remove_ok(capfd, tmpdir):
    from bootstrap import _env_remove
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_remove(str(tmpdir), 'test')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('removing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_remove_nok(capfd, tmpdir):
    from bootstrap import _env_remove
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_remove(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('removing', _err(captured), flags=re.I)
    assert None != re.search('error removing', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_create_ok(capfd, tmpdir):
    from bootstrap import _env_create
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_create(str(tmpdir), 'test')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('creating', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_create_nok(capfd, tmpdir):
    from bootstrap import _env_create
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_create(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('creating', _err(captured), flags=re.I)
    assert None != re.search('error creating', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_install_ok(capfd, tmpdir):
    from bootstrap import _env_install
    conda = tmpdir.join('bin/conda')
    _success_script(conda)
    _env_install(str(tmpdir), 'test', 'fakearg')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_env_install_nok(capfd, tmpdir):
    from bootstrap import _env_install
    conda = tmpdir.join('bin/conda')
    _error_script(conda)
    def f():
        _env_install(str(tmpdir), 'test', 'fakearg')
    e = pytest.raises(Exception, f)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('installing', _err(captured), flags=re.I)
    assert None != re.search('error installing', str(e.value), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_no_reset(capfd, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 1, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', False)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None == re.search('removing', _err(captured), flags=re.I)
    assert None == re.search('--reset-env', _err(captured), flags=re.I)
    assert None != re.search('creating', _err(captured), flags=re.I)
    assert None != re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_reset(capfd, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 0, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', True)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('removing', _err(captured), flags=re.I)
    assert None == re.search('--reset-env', _err(captured), flags=re.I)
    assert None != re.search('creating', _err(captured), flags=re.I)
    assert None != re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_exists(capfd, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 0, 0, 0)
    _handle_env(str(tmpdir), 'test', 'fakearg', False)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None == re.search('removing', _err(captured), flags=re.I)
    assert None != re.search('--reset-env', _err(captured), flags=re.I)
    assert None == re.search('creating', _err(captured), flags=re.I)
    assert None != re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_no_environment_file(capfd, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 1, 0, 0)
    _handle_env(str(tmpdir), 'test', None, False)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None == re.search('removing', _err(captured), flags=re.I)
    assert None == re.search('--reset-env', _err(captured), flags=re.I)
    assert None != re.search('creating', _err(captured), flags=re.I)
    assert None == re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_env_no_environment_file(capfd, tmpdir):
    from bootstrap import _handle_env
    conda = tmpdir.join('bin/conda')
    _fake_conda_script(conda, 0, 1, 0, 0)
    _handle_env(str(tmpdir), 'test', None, False)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None == re.search('removing', _err(captured), flags=re.I)
    assert None == re.search('--reset-env', _err(captured), flags=re.I)
    assert None != re.search('creating', _err(captured), flags=re.I)
    assert None == re.search('installing', _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_bootstrap_command(capfd, tmpdir, environment):
    from bootstrap import _handle_bootstrap_command
    command = 'echo bootstrap'
    environment['BOOTSTRAP_COMMAND'] = command
    activate = tmpdir.join('bin/activate')
    _fake_activate_script(activate)
    _handle_bootstrap_command(str(tmpdir), 'test')
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('running', _err(captured), flags=re.I)
    assert None != re.search(command, _err(captured), flags=re.I)
    shutil.rmtree(str(tmpdir))

def test_handle_bootstrap_command_ko(capfd, tmpdir, environment):
    from bootstrap import _handle_bootstrap_command
    command = 'false'
    environment['BOOTSTRAP_COMMAND'] = command
    activate = tmpdir.join('bin/activate')
    _fake_activate_script(activate)
    def f():
        _handle_bootstrap_command(str(tmpdir), 'test')
    e = pytest.raises(Exception, f)
    captured = capfd.readouterr()
    assert '' == _out(captured)
    assert None != re.search('running', _err(captured), flags=re.I)
    assert None != re.search(command, _err(captured), flags=re.I)
    assert None != re.search('error running', str(e.value), flags=re.I)
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
    return 0;
}}
""".format(), ensure=True)
    lpath.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
