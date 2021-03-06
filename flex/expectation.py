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


from flex.exceptions import CallOrderError
from flex.exceptions import FlexError
from flex.exceptions import MethodCallError
from flex.helpers import _arg_to_str
from flex.helpers import _format_args
from flex.helpers import _isclass
from flex.helpers import _match_args


AT_LEAST = 'at least'
AT_MOST = 'at most'
EXACTLY = 'exactly'


class ReturnValue(object):
    def __init__(self, value=None, raises=None):
        self.value = value
        self.raises = raises

    def __str__(self):
        if self.raises:
            return '%s(%s)' % (self.raises, _arg_to_str(self.value))
        else:
            return _arg_to_str(self.value)


class Expectation(object):
    """Holds expectations about methods.

    The information contained in the Expectation object includes method name,
    its argument list, return values, and any exceptions that the method might
    raise.
    """

    def __init__(self, mock, name=None, return_value=None, original_method=None):
        self.mock = mock
        self.method = name
        self.original_method = original_method
        self.args = None
        value = ReturnValue(return_value)
        self._action = {
            'return_values': [],
            'yield_values': []
        }
        return_values = self._action['return_values']
        if return_value is not None:
            return_values.append(value)
        self._replace_with = None
        self._times_called = 0
        self._expected_calls = {EXACTLY: None, AT_LEAST: None, AT_MOST: None}
        self._runnable = lambda: True
        self._pass_thru = False
        self._ordered = False
        self._verified = False

    def __str__(self):
        return ('%s -> (%s)' %
                (_format_args(self.method, self.args),
                ', '.join(['%s' % x for x in self._action['return_values']])))

    def __call__(self, *kargs, **kwargs):
        if self.args:
            self.__raise(FlexError, 'Arguments can only be specified once')

        self.args = {'kargs': kargs, 'kwargs': kwargs}
        return self

    def __getattr__(self, name):
        self.__raise(
            AttributeError, "'%s' object has not attribute '%s'" %
                (self.__class__.__name__, name))

    def returns(self, *values):
        """Override the return value of this expectation's method.

        Provided return values are returned on successive invocations of the
        method. When returns() is given multiple times, each additional
        value is added to the return value list.
        
        It is possible to mix returns() with raises() to alternate between
        returning a value and raising and exception on different method
        invocations.

        Args:
            - values: optional list of return values, defaults to None

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        replace_with = self._replace_with
        if replace_with:
            self.__raise(
                FlexError, 'returns() cannot be specified after runs()')
        return_values = self._action['return_values']
        if not values:
            return_values.append(ReturnValue())
        for value in values:
            return_values.append(ReturnValue(value))
        return self

    def raises(self, exception, *kargs, **kwargs):
        """Specifies the exception to be raised when this expectation is met.

        Args:
            - exception: class or instance of the exception
            - kargs: optional keyword arguments to pass to the exception
            - kwargs: optional named arguments to pass to the exception

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        replace_with = self._replace_with
        if replace_with:
            self.__raise(
                FlexError, 'raises() cannot be specified after runs()')
        args = {'kargs': kargs, 'kwargs': kwargs}
        return_values = self._action['return_values']
        return_values.append(ReturnValue(raises=exception, value=args))
        return self

    def yields(self, *values):
        """Turns the return value into a generator.

        Each value provided is yielded on successive calls to next().

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        replace_with = self._replace_with
        if replace_with:
            self.__raise(FlexError, 'yields() cannot be specified after runs()')
        yield_values = self._action['yield_values']
        for value in values:
            yield_values.append(ReturnValue(value))
        return self

    def runs(self, function=None):
        """Gives a function to run instead of the mocked out one.

        Args:
            - function: callable (defaults to function being replaced)

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        if [val for _, val in self._action.items() if val]:
            self.__raise(FlexError, 'runs() cannot be mixed with return values')
        if not function:
            function = self.original_method
        replace_with = self._replace_with
        original_method = self.original_method
        if replace_with:
            self.__raise(FlexError, 'runs() cannot be specified twice')
        obj = self.mock._Flex__object
        func_type = type(function)
        if _isclass(obj):
            if func_type is not classmethod and func_type is not staticmethod:
                self.__raise(
                    FlexError, 'calls() cannot be used on a class mock')
        if function == original_method:
            self._pass_thru = True
        self._replace_with = function
        return self

    def times(self, start, end=0):
        """Number of times this expectation's method is expected to be called.

        Args:
            - start: int
            - end: int

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        expected_calls = self._expected_calls
        if end is None:
            expected_calls[AT_LEAST] = start
        elif end <= start:
            expected_calls[EXACTLY] = start
        else:
            expected_calls[AT_LEAST] = start
            expected_calls[AT_MOST] = end
        return self

    def ordered(self):
        """Makes the expectation respect the order of method statements.

        An exception will be raised if methods are called out of order,
        determined by order of method calls in the test.

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        self._ordered = True
        return self

    def when(self, func):
        """Sets an outside resource to be checked before executing the method.

        Args:
            - func: function to call to check if the method should be executed

        Returns:
            - self, i.e. can be chained with other Expectation methods
        """
        if not hasattr(func, '__call__'):
            self.__raise(FlexError, 'when() parameter must be callable')
        self._runnable = func
        return self

    def _verify(self, final=True):
        """Verify that this expectation has been met.

        Args:
            final: boolean, True if no further calls to this method expected
            (skip checking at_least expectations when False)

        Raises:
            CallOrderError
        """
        if self._verified:
            return  # ensure we only raise one error per failed expectation
        failed = False
        message = ''
        expected_calls = self._expected_calls
        if expected_calls[EXACTLY] is not None:
            message = 'exactly %s' % expected_calls[EXACTLY]
            if final:
                if self._times_called != expected_calls[EXACTLY]:
                    failed = True
            else:
                if self._times_called > expected_calls[EXACTLY]:
                    failed = True
        else:
            if final and expected_calls[AT_LEAST] is not None:
                message = 'at least %s' % expected_calls[AT_LEAST]
                if self._times_called < expected_calls[AT_LEAST]:
                    failed = True
            if expected_calls[AT_MOST] is not None:
                if message:
                    message += ' and '
                message += 'at most %s' % expected_calls[AT_MOST]
                if self._times_called > expected_calls[AT_MOST]:
                    failed = True
        if not failed:
            return
        else:
            self._verified = True
            self.__raise(
                MethodCallError,
                '%s expected to be called %s times, called %s times' %
                    (_format_args(self.method, self.args),
                    message,
                    self._times_called))

    def _reset(self):
        """Returns methods overriden by this expectation to their originals."""
        obj = self.mock._Flex__object
        original_method = self.original_method
        if original_method:
            method = self.method
            if (hasattr(obj, '__dict__') and
                    method in obj.__dict__ and
                    type(obj.__dict__) is dict):
                del obj.__dict__[method]
                if not hasattr(obj, method):
                    obj.__dict__[method] = original_method
            else:
                setattr(obj, method, original_method)
        del self

    def _verify_call_order(self, flex_objects):
        for exp in flex_objects[self.mock]:
            if (exp.method == self.method and
                    not _match_args(self.args, exp.args) and
                    not exp._times_called):
                raise CallOrderError(
                        '%s called before %s' %
                        (_format_args(self.method, self.args),
                         _format_args(exp.method, exp.args)))
            if (exp.method == self.method and
                    self.args and exp.args and    # ignore default stub case
                    _match_args(self.args, exp.args)):
                break

    def __raise(self, exception, message):
        """Safe internal raise implementation.

        In case we're patching builtins, it's important to reset the
        expectation before raising any exceptions or else things like
        open() might be stubbed out and the resulting runner errors are very
        difficult to diagnose.
        """
        self._reset()
        raise exception(message)
