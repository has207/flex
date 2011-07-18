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


import inspect
import sys
import types

from testutils.helpers import _arguments_match
from testutils.helpers import _isclass
from testutils.helpers import _format_args
from testutils.helpers import _match_args
from testutils.expectation import Expectation
from testutils.expectation import ReturnValue
from testutils.exceptions import *


# Holds global hash of object/expectation mappings
_testutils_objects = {}


class Wrap(object):
    """Wrap object class returned by the wrap() function."""

    def __init__(self, spec, **methods):
        """Wrap constructor.

        Args:
            - spec: object, class or module to wrap
            - methods: dict of method/return_value pairs used
              to stub out multiple methods at the same time with specified
              return values
        """
        self.__object__ = spec
        for method, return_value in methods.items():
            self._stubs(method).returns(return_value)
        self._add_expectation(Expectation(self))

    def __getattribute__(self, name):
        # TODO(herman): this sucks, generalize this!
        if name == '__new__':
            if _isclass(self.__object__):
                raise AttributeError
            else:
                raise TestutilsError('__new__ can only be replaced on classes')
        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        return self._stubs(name)

    def _stubs(self, method):
        """Replaces a method with a fake one.

        Args:
            - method: string name of the method to stub

        Returns:
            - Expectation object
        """
        obj = object.__getattribute__(self, '__object__')
        return_value = None
        if (method.startswith('__') and not method.endswith('__') and
                not inspect.ismodule(obj)):
            if _isclass(obj):
                name = obj.__name__
            else:
                name = obj.__class__.__name__
            method = '_%s__%s' % (name, method.lstrip('_'))
        if not isinstance(obj, Wrap) and not hasattr(obj, method):
            raise MethodDoesNotExist('%s does not have method %s' %
                                     (obj, method))
        if self not in _testutils_objects:
            _testutils_objects[self] = []
        expectation = self._create_expectation(method, return_value)
        if expectation not in _testutils_objects[self]:
            try:
                self._update_method(expectation, method)
                _testutils_objects[self].append(expectation)
            except TypeError:
                raise AttemptingToMockBuiltin(
                    'Python does not allow updating builtin objects. '
                    'Consider wrapping it in a class you can mock instead')
            except AttributeError:
                raise AttemptingToMockBuiltin(
                    'Python does not allow updating instances of builtins. '
                    'Consider wrapping it in a class you can mock instead')
        return expectation

    def _create_expectation(self, method, return_value=None):
        if method in [x.method for x in _testutils_objects[self]]:
            expectation = [x for x in _testutils_objects[self]
                           if x.method == method][0]
            original_method = expectation.original_method
            expectation = Expectation(
                    self, name=method, return_value=return_value,
                    original_method=original_method)
        else:
            expectation = Expectation(
                self, name=method, return_value=return_value)
        return expectation

    def _update_method(self, expectation, method):
        obj = object.__getattribute__(self, '__object__')
        original_method = expectation.original_method
        meth = object.__getattribute__(self, '_create_mock_method')(method)
        if hasattr(obj, method) and not original_method:
            if hasattr(obj, '__dict__') and method in obj.__dict__:
                expectation.original_method = obj.__dict__[method]
            else:
                expectation.original_method = getattr(obj, method)
            method_type = type(expectation.original_method)
            if method_type is classmethod or method_type is staticmethod:
                expectation.original_function = getattr(obj, method)
        if hasattr(obj, '__dict__') and type(obj.__dict__) is dict:
            obj.__dict__[method] = types.MethodType(meth, obj)
        else:
            setattr(obj, method, types.MethodType(meth, obj))

    def _create_mock_method(self, method):
        def generator_method(yield_values):
            for value in yield_values:
                yield value.value

        def _handle_exception_matching(expectation):
            return_values = expectation.return_values
            if return_values:
                raised, instance = sys.exc_info()[:2]
                message = '%s' % instance
                expected = return_values[0].raises
                if not expected:
                    raise
                args = return_values[0].value
                expected_instance = expected(*args['kargs'], **args['kwargs'])
                expected_message = '%s' % expected_instance
                if _isclass(expected):
                    if (expected is not raised and
                        expected not in raised.__bases__):
                        raise (InvalidExceptionClass('expected %s, raised %s' %
                                     (expected, raised)))
                    if (args['kargs'] and
                        '_sre.SRE_Pattern' in str(args['kargs'][0])):
                        if not args['kargs'][0].search(message):
                            raise (InvalidExceptionMessage(
                                'expected /%s/, raised "%s"' %
                                (args['kargs'][0].pattern, message)))
                    elif expected_message and expected_message != message:
                        raise (InvalidExceptionMessage(
                            'expected "%s", raised "%s"' %
                            (expected_message, message)))
                elif expected is not raised:
                    raise (InvalidExceptionClass('expected "%s", raised "%s"' %
                                 (expected, raised)))
            else:
                raise

        def match_return_values(expected, received):
            if not received:
                return True
            if not isinstance(expected, tuple):
                expected = (expected,)
            if not isinstance(received, tuple):
                received = (received,)
            if len(received) != len(expected):
                return False
            for i, val in enumerate(received):
                if not _arguments_match(val, expected[i]):
                    return False
            return True

        def pass_thru(expectation, *kargs, **kwargs):
            return_values = None
            try:
                original_method = expectation.original_method
                _mock = expectation._mock
                obj = object.__getattribute__(_mock, '__object__')
                if _isclass(obj):
                    if (type(original_method) is classmethod or
                            type(original_method) is staticmethod):
                        original = expectation.original_function
                        return_values = original(*kargs, **kwargs)
                else:
                    return_values = original_method(*kargs, **kwargs)
            except:
                return _handle_exception_matching(expectation)
            expected_values = expectation.return_values
            if (expected_values and
                    not match_return_values(expected_values[0].value,
                                            return_values)):
                raise (InvalidMethodSignature(
                    'expected to return %s, returned %s' %
                    (expected_values[0].value, return_values)))
            return return_values

        def mock_method(runtime_self, *kargs, **kwargs):
            arguments = {'kargs': kargs, 'kwargs': kwargs}
            expectation = self._get_expectation(method, arguments)
            if expectation:
                if not expectation.runnable():
                    raise InvalidState(
                        '%s expected to be called when %s is True' %
                        (method, expectation.runnable))
                expectation.times_called += 1
                _pass_thru = expectation._pass_thru
                _replace_with = expectation._replace_with
                if _pass_thru:
                    return pass_thru(expectation, *kargs, **kwargs)
                elif _replace_with:
                    return _replace_with(*kargs, **kwargs)
                yield_values = expectation.yield_values
                return_values = expectation.return_values
                if yield_values:
                    return generator_method(yield_values)
                elif return_values:
                    return_value = return_values[0]
                    del return_values[0]
                    return_values.append(return_value)
                else:
                    return_value = ReturnValue()
                if return_value.raises:
                    if _isclass(return_value.raises):
                        raise return_value.raises(
                                *return_value.value['kargs'],
                                **return_value.value['kwargs'])
                    else:
                        raise return_value.raises
                else:
                    return return_value.value
            else:
                raise InvalidMethodSignature(_format_args(method, arguments))

        return mock_method

    def _get_expectation(self, name=None, args=None):
        """Gets attached to the object under mock and is called in that context."""
        if args == None:
            args = {'kargs': (), 'kwargs': {}}
        if not isinstance(args, dict):
            args = {'kargs': args, 'kwargs': {}}
        if not isinstance(args['kargs'], tuple):
            args['kargs'] = (args['kargs'],)
        if name and self in _testutils_objects:
            for e in reversed(_testutils_objects[self]):
                if e.method == name and _match_args(args, e.args):
                    if e._ordered:
                        e._verify_call_order(_testutils_objects)
                    return e


    def _add_expectation(self, expectation):
        if self in _testutils_objects:
            _testutils_objects[self].append(expectation)
        else:
            _testutils_objects[self] = [expectation]
