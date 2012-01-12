from flexmock import flexmock
from flexmock import flexmock_teardown
import unittest

class TestFoo(unittest.TestCase):

  def test_some_flexmock(self):
    foo = flexmock(asdf=1234, stuff='foo')
    mock = flexmock(SomeStuff, method1='blah')
    mock2 = flexmock(SomeOtherStuff)
    asdf = flexmock(Blah, sadf=flexmock(fake=stuff))

  def test_something(self):
    flexmock(
        SomeCrazyLineBreaks).should_receive('foo')
    flexmock(SomeCrazyLineBreaks2
        ).should_receive('foo')

  def test_should_receive_stuff(self):
    flexmock(obj).should_receive('method1').once
    flexmock(obj).should_receive("method2"
    ).times(3).and_return('stuff')
    flexmock(obj).should_receive(
        'method3')
    flexmock(obj).should_receive(
        "method4").with_args(1, 2).once()
    # flexmock(obj).should_receive(
    #    'method5')
    # flexmock(obj).should_receive(
    #    "method6").with_args(1, 2)
    flexmock(obj).should_receive(
        "method7").with_args(
        1, 2).and_return('stuff')
    flexmock(obj).should_receive('method8').once.with_args().and_return(1
        ).and_return(2
        ).and_raise(3).and_return(
            4)
    flexmock(obj).should_receive('method9').and_return(0).with_args('with_args').and_return(1).and_return(2).and_raise(
        3).and_raise(4).once().and_return(5)

  def test_spies(self):
    flexmock(obj).should_call('method1')
    flexmock(obj).should_call("method2"
    )
    flexmock(obj).should_call(
        'method3')
    flexmock(obj).should_call(
        "method4"
        ).and_return(1).with_args(1, 2, 3)

  def test_new_instances(self):
    flexmock(Object).new_instances(1, 2, 3)

  def test_side_effecty_usage(self):
    flexmock(foo)
    foo.should_receive('bar').and_raise(Exception, "stuff")

  def test_times_modifiers(self):
    flexmock(foo).should_receive('bar').at_least.once.at_most.twice()
    flexmock(foo).should_receive('bar').at_least.twice.when(lambda: x)
    flexmock(foo).should_receive('bar').at_most.twice
