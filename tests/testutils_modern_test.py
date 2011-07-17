import sys
import testutils
import unittest

class ModernClass(object):
  """Contains features only available in 2.6 and above."""
  def test_testutils_should_support_with(self):
    foo = fake(foo='bar')
    with foo as mock:
      assert mock.bar() == 'baz'

  def test_builtin_open(self):
    if sys.version_info < (3, 0):
      mock = wrap(sys.modules['__builtin__'])
    else:
      mock = wrap(sys.modules['builtins'])
    mock.open.calls_original()
    mock.open('file_name').x(1).returns(fake(read=lambda: 'some data'))
    with open('file_name') as f:
      data = f.read()
    self.assertEqual('some data', data)



class TestutilsUnittestModern(ModernClass, unittest.TestCase):
  def _tear_down(self):
    return unittest.TestCase.tearDown(self)


if __name__ == '__main__':
  unittest.main()
