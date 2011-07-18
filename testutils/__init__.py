"""Copyright 2011 Herman Sheremetyev. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are
permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice, this list of
      conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice, this list
      of conditions and the following disclaimer in the documentation and/or other materials
      provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


import sys

from testutils.fake import Fake
from testutils.helpers import _match_args
from testutils.wrap import Wrap


# Holds global hash of object/expectation mappings
_testutils_objects = {}


def wrap(spec, **kwargs):
    """Wraps an object in order to manipulate its methods.
 
    Examples:
        >>> wrap(SomeClass).some_method.returns('stuff')
 
    Args:
        - spec: object (or class or module) to mock
        - kwargs: method/return_value pairs to attach to the object
 
    Returns:
        Wrap object
    """
    matches = [x for x in _testutils_objects if x.__object__ is spec]
    if matches:
        mock = matches[0]
    else:
        mock = Wrap(spec, **kwargs)
    return mock


def fake(**kwargs):
    """Creates a fake object.
 
    Populates the returned object's attribute/value pairs based on
    keyword arguments provided.
    """
    return Fake(**kwargs)


def _teardown():
    """Performs testuitls-specific teardown tasks."""
 
    saved = {}
    for mock_object, expectations in _testutils_objects.items():
        saved[mock_object] = expectations[:]
        for expectation in expectations:
            expectation._reset()
    for mock_object in saved:
        del _testutils_objects[mock_object]
    # make sure this is done last to keep exceptions here from breaking
    # any of the previous steps that cleanup all the changes
    for mock_object, expectations in saved.items():
        for expectation in expectations:
            expectation._verify()


def _get_expectation(obj, name=None, args=None):
    """Gets attached to the object under mock and is called in that context."""
    if args == None:
        args = {'kargs': (), 'kwargs': {}}
    if not isinstance(args, dict):
        args = {'kargs': args, 'kwargs': {}}
    if not isinstance(args['kargs'], tuple):
        args['kargs'] = (args['kargs'],)
    if name and obj in _testutils_objects:
        for e in reversed(_testutils_objects[obj]):
            if e.method == name and _match_args(args, e.args):
                if e._ordered:
                    e._verify_call_order()
                return e


def _add_expectation(obj, expectation):
    if obj in _testutils_objects:
        _testutils_objects[obj].append(expectation)
    else:
        _testutils_objects[obj] = [expectation]


# RUNNER INTEGRATION


def _hook_into_pytest():
    try:
        from _pytest import runner
        saved = runner.call_runtest_hook
        def call_runtest_hook(item, when):
            ret = saved(item, when)
            teardown = runner.CallInfo(_teardown, when=when)
            if when == 'call' and not ret.excinfo:
                teardown.result = None
                return teardown
            else:
                return ret
        runner.call_runtest_hook = call_runtest_hook
 
    except ImportError:
        pass
_hook_into_pytest()


def _hook_into_doctest():
    try:
        from doctest import DocTestRunner
        saved = DocTestRunner.run
        def run(self, test, compileflags=None, out=None, clear_globs=True):
            try:
                return saved(self, test, compileflags, out, clear_globs)
            finally:
                _teardown()
        DocTestRunner.run = run
    except ImportError:
        pass
_hook_into_doctest()


def _update_unittest(klass):
    saved_stopTest = klass.stopTest
    saved_addSuccess = klass.addSuccess
    def stopTest(self, test):
        try:
            _teardown()
            saved_addSuccess(self, test)
        except:
            if hasattr(self, '_pre_testutils_success'):
                self.addError(test, sys.exc_info())
        return saved_stopTest(self, test)
    klass.stopTest = stopTest

    def addSuccess(self, test):
        self._pre_testutils_success = True
    klass.addSuccess = addSuccess


def _hook_into_unittest():
    try:
        import unittest
        try:
            from unittest import TextTestResult as TestResult
        except ImportError:
            from unittest import _TextTestResult as TestResult
        _update_unittest(TestResult)
    except ImportError:
        pass
_hook_into_unittest()
