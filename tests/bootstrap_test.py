#! /bin/env python2
# -*- encoding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4 expandtab ai

def test_run_standard(capfd):
    """Run a command (success)"""
    from bootstrap import _run
    args = ['echo', '-n', 'hello', 'world']
    debug = False
    _run(args, debug=debug, env={})
    captured = capfd.readouterr()
    print(captured)
    assert 'hello world' == captured.out
    
