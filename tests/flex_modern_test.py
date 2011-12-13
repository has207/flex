import sys
from flex import fake, flex
import unittest

class ModernClass(object):
    """Contains features only available in 2.6 and above."""

    def test_flex_should_support_with(self):
        foo = fake(foo='bar')
        with foo as mock:
            assert mock.bar() == 'baz'

    def test_builtin_open(self):
        if sys.version_info < (3, 0):
            mock = flex(sys.modules['__builtin__'])
        else:
            mock = flex(sys.modules['builtins'])
        mock.open.runs()
        mock.open('file_name').returns(fake(read=lambda: 'some data')).times(1)
        with open('file_name') as f:
            data = f.read()
        self.assertEqual('some data', data)


class FlexUnittestModern(ModernClass, unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
