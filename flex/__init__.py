"""Copyright 2011 Herman Sheremetyev. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

   1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

   2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.  """


import sys

from flex.fake import Fake
from flex.helpers import _match_args
from flex.helpers import _get_code
from flex.wrap import _flex_objects
from flex.wrap import Wrap


def flex(spec, **kwargs):
    """Wraps an object in order to manipulate its methods.

    Examples:
        >>> wrap(SomeClass).some_method.returns('stuff')

    Args:
        - spec: object (or class or module) to mock
        - kwargs: method/return_value pairs to attach to the object

    Returns:
        Wrap object
    """
    matches = [x for x in _flex_objects if x.__object__ is spec]
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


def verify():
    """Performs flex-specific teardown tasks."""

    saved = {}
    for mock_object, expectations in _flex_objects.items():
        saved[mock_object] = expectations[:]
        for expectation in expectations:
            expectation._reset()
    for mock_object in saved:
        del _flex_objects[mock_object]
    # make sure this is done last to keep exceptions here from breaking
    # any of the previous steps that cleanup all the changes
    for mock_object, expectations in saved.items():
        for expectation in expectations:
            expectation._verify()


# RUNNER INTEGRATION


def _hook_into_pytest():
    try:
        from _pytest import runner
        saved = runner.call_runtest_hook
        def call_runtest_hook(item, when):
            ret = saved(item, when)
            teardown = runner.CallInfo(verify, when=when)
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
                verify()
        DocTestRunner.run = run
    except ImportError:
        pass
_hook_into_doctest()


def _patch_test_result(klass):
    """Patches flex verify() into any class that inherits unittest.TestResult.

    This seems to work well for majority of test runners. In the case of nose
    it's not even necessary as it doesn't override unittest.TestResults's
    addSuccess and addFailure methods so simply patching unittest works out of
    the box for nose.

    For those that do inherit from unittest.TestResult and override its
    stopTest and addSuccess methods, patching is pretty straightforward
    (numerous examples below).

    The reason we don't simply patch unittest's parent TestResult class is
    stopTest and addSuccess in the child classes tend to add messages into the
    output that we want to override in case flex generates its own failures.
    """

    saved_addSuccess = klass.addSuccess
    saved_stopTest = klass.stopTest

    def addSuccess(self, test):
        self._pre_flex_success = True

    def stopTest(self, test):
        if _get_code(saved_stopTest) is not _get_code(stopTest):
            # if parent class was for some reason patched, avoid calling
            # verify() twice and delegate up the class hierarchy
            # this doesn't help if there is a gap and only the parent's
            # parent class was patched, but should cover most screw-ups
            try:
                verify()
                saved_addSuccess(self, test)
            except:
                if hasattr(self, '_pre_flex_success'):
                    self.addFailure(test, sys.exc_info())
            if hasattr(self, '_pre_flex_success'):
                del self._pre_flex_success
        return saved_stopTest(self, test)

    if klass.stopTest is not stopTest:
        klass.stopTest = stopTest

    if klass.addSuccess is not addSuccess:
        klass.addSuccess = addSuccess


def _hook_into_unittest():
    import unittest
    try:
        try:
            # only valid TestResult class for unittest is TextTestResult
            _patch_test_result(unittest.TextTestResult)
        except AttributeError:
            # ugh, python2.4
            _patch_test_result(unittest._TextTestResult)
    except: # let's not take any chances
        pass
_hook_into_unittest()


def _hook_into_unittest2():
    try:
        try:
            from unittest2 import TextTestResult
        except ImportError:
            # Django has its own copy of unittest2 it uses as fallback
            from django.utils.unittest import TextTestResult
        _patch_test_result(TextTestResult)
    except:
        pass
_hook_into_unittest2()


def _hook_into_twisted():
    try:
        from twisted.trial import reporter
        _patch_test_result(reporter.MinimalReporter)
        _patch_test_result(reporter.TextReporter)
        _patch_test_result(reporter.VerboseTextReporter)
        _patch_test_result(reporter.TreeReporter)
    except:
        pass
_hook_into_twisted()


def _hook_into_subunit():
    try:
        import subunit
        _patch_test_result(subunit.TestProtocolClient)
    except:
        pass
_hook_into_subunit()


def _hook_into_zope():
    try:
        from zope import testrunner
        _patch_test_result(testrunner.runner.TestResult)
    except:
        pass
_hook_into_zope()


def _hook_into_testtools():
    try:
        from testtools import testresult
        _patch_test_result(testresult.TestResult)
    except:
        pass
_hook_into_testtools()
