# -*- coding: utf8 -*-
from testutils.exceptions import AttemptingToMockBuiltin
from testutils.exceptions import TestutilsError
from testutils.exceptions import InvalidMethodSignature
from testutils.exceptions import InvalidExceptionClass
from testutils.exceptions import InvalidExceptionMessage
from testutils.exceptions import InvalidState
from testutils.exceptions import MethodDoesNotExist
from testutils.exceptions import MethodNotCalled
from testutils.exceptions import MethodCalledOutOfOrder
from testutils.expectation import ReturnValue
from testutils.helpers import _format_args
from testutils import _testutils_objects
from testutils import verify
from testutils import fake
from testutils import flex
import re
import sys
import unittest


def module_level_function(some, args):
    return "%s, %s" % (some, args)


def assertRaises(exception, method, *kargs, **kwargs):
    try:
        method(*kargs, **kwargs)
    except exception:
        assert True
        return
    except:
        pass
    raise Exception('%s not raised' % exception.__name__)


def assertEqual(expected, received, msg=''):
    if not msg:
        msg = 'expected %s, received %s' % (expected, received)
    if expected != received:
        raise AssertionError('%s != %s : %s' % (expected, received, msg))


class RegularClass(object):

    def _tear_down(self):
        return verify()

    def test_testutils_should_create_mock_object_from_dict(self):
        mock = fake(foo='foo', bar='bar')
        assertEqual('foo',    mock.foo)
        assertEqual('bar', mock.bar)

    def test_testutils_should_add_expectations(self):
        class Foo:
            def method_foo(self): pass
        mock = flex(Foo)
        mock.method_foo
        assert ('method_foo' in [x.method for x in _testutils_objects[mock]])

    def test_testutils_should_return_value(self):
        class Foo:
            def method_foo(self): pass
            def method_bar(self): pass
        foo = Foo()
        mock = flex(foo)
        mock.method_foo.returns('value_bar')
        mock.method_bar.returns('value_baz')
        assertEqual('value_bar', foo.method_foo())
        assertEqual('value_baz', foo.method_bar())

    def test_testutils_should_accept_shortcuts_for_creating_mock_object(self):
        mock = fake(attr1='value 1', attr2=lambda: 'returning 2')
        assertEqual('value 1', mock.attr1)
        assertEqual('returning 2',    mock.attr2())

    def test_testutils_should_accept_shortcuts_for_creating_expectations(self):
        class Foo:
            def method1(self): pass
            def method2(self): pass
        foo = Foo()
        flex(foo, method1='returning 1', method2='returning 2')
        assertEqual('returning 1', foo.method1())
        assertEqual('returning 2', foo.method2())
        assertEqual('returning 2', foo.method2())

    def test_testutils_expectations_returns_named_expectation(self):
        class Foo:
            def method_foo(self): pass
        mock = flex(Foo)
        mock.method_foo
        assertEqual('method_foo', mock._get_expectation('method_foo').method)

    def test_testutils_expectations_returns_none_if_not_found(self):
        class Foo:
            def method_foo(self): pass
        mock = flex(Foo)
        mock.method_foo
        assert mock._get_expectation('method_bar') is None

    def test_testutils_should_check_parameters(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        mock = flex(foo)
        mock.method_foo('bar').returns(1)
        mock.method_foo('baz').returns(2)
        assertEqual(1, foo.method_foo('bar'))
        assertEqual(2, foo.method_foo('baz'))

    def test_testutils_should_keep_track_of_calls(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        mock = flex(foo)
        mock.method_foo('foo').returns(0)
        mock.method_foo('bar').returns(1)
        mock.method_foo('baz').returns(2)
        foo.method_foo('bar')
        foo.method_foo('bar')
        foo.method_foo('baz')
        expectation = mock._get_expectation('method_foo', ('foo',))
        assertEqual(0, expectation.times_called)
        expectation = mock._get_expectation('method_foo', ('bar',))
        assertEqual(2, expectation.times_called)
        expectation = mock._get_expectation('method_foo', ('baz',))
        assertEqual(1, expectation.times_called)

    def test_testutils_should_set_expectation_call_numbers(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        mock = flex(foo)
        mock.method_foo.times(1)
        expectation = mock._get_expectation('method_foo')
        assertRaises(MethodNotCalled, expectation._verify)
        foo.method_foo()
        expectation._verify()

    def test_testutils_should_check_raised_exceptions(self):
        class Foo:
            def method_foo(): pass
        mock = flex(Foo)
        class FakeException(Exception):
            pass
        foo = Foo()
        mock.method_foo.raises(FakeException)
        assertRaises(FakeException, foo.method_foo)
        assertEqual(1, mock._get_expectation('method_foo').times_called)

    def test_testutils_should_check_raised_exceptions_instance_with_args(self):
        class Foo:
            def method_foo(): pass
        mock = flex(Foo)
        foo = Foo()
        class FakeException(Exception):
            def __init__(self, arg, arg2):
                pass
        mock.method_foo.raises(FakeException(1, arg2=2))
        assertRaises(FakeException, foo.method_foo)
        assertEqual(1, mock._get_expectation('method_foo').times_called)

    def test_testutils_should_check_raised_exceptions_class_with_args(self):
        class Foo:
            def method_foo(): pass
        mock = flex(Foo)
        foo = Foo()
        class FakeException(Exception):
            def __init__(self, arg, arg2):
                pass
        mock.method_foo.raises(FakeException, 1, arg2=2)
        assertRaises(FakeException, foo.method_foo)
        assertEqual(1, mock._get_expectation('method_foo').times_called)

    def test_testutils_should_match_any_args_by_default(self):
        class Foo:
            def method_foo(): pass
        mock = flex(Foo)
        foo = Foo()
        mock.method_foo.returns('bar')
        mock.method_foo('baz').returns('baz')
        assertEqual('bar', foo.method_foo())
        assertEqual('bar', foo.method_foo(1))
        assertEqual('bar', foo.method_foo('foo', 'bar'))
        assertEqual('baz', foo.method_foo('baz'))

    def test_should_fail_to_match_exactly_no_args_when_calling_with_args(self):
        class Foo:
            def method_foo(): pass
        mock = flex(Foo)
        foo = Foo()
        mock.method_foo()
        assertRaises(InvalidMethodSignature, foo.method_foo, 'baz')

    def test_testutils_should_match_exactly_no_args(self):
        class Foo:
            def bar(self): pass
        foo = Foo()
        flex(foo).bar().returns('baz')
        assertEqual('baz', foo.bar())

    def test_expectation_dot_mock_should_return_mock(self):
        class Foo:
            def bar(self): pass
        mock = flex(Foo)
        assertEqual(mock, mock.bar.mock)

    def test_testutils_should_create_partial_new_style_object_mock(self):
        class User(object):
            def __init__(self, name=None):
                self.name = name
            def get_name(self):
                return self.name
            def set_name(self, name):
                self.name = name
        user = User()
        flex(user).get_name.returns('john')
        user.set_name('mike')
        assertEqual('john', user.get_name())

    def test_testutils_should_create_partial_old_style_object_mock(self):
        class User:
            def __init__(self, name=None):
                self.name = name
            def get_name(self):
                return self.name
            def set_name(self, name):
                self.name = name
        user = User()
        flex(user).get_name.returns('john')
        user.set_name('mike')
        assertEqual('john', user.get_name())

    def test_testutils_should_create_partial_new_style_class_mock(self):
        class User(object):
            def __init__(self): pass
            def get_name(self): pass
        flex(User).get_name.returns('mike')
        user = User()
        assertEqual('mike', user.get_name())

    def test_testutils_should_create_partial_old_style_class_mock(self):
        class User:
            def __init__(self): pass
            def get_name(self): pass
        flex(User).get_name.returns('mike')
        user = User()
        assertEqual('mike', user.get_name())

    def test_should_match_expectations_against_builtin_classes(self):
        class Foo:
            def method_foo(self): pass
        mock = flex(Foo)
        foo = Foo()
        mock.method_foo(str).returns('got a string')
        mock.method_foo(int).returns('got an int')
        assertEqual('got a string', foo.method_foo('string!'))
        assertEqual('got an int', foo.method_foo(23))
        assertRaises(InvalidMethodSignature, foo.method_foo, 2.0)

    def test_should_match_expectations_against_user_defined_classes(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo
        mock = flex(foo)
        mock.method_foo(Foo).returns('got a Foo')
        assertEqual('got a Foo', foo.method_foo(Foo()))
        assertRaises(InvalidMethodSignature, foo.method_foo, 1)

    def test_testutils_teardown_verifies_mocks(self):
        class Foo:
            def uncalled_method(self): pass
        flex(Foo).uncalled_method.times(1)
        assertRaises(MethodNotCalled, self._tear_down)

    def test_testutils_teardown_does_not_verify_stubs(self):
        class Foo:
            def uncalled_method(self): pass
        flex(Foo).uncalled_method()
        self._tear_down()

    def test_testutils_preserves_stubbed_object_methods_between_tests(self):
        class User:
            def get_name(self):
                return 'mike'
        user = User()
        flex(user).get_name().returns('john')
        assertEqual('john', user.get_name())
        self._tear_down()
        assertEqual('mike', user.get_name())

    def test_testutils_preserves_stubbed_class_methods_between_tests(self):
        class User:
            def get_name(self):
                return 'mike'
        user = User()
        flex(User).get_name.returns('john')
        assertEqual('john', user.get_name())
        self._tear_down()
        assertEqual('mike', user.get_name())

    def test_testutils_removes_new_stubs_from_objects_after_tests(self):
        class User:
            def get_name(self): pass
        user = User()
        saved = user.get_name
        flex(user).get_name.returns('john')
        assert saved != user.get_name
        assertEqual('john', user.get_name())
        self._tear_down()
        assertEqual(saved, user.get_name)

    def test_testutils_removes_new_stubs_from_classes_after_tests(self):
        class User:
            def get_name(self): pass
        user = User()
        saved = user.get_name
        flex(User).get_name.returns('john')
        assert saved != user.get_name
        assertEqual('john', user.get_name())
        self._tear_down()
        assertEqual(saved, user.get_name)

    def test_testutils_removes_stubs_from_multiple_objects_on_teardown(self):
        class User:
            def get_name(self): pass
        class Group:
            def get_name(self): pass
        user = User()
        group = User()
        saved1 = user.get_name
        saved2 = group.get_name
        flex(user).get_name.returns('john').times(1)
        flex(group).get_name.returns('john').times(1)
        assert saved1 != user.get_name
        assert saved2 != group.get_name
        assertEqual('john', user.get_name())
        assertEqual('john', group.get_name())
        self._tear_down()
        assertEqual(saved1, user.get_name)
        assertEqual(saved2, group.get_name)

    def test_testutils_removes_stubs_from_multiple_classes_on_teardown(self):
        class User:
            def get_name(self): pass
        class Group:
            def get_name(self): pass
        user = User()
        group = User()
        saved1 = user.get_name
        saved2 = group.get_name
        flex(User).get_name.returns('john')
        flex(Group).get_name.returns('john')
        assert saved1 != user.get_name
        assert saved2 != group.get_name
        assertEqual('john', user.get_name())
        assertEqual('john', group.get_name())
        self._tear_down()
        assertEqual(saved1, user.get_name)
        assertEqual(saved2, group.get_name)

    def test_testutils_respects_at_least_when_called_less_than_requested(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('bar').times(2, None)
        foo.method_foo()
        assertRaises(MethodNotCalled, self._tear_down)

    def test_testutils_respects_at_least_when_called_requested_number(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(1, None)
        foo.method_foo()
        self._tear_down()

    def test_testutils_respects_at_least_when_called_more_than_requested(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(1, None)
        foo.method_foo()
        foo.method_foo()
        self._tear_down()

    def test_testutils_respects_at_most_when_called_less_than_requested(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('bar').times(0, 2)
        foo.method_foo()
        self._tear_down()

    def test_testutils_respects_at_most_when_called_requested_number(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(0, 1)
        foo.method_foo()
        self._tear_down()

    def test_testutils_respects_at_most_when_called_more_than_requested(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(0, 1)
        foo.method_foo()
        foo.method_foo()
        assertRaises(MethodNotCalled, self._tear_down)

    def test_testutils_works_with_never_when_true(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(0)
        self._tear_down()

    def test_testutils_works_with_never_when_false(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        flex(foo).method_foo.returns('value_bar').times(0)
        foo.method_foo()
        assertRaises(MethodNotCalled, self._tear_down)
    
    def test_testutils_get_testutils_expectation_should_work_with_args(self):
        class Foo:
            def method_foo(self): pass
        foo = Foo()
        mock = flex(foo)
        mock.method_foo('value_bar')
        assert mock._get_expectation('method_foo', 'value_bar')

    def test_testutils_function_should_always_return_same_mock_object(self):
        class User(object): pass
        user = User()
        foo = flex(user)
        assert foo != user
        assert foo == flex(user)

    def test_should_not_return_class_object_if_mocking_instance(self):
        class User:
            def method(self): pass
        user = User()
        user2 = User()
        class_mock = flex(User).method.returns('class').mock
        user_mock = flex(user).method.returns('instance').mock
        assert class_mock is not user_mock
        assertEqual('instance', user.method())
        assertEqual('class', user2.method())

    def test_should_blow_up_on_default_for_class_mock(self):
        class User:
            def foo(self):
                return 'class'
        assertRaises(TestutilsError, flex(User).foo.runs)

    def test_should_not_blow_up_on_default_for_class_methods(self):
        class User:
            @classmethod
            def foo(self):
                return 'class'
        flex(User).foo.runs()
        assertEqual('class', User.foo())

    def test_should_not_blow_up_on_default_for_static_methods(self):
        class User:
            @staticmethod
            def foo():
                return 'static'
        flex(User).foo.runs()
        assertEqual('static', User.foo())

    def test_should_mock_new_instances_with_multiple_params(self):
        class User(object): pass
        class Group(object):
            def __init__(self, arg, arg2):
                pass
        user = User()
        flex(Group).__new__.returns(user)
        assert user is Group(1, 2)

    def test_testutils_should_revert_new_instances_on_teardown(self):
        class User(object): pass
        class Group(object): pass
        user = User()
        group = Group()
        flex(Group).__new__.returns(user)
        assert user is Group()
        self._tear_down()
        assertEqual(group.__class__, Group().__class__)

    def test_testutils_default_calls_respects_matched_expectations(self):
        class Group(object):
            def method1(self, arg1, arg2='b'):
                return '%s:%s' % (arg1, arg2)
            def method2(self, arg):
                return arg
        group = Group()
        flex(group).method1.runs().times(2)
        assertEqual('a:c', group.method1('a', arg2='c'))
        assertEqual('a:b', group.method1('a'))
        flex(group).method2('c').runs().times(1)
        assertEqual('c', group.method2('c'))
        self._tear_down()

    def test_testutils_default_respects_unmatched_expectations(self):
        class Group(object):
            def method1(self, arg1, arg2='b'):
                return '%s:%s' % (arg1, arg2)
            def method2(self): pass
        group = Group()
        flex(group).method1.runs().times(1, None)
        assertRaises(MethodNotCalled, self._tear_down)
        flex(group).method2('a').times(1)
        flex(group).method2('not a')
        flex(group).method2('not a')
        assertRaises(MethodNotCalled, self._tear_down)

    def test_testutils_doesnt_error_on_properly_ordered_expectations(self):
        class Foo(object):
            def foo(self): pass
            def method1(self): pass
            def bar(self): pass
            def baz(self): pass
        flex(Foo).foo
        flex(Foo).method1('a').ordered()
        flex(Foo).bar
        flex(Foo).method1('b').ordered()
        flex(Foo).baz
        Foo.bar()
        Foo.method1('a')
        Foo.method1('b')
        Foo.baz()
        Foo.foo()

    def test_testutils_errors_on_improperly_ordered_expectations(self):
        class Foo(object):
            def foo(self): pass
            def method1(self): pass
            def bar(self): pass
            def baz(self): pass
        flex(Foo).foo
        flex(Foo).method1('a').ordered()
        flex(Foo).bar
        flex(Foo).method1('b').ordered()
        Foo.baz
        Foo.bar()
        Foo.bar()
        Foo.foo()
        assertRaises(MethodCalledOutOfOrder, Foo.method1, 'b')

    def test_testutils_should_accept_multiple_return_values(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1.returns(1, 5).returns(2)
        assertEqual(1, foo.method1())
        assertEqual(5, foo.method1())
        assertEqual(2, foo.method1())
        assertEqual(1, foo.method1())
        assertEqual(5, foo.method1())
        assertEqual(2, foo.method1())

    def test_should_accept_multiple_return_values_with_shortcut(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1.returns(1, 2)
        assertEqual(1, foo.method1())
        assertEqual(2, foo.method1())
        assertEqual(1, foo.method1())
        assertEqual(2, foo.method1())

    def test_should_mix_multiple_return_values_with_exceptions(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1.returns(1).raises(Exception).returns(2)
        assertEqual(1, foo.method1())
        assertRaises(Exception, foo.method1)
        assertEqual(2, foo.method1())
        assertEqual(1, foo.method1())
        assertRaises(Exception, foo.method1)
        assertEqual(2, foo.method1())

    def test_testutils_should_match_types_on_multiple_arguments(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1(str, int).returns('ok')
        assertEqual('ok', foo.method1('some string', 12))
        assertRaises(InvalidMethodSignature, foo.method1, 12, 32)
        assertRaises(InvalidMethodSignature, foo.method1, 12, 'some string')
        assertRaises(InvalidMethodSignature, foo.method1, 'string', 12, 14)

    def test_testutils_should_match_types_on_multiple_arguments_generic(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1(object, object, object).returns('ok')
        assertEqual('ok', foo.method1('some string', None, 12))
        assertEqual('ok', foo.method1((1,), None, 12))
        assertEqual('ok', foo.method1(12, 14, []))
        assertEqual('ok', foo.method1('some string', 'another one', False))
        assertRaises(InvalidMethodSignature, foo.method1, 'string', 12)
        assertRaises(InvalidMethodSignature, foo.method1, 'string', 12, 13, 14)

    def test_testutils_should_match_types_on_multiple_arguments_classes(self):
        class Foo:
            def method1(self): pass
        class Bar: pass
        foo = Foo()
        bar = Bar()
        flex(foo).method1(object, Bar).returns('ok')
        assertEqual('ok', foo.method1('some string', bar))
        assertRaises(InvalidMethodSignature, foo.method1, bar, 'some string')
        assertRaises(InvalidMethodSignature, foo.method1, 12, 'some string')

    def test_testutils_should_match_keyword_arguments(self):
        class Foo:
            def method1(self): pass
        foo = Foo()
        flex(foo).method1(1, arg3=3, arg2=2).times(2)
        foo.method1(1, arg2=2, arg3=3)
        foo.method1(1, arg3=3, arg2=2)
        self._tear_down()
        flex(foo).method1(1, arg3=3, arg2=2)
        assertRaises(InvalidMethodSignature, foo.method1, arg2=2, arg3=3)
        assertRaises(InvalidMethodSignature, foo.method1, 1, arg2=2, arg3=4)
        assertRaises(InvalidMethodSignature, foo.method1, 1)

    def test_testutils_calls_should_match_keyword_arguments(self):
        class Foo:
            def method1(self, arg1, arg2=None, arg3=None):
                return '%s%s%s' % (arg1, arg2, arg3)
        foo = Foo()
        flex(foo).method1(1, arg3=3, arg2=2).runs().times(1)
        assertEqual('123', foo.method1(1, arg2=2, arg3=3))

    def test_testutils_should_mock_private_methods(self):
        class Foo:
            def __private_method(self):
                return 'foo'
            def public_method(self):
                return self.__private_method()
        foo = Foo()
        flex(foo)._Foo__private_method.returns('bar')
        assertEqual('bar', foo.public_method())

    def test_testutils_should_mock_private_special_methods(self):
        class Foo:
            def __private_special_method__(self):
                return 'foo'
            def public_method(self):
                return self.__private_special_method__()
        foo = Foo()
        flex(foo).__private_special_method__.returns('bar')
        assertEqual('bar', foo.public_method())

    def test_testutils_should_mock_double_underscore_method(self):
        class Foo:
            def __(self):
                return 'foo'
            def public_method(self):
                return self.__()
        foo = Foo()
        flex(foo).__.returns('bar')
        assertEqual('bar', foo.public_method())

    def test_testutils_should_mock_private_class_methods(self):
        class Foo:
            def __iter__(self): pass
        flex(Foo).__iter__.yields(1, 2, 3)
        assertEqual([1, 2, 3], [x for x in Foo()])

    def test_testutils_should_mock_generators(self):
        class Gen:
            def foo(self): pass
        gen = Gen()
        flex(gen).foo.yields(*range(1, 10))
        output = [val for val in gen.foo()]
        assertEqual([val for val in range(1, 10)], output)

    def test_testutils_should_mock_same_class_twice(self):
        class Foo: pass
        flex(Foo)
        flex(Foo)

    def test_testutils_spy_should_not_clobber_original_method(self):
        class User:
            def get_stuff(self): return 'real', 'stuff'
        user = User()
        flex(user).get_stuff.runs()
        flex(user).get_stuff.runs()
        assertEqual(('real', 'stuff'), user.get_stuff())

    def test_testutils_should_properly_restore_static_methods(self):
        class User:
            @staticmethod
            def get_stuff(): return 'ok!'
        assertEqual('ok!', User.get_stuff())
        flex(User).get_stuff
        assert User.get_stuff() is None
        self._tear_down()
        assertEqual('ok!', User.get_stuff())

    def test_should_properly_restore_undecorated_static_methods(self):
        class User:
            def get_stuff(): return 'ok!'
            get_stuff = staticmethod(get_stuff)
        assertEqual('ok!', User.get_stuff())
        flex(User).get_stuff
        assert User.get_stuff() is None
        self._tear_down()
        assertEqual('ok!', User.get_stuff())

    def test_testutils_should_properly_restore_module_level_functions(self):
        if 'testutils_test' in sys.modules:
            mod = sys.modules['testutils_test']
        else:
            mod = sys.modules['__main__']
        flex(mod).module_level_function
        assertEqual(None,    module_level_function(1, 2))
        self._tear_down()
        assertEqual('1, 2', module_level_function(1, 2))

    def test_testutils_should_properly_restore_class_methods(self):
        class User:
            @classmethod
            def get_stuff(cls):
                return cls.__name__
        assertEqual('User', User.get_stuff())
        flex(User).get_stuff.returns('foo')
        assertEqual('foo', User.get_stuff())
        self._tear_down()
        assertEqual('User', User.get_stuff())

    def test_testutils_should_fail_mocking_nonexistent_methods(self):
        class User: pass
        user = User()
        try:
            flex(user).nonexistent()
            raise Exception('failed to raise MethodDoesNotExist')
        except MethodDoesNotExist:
            pass

    def test_testutils_should_not_explode_on_unicode_formatting(self):
        if sys.version_info >= (3, 0):
            formatted = _format_args(
                    'method', {'kargs' : (chr(0x86C7),), 'kwargs' : {}})
            assertEqual('method("蛇")', formatted)
        else:
            formatted = _format_args(
                    'method', {'kargs' : (unichr(0x86C7),), 'kwargs' : {}})
            assertEqual('method("%s")' % unichr(0x86C7), formatted)

    def test_return_value_should_not_explode_on_unicode_values(self):
        class Foo:
            def method(self): pass
        if sys.version_info >= (3, 0):
            return_value = ReturnValue(chr(0x86C7))
            assertEqual('"蛇"', '%s' % return_value)
            return_value = ReturnValue((chr(0x86C7), chr(0x86C7)))
            assertEqual('("蛇", "蛇")', '%s' % return_value)
        else:
            return_value = ReturnValue(unichr(0x86C7))
            assertEqual('"%s"' % unichr(0x86C7), unicode(return_value))

    def test_pass_thru_calls_original_method_only_once(self):
        class Nyan(object):
            def __init__(self):
                    self.n = 0
            def method(self):
                    self.n += 1
        obj = Nyan()
        flex(obj).method.runs()
        obj.method()
        assertEqual(obj.n, 1)
    
    def test_calls_works_for_same_method_with_different_args(self):
        class Foo:
            def method(self, arg):
                pass
        foo = Foo()
        flex(foo).method('foo').runs().times(1)
        flex(foo).method('bar').runs().times(1)
        foo.method('foo')
        foo.method('bar')
        self._tear_down()

    def test_calls_fails_properly_for_same_method_with_different_args(self):
        class Foo:
            def method(self, arg):
                pass
        foo = Foo()
        flex(foo).method('foo').runs().times(1)
        flex(foo).method('bar').runs().times(1)
        foo.method('foo')
        assertRaises(MethodNotCalled, self._tear_down)

    def test_should_give_reasonable_error_for_builtins(self):
        try:
            flex(dict).keys
            raise Exception('AttemptingToMockBuiltin not raised')
        except AttemptingToMockBuiltin:
            pass

    def test_should_give_reasonable_error_for_instances_of_builtins(self):
        d = dict()
        try:
            flex(d).keys
            raise Exception('AttemptingToMockBuiltin not raised')
        except AttemptingToMockBuiltin:
            pass

    def test_testutils_should_replace_method(self):
        class Foo:
            def method(self, arg):
                return arg
        foo = Foo()
        flex(foo).method.runs(lambda x: x == 5)
        assertEqual(foo.method(5), True)
        assertEqual(foo.method(4), False)

    def test_testutils_should_replace_cannot_be_specified_twice(self):
        class Foo:
            def method(self, arg):
                return arg
        foo = Foo()
        expectation = flex(foo).method.runs(lambda x: x == 5)
        assertRaises(TestutilsError,
                                 expectation.runs, lambda x: x == 3)

    def test_testutils_should_mock_the_same_method_multiple_times(self):
        class Foo:
            def method(self): pass
        foo = Foo()
        flex(foo).method.returns(1)
        assertEqual(foo.method(), 1)
        flex(foo).method.returns(2)
        assertEqual(foo.method(), 2)
        flex(foo).method.returns(3)
        assertEqual(foo.method(), 3)
        flex(foo).method.returns(4)
        assertEqual(foo.method(), 4)

    def test_new_instances_should_be_a_method(self):
        class Foo(object): pass
        flex(Foo).__new__.returns('bar')
        assertEqual('bar', Foo())
        self._tear_down()
        assert 'bar' != Foo()

    def test_new_instances_raises_error_when_not_a_class(self):
        class Foo(object): pass
        foo = Foo()
        try:
            mock = flex(foo).__new__.returns('bar')
            raise Exception('TestutilsError not raised')
        except TestutilsError:
            pass

    def test_new_instances_works_with_multiple_return_values(self):
        class Foo(object): pass
        flex(Foo).__new__.returns('foo', 'bar')
        assertEqual('foo', Foo())
        assertEqual('bar', Foo())

    def test_mocking_down_the_inheritance_chain_class_to_class(self):
        class Parent(object):
            def foo(self): pass
        class Child(Parent):
            def bar(self): pass

        flex(Parent).foo.returns('outer')
        flex(Child).bar.returns('inner')
        assert 'outer', Parent().foo()
        assert 'inner', Child().bar()

    def test_arg_matching_works_with_regexp(self):
        class Foo:
            def foo(arg1, arg2): pass
        foo = Foo()
        flex(foo).foo(
            re.compile('^arg1.*asdf$'), arg2=re.compile('f')).returns('mocked')
        assertEqual('mocked', foo.foo('arg1somejunkasdf', arg2='aadsfdas'))

    def test_arg_matching_with_regex_fails_when_regex_doesnt_match_karg(self):
        class Foo:
            def foo(arg1, arg2): pass
        foo = Foo()
        flex(foo).foo(
            re.compile('^arg1.*asdf$'), arg2=re.compile('a')).returns('mocked')
        assertRaises(InvalidMethodSignature,
                     foo.foo, 'arg1somejunkasdfa', arg2='a')

    def test_arg_matching_with_regex_fails_when_regex_doesnt_match_kwarg(self):
        class Foo:
            def foo(arg1, arg2): pass
        foo = Foo()
        flex(foo).foo(
            re.compile('^arg1.*asdf$'), arg2=re.compile('a')).returns('mocked')
        assertRaises(InvalidMethodSignature,
            foo.foo, 'arg1somejunkasdf', arg2='b')

    def test_testutils_class_returns_same_object_on_repeated_calls(self):
        class Foo: pass
        a = flex(Foo)
        b = flex(Foo)
        assertEqual(a, b)

    def test_testutils_object_returns_same_object_on_repeated_calls(self):
        class Foo: pass
        foo = Foo()
        a = flex(foo)
        b = flex(foo)
        assertEqual(a, b)

    def test_testutils_ordered_worked_after_default_stub(self):
        class Foo:
            def bar(self): pass
        foo = Foo()
        flex(foo).bar
        flex(foo).bar('a').ordered()
        flex(foo).bar('b').ordered()
        assertRaises(MethodCalledOutOfOrder, foo.bar, 'b')

    def test_fake_object_takes_any_attribute(self):
        foo = fake()
        assertEqual(foo, foo.bar)

    def test_state_machine(self):
        class Radio:
            def __init__(self): self.is_on = False
            def switch_on(self): self.is_on = True
            def switch_off(self): self.is_on = False
            def select_channel(self): return None
            def adjust_volume(self, num): self.volume = num

        radio = Radio()
        mock = flex(radio)
        mock.select_channel.times(1).when(lambda: radio.is_on)
        mock.adjust_volume(5).runs().times(1).when(lambda: radio.is_on)

        assertRaises(InvalidState, radio.select_channel)
        assertRaises(InvalidState, radio.adjust_volume, 5)
        radio.is_on = True
        radio.select_channel()
        radio.adjust_volume(5)

    def test_support_at_least_and_at_most_together(self):
        class Foo:
            def bar(self): pass

        foo = Foo()
        flex(foo).bar.runs().times(1, 2)
        assertRaises(MethodNotCalled, self._tear_down)

        flex(foo).bar.runs().times(1, 2)
        foo.bar()
        foo.bar()
        foo.bar()
        assertRaises(MethodNotCalled, self._tear_down)

        flex(foo).bar.runs().times(1, 2)
        foo.bar()
        self._tear_down()

        flex(foo).bar.runs().times(1, 2)
        foo.bar()
        foo.bar()
        self._tear_down()

    def test_recorder_for_unassigned_variables(self):
        foo = fake()
        foo.asdf()
        foo.attr
        foo.hjkl()
        assertEqual(
            [{'name': 'asdf', 'kargs': (), 'kwargs': {}, 'returned': foo},
             {'name': 'attr', 'returned': foo},
             {'name': 'hjkl', 'kargs': (), 'kwargs': {}, 'returned': foo}],
            foo.__calls__)

    def test_recorder_for_assigned_variables(self):
        foo = fake(asdf=lambda: 'blah', attr=23)
        foo.asdf()
        foo.attr
        foo.hjkl()
        assertEqual(
            [{'name': 'asdf', 'kargs': (), 'kwargs': {}, 'returned': 'blah'},
             {'name': 'attr', 'returned': 23},
             {'name': 'hjkl', 'kargs': (), 'kwargs': {}, 'returned': foo}],
            foo.__calls__)


class TestTestutilsUnittest(RegularClass, unittest.TestCase):
    def tearDown(self):
        pass

    def _tear_down(self):
        return verify()


if sys.version_info >= (2, 6):
    import testutils_modern_test

    class TestUnittestModern(testutils_modern_test.TestutilsUnittestModern):
        pass


if __name__ == '__main__':
    unittest.main()
