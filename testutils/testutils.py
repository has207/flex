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
import os
import re
import sys
import types
import unittest
import warnings


AT_LEAST = 'at least'
AT_MOST = 'at most'
EXACTLY = 'exactly'


class TestutilsError(Exception):
  pass


class AttemptingToMockBuiltin(TestutilsError):
  pass


class InvalidMethodSignature(TestutilsError):
  pass


class InvalidExceptionClass(TestutilsError):
  pass


class InvalidExceptionMessage(TestutilsError):
  pass


class InvalidState(TestutilsError):
  pass


class MethodNotCalled(TestutilsError):
  pass


class MethodCalledOutOfOrder(TestutilsError):
  pass


class MethodDoesNotExist(TestutilsError):
  pass


class AlreadyMocked(TestutilsError):
  pass


class ReturnValue(object):
  def __init__(self, value=None, raises=None):
    self.value = value
    self.raises = raises

  def __str__(self):
    if self.raises:
      return '%s(%s)' % (self.raises, _arg_to_str(self.value))
    else:
      if len(self.value) == 1:
        return '%s' % _arg_to_str(self.value[0])
      else:
        return '(%s)' % ', '.join([_arg_to_str(x) for x in self.value])


class TestutilsContainer(object):
  """Holds global hash of object/expectation mappings."""
  testutils_objects = {}
  teardown_updated = []

  @classmethod
  def get_testutils_expectation(cls, obj, name=None, args=None):
    """Gets attached to the object under mock and is called in that context."""
    if args == None:
      args = {'kargs': (), 'kwargs': {}}
    if not isinstance(args, dict):
      args = {'kargs': args, 'kwargs': {}}
    if not isinstance(args['kargs'], tuple):
      args['kargs'] = (args['kargs'],)
    if name and obj in cls.testutils_objects:
      for e in reversed(cls.testutils_objects[obj]):
        if e.method == name and _match_args(args, e.args):
          if e._ordered:
            cls._verify_call_order(e, obj, args, name)
          return e

  @classmethod
  def _verify_call_order(cls, e, obj, args, name):
    for exp in cls.testutils_objects[obj]:
      if (exp.method == name and
          not _match_args(args, exp.args) and
          not exp.times_called):
        raise MethodCalledOutOfOrder(
            '%s called before %s' %
            (format_args(e.method, e.args),
             format_args(exp.method, exp.args)))
      if (exp.method == name and
          args and exp.args and  # ignore default stub case
          _match_args(args, exp.args)):
        break

  @classmethod
  def add_expectation(cls, obj, expectation):
    if obj in cls.testutils_objects:
      cls.testutils_objects[obj].append(expectation)
    else:
      cls.testutils_objects[obj] = [expectation]


class Expectation(object):
  """Holds expectations about methods.

  The information contained in the Expectation object includes method name,
  its argument list, return values, and any exceptions that the method might
  raise.
  """

  def __init__(self, mock, name=None, return_value=None, original_method=None):
    self.method = name
    self.original_method = original_method
    self.args = None
    value = ReturnValue(return_value)
    self.return_values = return_values = []
    self._replace_with = None
    if return_value is not None:
      return_values.append(value)
    self.yield_values = []
    self.times_called = 0
    self.expected_calls = {
        EXACTLY: None,
        AT_LEAST: None,
        AT_MOST: None}
    self.runnable = lambda: True
    self._mock = mock
    self._pass_thru = False
    self._ordered = False
    self._one_by_one = False

  def __str__(self):
    return '%s -> (%s)' % (format_args(self.method, self.args),
                           ', '.join(['%s' % x for x in self.return_values]))

  def __call__(self, *kargs, **kwargs):
    if self.args:
      raise TestutilsError('Arguments cannot be specified more than once')

    self.args = {'kargs': kargs, 'kwargs': kwargs}
    return self

  @property
  def mock(self):
    """Return the mock associated with this expectation.

    Since this method is a property it must be called without parentheses.
    """
    return self._mock

  def returns(self, *values):
    """Override the return value of this expectation's method.

    When and_return is given multiple times, each value provided is returned
    on successive invocations of the method. It is also possible to mix
    and_return with and_raise in the same manner to alternate between returning
    a value and raising and exception on different method invocations.

    When combined with the one_by_one property, value is treated as a list of
    values to be returned in the order specified by successive calls to this
    method rather than a single list to be returned each time.

    Args:
      - values: optional list of return values, defaults to None if not given

    Returns:
      - self, i.e. can be chained with other Expectation methods
    """
    if len(values) == 1:
      value = values[0]
    else:
      value = values
    return_values = self.return_values
    if not self._one_by_one:
      value = ReturnValue(value)
      return_values.append(value)
    else:
      try:
        return_values.extend([ReturnValue(v) for v in value])
      except TypeError:
        return_values.append(ReturnValue(value))
    return self

  def x(self, number, at_most=None):
    """Number of times this expectation's method is expected to be called.

    Args:
      - number: int

    Returns:
      - self, i.e. can be chained with other Expectation methods
    """
    expected_calls = self.expected_calls
    if number < 0:
      number = 0
    if at_most == None:
      expected_calls[EXACTLY] = number
    elif at_most < number:
      expected_calls[AT_LEAST] = number
    else:
      expected_calls[AT_LEAST] = number
      expected_calls[AT_MOST] = at_most
    return self

  def one_by_one(self):
    """Modifies the return value to be treated as a list of return values.

    Each value in the list is returned on successive invocations of the method.

    This is a property method so must be called without parentheses.

    Returns:
      - self, i.e. can be chained with other Expectation methods
    """
    if not self._one_by_one:
      self._one_by_one = True
      return_values = self.return_values
      saved_values = return_values[:]
      self.return_values = return_values = []
      for value in saved_values:
        try:
          for val in value.value:
            return_values.append(ReturnValue(val))
        except TypeError:
          return_values.append(value)
    return self


  def ordered(self):
    """Makes the expectation respect the order of method statements.

    An exception will be raised if methods are called out of order, determined
    by order of method calls in the test.

    This is a property method so must be called without parentheses.

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
    self.runnable = func
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
    args = {'kargs': kargs, 'kwargs': kwargs}
    return_values = self.return_values
    return_values.append(ReturnValue(raises=exception, value=args))
    return self

  def calls(self, function):
    """Gives a function to run instead of the mocked out one.

    Args:
      - function: callable

    Returns:
      - self, i.e. can be chained with other Expectation methods
    """
    replace_with = self._replace_with
    original_method = self.original_method
    if replace_with:
      raise TestutilsError('calls() cannot be specified twice')
    mock = self._mock
    obj = _getattr(mock, '__object__')
    func_type = type(function)
    if _isclass(obj):
      if func_type is not classmethod and func_type is not staticmethod:
        raise TestutilsError('calls() cannot be used on a class mock')
    if function == original_method:
      self._pass_thru = True
    self._replace_with = function
    return self

  def calls_original(self):
      return self.calls(self.original_method)

  def yields(self, *kargs):
    """Specifies the list of items to be yielded on successive method calls.

    In effect, the mocked object becomes a generator.

    Returns:
      - self, i.e. can be chained with other Expectation methods
    """
    yield_values = self.yield_values
    for value in kargs:
      yield_values.append(ReturnValue(value))
    return self

  def _verify(self):
    """Verify that this expectation has been met.

    Raises:
      MethodNotCalled Exception
    """
    failed = False
    message = ''
    expected_calls = self.expected_calls
    if expected_calls[EXACTLY] is not None:
      message = 'exactly %s' % expected_calls[EXACTLY]
      if self.times_called != expected_calls[EXACTLY]:
        failed = True
    else:
      if expected_calls[AT_LEAST] is not None:
        message = 'at least %s' % expected_calls[AT_LEAST]
        if self.times_called < expected_calls[AT_LEAST]:
          failed = True
      if expected_calls[AT_MOST] is not None:
        if message:
          message += ' and '
        message += 'at most %s' % expected_calls[AT_MOST]
        if self.times_called > expected_calls[AT_MOST]:
          failed = True
    if not failed:
      return
    else:
      raise MethodNotCalled(
          '%s expected to be called %s times, called %s times' %
          (format_args(self.method, self.args), message, self.times_called))

  def _reset(self):
    """Returns the methods overriden by this expectation to their originals."""
    _mock = self._mock
    if isinstance(_mock, Wrap):
      obj = _mock.__object__
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


class Wrap(object):
  """Wrap object class returned by the wrap() function."""

  def __init__(self, spec, **kwargs):
    """Wrap constructor.

    Args:
      - spec: object, class or module to wrap
      - kwargs: dict of attribute/value pairs used to initialize the fake object
    """
    self.__object__ = spec
    for method, return_value in kwargs.items():
      self._stubs(method).returns(return_value)

  def __getattribute__(self, name):
    # TODO(herman): this sucks, generalize this!
    if name == '__new__':
      if _isclass(self.__object__):
        raise AttributeError
      else:
        raise TestutilsError('__new__ can only be replaced on classes')
    return _getattr(self, name)

  def __getattr__(self, name):
    return self._stubs(name)

  def _stubs(self, method):
    """Adds a method Expectation for the provided class, instance or module.

    Args:
      - method: string name of the method to add

    Returns:
      - Expectation object
    """
    obj = _getattr(self, '__object__')
    return_value = None
    if (method.startswith('__') and not method.endswith('__') and
        not inspect.ismodule(obj)):
      if _isclass(obj):
        name = obj.__name__
      else:
        name = obj.__class__.__name__
      method = '_%s__%s' % (name, method.lstrip('_'))
    if not isinstance(obj, Wrap) and not hasattr(obj, method):
      raise MethodDoesNotExist('%s does not have method %s' % (obj, method))
    if self not in TestutilsContainer.testutils_objects:
      TestutilsContainer.testutils_objects[self] = []
    expectation = _getattr(
        self, '_create_expectation')(method, return_value)
    if expectation not in TestutilsContainer.testutils_objects[self]:
      try:
        _getattr(self, '_update_method')(expectation, method)
        TestutilsContainer.testutils_objects[self].append(expectation)
      except TypeError:
        raise AttemptingToMockBuiltin(
          'Python does not allow you to mock builtin objects or modules. '
          'Consider wrapping it in a class you can mock instead')
      except AttributeError:
        raise AttemptingToMockBuiltin(
          'Python does not allow you to mock instances of builtin objects. '
          'Consider wrapping it in a class you can mock instead')
    return expectation

  def _create_expectation(self, method, return_value=None):
    if method in [x.method for x in TestutilsContainer.testutils_objects[self]]:
      expectation = [x for x in TestutilsContainer.testutils_objects[self]
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
    method_instance = _getattr(self, '_create_mock_method')(method)
    obj = _getattr(self, '__object__')
    original_method = expectation.original_method
    if hasattr(obj, method) and not original_method:
      if hasattr(obj, '__dict__') and method in obj.__dict__:
        expectation.original_method = obj.__dict__[method]
      else:
        expectation.original_method = getattr(obj, method)
      method_type = type(expectation.original_method)
      if method_type is classmethod or method_type is staticmethod:
        expectation.original_function = getattr(obj, method)
    if hasattr(obj, '__dict__') and type(obj.__dict__) is dict:
      obj.__dict__[method] = types.MethodType(method_instance, obj)
    else:
      setattr(obj, method, types.MethodType(method_instance, obj))

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
          if expected is not raised and expected not in raised.__bases__:
            raise (InvalidExceptionClass('expected %s, raised %s' %
                   (expected, raised)))
          if args['kargs'] and '_sre.SRE_Pattern' in str(args['kargs'][0]):
            if not args['kargs'][0].search(message):
              raise (InvalidExceptionMessage('expected /%s/, raised "%s"' %
                     (args['kargs'][0].pattern, message)))
          elif expected_message and expected_message != message:
            raise (InvalidExceptionMessage('expected "%s", raised "%s"' %
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
        obj = _getattr(_mock, '__object__')
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
          not match_return_values(expected_values[0].value, return_values)):
        raise (InvalidMethodSignature('expected to return %s, returned %s' %
               (expected_values[0].value, return_values)))
      return return_values

    def mock_method(runtime_self, *kargs, **kwargs):
      arguments = {'kargs': kargs, 'kwargs': kwargs}
      expectation = TestutilsContainer.get_testutils_expectation(
          self, method, arguments)
      if expectation:
        if not expectation.runnable():
          raise InvalidState('%s expected to be called when %s is True' %
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
                *return_value.value['kargs'], **return_value.value['kwargs'])
          else:
            raise return_value.raises
        else:
          return return_value.value
      else:
        raise InvalidMethodSignature(format_args(method, arguments))

    return mock_method


class Fake(object):

  def __init__(self, **kwargs):
    """Fake constructor.

    Args:
      - kwargs: dict of attribute/value pairs used to initialize the fake object
    """
    self.__calls__ = []
    for attr, value in kwargs.items():
      if hasattr(value, '__call__'):
        setattr(self, attr, self._recordable(value))
      else:
        setattr(self, attr, value)

  def __enter__(self):
    return self.__object__

  def __exit__(self, type, value, traceback):
    return self

  def __call__(self, *kargs, **kwargs):
    calls = _getattr(self, '__calls__')
    if calls:
      call = calls[-1]
      call['kargs'] = kargs
      call['kwargs'] = kwargs
      call['returned'] = self
    return self

  def __getattribute__(self, name):
    attr = _getattr(self, name)
    if name not in ORIGINAL_FAKE_ATTRS:
      calls = _getattr(self, '__calls__')
      calls.append({'name': name, 'returned': attr})
    return attr

  def __getattr__(self, name):
    calls = _getattr(self, '__calls__')
    calls.append({'name': name, 'returned': self})
    return self

  def _recordable(self, func):
    def inner(*kargs, **kwargs):
      calls = _getattr(self, '__calls__')
      if not calls:
        return func(*kargs, **kwargs)
      else:
        call = calls[-1]
        call['kargs'] = kargs
        call['kwargs'] = kwargs
        try:
          ret = func(*kargs, **kwargs)
          call['returned'] = ret
          return ret
        except:
          call['raised'] = sys.exc_info()
          del call['returned']
          raise
    return inner


ORIGINAL_FAKE_ATTRS = dir(Fake) + ['__calls__']


def _arg_to_str(arg):
  if '_sre.SRE_Pattern' in str(type(arg)):
    return '/%s/' % arg.pattern
  if sys.version_info < (3, 0):
    # prior to 3.0 unicode strings are type unicode that inherits
    # from basestring along with str, in 3.0 both unicode and basestring
    # go away and str handles everything properly
    if isinstance(arg, basestring):
      return '"%s"' % arg
    else:
      return '%s' % arg
  else:
    if isinstance(arg, str):
      return '"%s"' % arg
    else:
      return '%s' % arg


def format_args(method, arguments):
  if arguments is None:
    arguments = {'kargs': (), 'kwargs': {}}
  kargs = ', '.join(_arg_to_str(arg) for arg in arguments['kargs'])
  kwargs = ', '.join('%s=%s' % (k, _arg_to_str(v)) for k, v in
                                arguments['kwargs'].items())
  if kargs and kwargs:
    args = '%s, %s' % (kargs, kwargs)
  else:
    args = '%s%s' % (kargs, kwargs)
  return '%s(%s)' % (method, args)


def _get_code(func):
  if hasattr(func, 'func_code'):
    code = 'func_code'
  elif hasattr(func, 'im_func'):
    func = func.im_func
    code = 'func_code'
  else:
    code = '__code__'
  return getattr(func, code)


def _match_args(given_args, expected_args):
  if (given_args == expected_args or expected_args is None):
    return True
  if (len(given_args['kargs']) != len(expected_args['kargs']) or
      len(given_args['kwargs']) != len(expected_args['kwargs']) or
      given_args['kwargs'].keys() != expected_args['kwargs'].keys()):
    return False
  for i, arg in enumerate(given_args['kargs']):
    if not _arguments_match(arg, expected_args['kargs'][i]):
      return False
  for k, v in given_args['kwargs'].items():
    if not _arguments_match(v, expected_args['kwargs'][k]):
      return False
  return True


def _arguments_match(arg, expected_arg):
  if arg == expected_arg:
    return True
  elif _isclass(expected_arg) and isinstance(arg, expected_arg):
    return True
  elif ('_sre.SRE_Pattern' in str(type(expected_arg)) and
        expected_arg.search(arg)):
    return True
  else:
    return False


def _getattr(obj, name):
  """Convenience wrapper."""
  return object.__getattribute__(obj, name)


def _isclass(obj):
  """Fixes stupid bug in inspect.isclass from < 2.7."""
  if sys.version_info < (2, 7):
    return isinstance(obj, (type, types.ClassType))
  else:
    return inspect.isclass(obj)

def teardown():
  """Performs testuitls-specific teardown tasks."""

  saved = {}
  for mock_object, expectations in TestutilsContainer.testutils_objects.items():
    saved[mock_object] = expectations[:]
    for expectation in expectations:
      expectation._reset()
  for mock_object in saved:
    del TestutilsContainer.testutils_objects[mock_object]
  # make sure this is done last to keep exceptions here from breaking
  # any of the previous steps that cleanup all the changes
  for mock_object, expectations in saved.items():
    for expectation in expectations:
      expectation._verify()


def wrap(spec, **kwargs):
  """Wraps an object in order to manipulate its methods.

  This function takes an existing object (or class or module) and use
  it as a basis for a partial mock.

  Examples:
    >>> wrap(SomeClass).some_method.returns('stuff')

  Args:
    - spec: object (or class or module) to mock
    - kwargs: method/return_value pairs to attach to the object

  Returns:
    Wrap object if no spec is provided. Otherwise return the spec object.
  """
  matches = [x for x in TestutilsContainer.testutils_objects
             if x.__object__ is spec]
  if matches:
    mock = matches[0]
  else:
    mock = Wrap(spec, **kwargs)
    TestutilsContainer.add_expectation(mock, Expectation(spec))
  return mock


def fake(**kwargs):
  return Fake(**kwargs)
