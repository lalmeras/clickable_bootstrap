#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

import os
import py
import pytest
import shutil

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


