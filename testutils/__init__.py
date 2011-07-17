import sys

if sys.version_info < (3, 0):
  from testutils import *
  sys.modules['__builtin__'].wrap = wrap
  sys.modules['__builtin__'].fake = fake
else:
  from testutils.testutils import *
  sys.modules['builtins'].wrap = wrap
  sys.modules['builtins'].fake = fake


# RUNNER INTEGRATION


def _hook_into_pytest():
  try:
    from _pytest import runner
    saved = runner.call_runtest_hook
    def call_runtest_hook(item, when):
      ret = saved(item, when)
      _teardown = runner.CallInfo(teardown, when=when)
      if when == 'call' and not ret.excinfo:
        _teardown.result = None
        return _teardown
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
        teardown()
    DocTestRunner.run = run
  except ImportError:
    pass
_hook_into_doctest()


def _update_unittest(klass):
  saved_stopTest = klass.stopTest
  saved_addSuccess = klass.addSuccess
  def stopTest(self, test):
    try:
      teardown()
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
