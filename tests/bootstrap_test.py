#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

def test_run_standard(capfd):
    """Run a command, no extra args (success)"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    _run(args)
    captured = capfd.readouterr()
    assert 'hello world' == captured.out

def test_run_stderr(capfd):
    """Run a command with output on stderr (success)"""
    from bootstrap import _run
    args = ' '.join(['>&2', 'echo', '-n', 'hello', 'world'])
    _run(args, shell=True)
    captured = capfd.readouterr()
    assert 'hello world' == captured.err

def test_run_env(capfd):
    """Run a command that print a var from environment"""
    from bootstrap import _run
    args = ['printenv', 'TEST']
    _run(args, env={'TEST': 'VALUE'})
    captured = capfd.readouterr()
    assert 'VALUE\n' == captured.out

def test_run_debug(capfd):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    debug = True
    _run(args, debug=debug)
    captured = capfd.readouterr()
    assert '[cmd] echo -n hello world\n' == captured.err
    assert 'hello world' == captured.out

def test_run_debug_env(capfd):
    """Debug a command"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    debug = True
    import collections
    # use an ordered dict so that debug output is deterministic
    env = collections.OrderedDict([['TEST1', 'VALUE1'], ['TEST2', 'VALUE2']])
    _run(args, debug=debug, env=env)
    captured = capfd.readouterr()
    assert '[cmd] echo -n hello world\n' \
            + '[cmd] env:TEST1=VALUE1 TEST2=VALUE2\n' == captured.err
    assert 'hello world' == captured.out
