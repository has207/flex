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


import inspect
import sys
import types


def _arg_to_str(arg):
    if '_sre.SRE_Pattern' in str(type(arg)):
        return '/%s/' % arg.pattern
    if isinstance(arg, tuple):
        args = ', '.join([_arg_to_str(a) for a in arg])
        return '(' + args + ')'
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


def _format_args(method, arguments):
    if arguments is None:
        arguments = {'kargs': (), 'kwargs': {}}
    kargs = ', '.join(_arg_to_str(arg) for arg in arguments['kargs'])
    kwargs = ', '.join(
        '%s=%s' %
        (k, _arg_to_str(v)) for k, v in arguments['kwargs'].items())
    if kargs and kwargs:
        args = '%s, %s' % (kargs, kwargs)
    else:
        args = '%s%s' % (kargs, kwargs)
    return '%s(%s)' % (method, args)


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


def _isclass(obj):
    """Fixes stupid bug in inspect.isclass from < 2.7."""
    if sys.version_info < (2, 7):
        return isinstance(obj, (type, types.ClassType))
    else:
        return inspect.isclass(obj)


def _get_code(func):
    if hasattr(func, 'func_code'):
        code = 'func_code'
    elif hasattr(func, 'im_func'):
        func = func.im_func
        code = 'func_code'
    else:
        code = '__code__'
    return getattr(func, code)


def _get_runnable_name(runnable):
    """Ugly hack to get the name of when() condition from the source code."""
    name = 'condition'
    try:
        source = inspect.getsource(runnable)
        if 'when(' in source:
            name = source.split('when(')[1].split(')')[0]
        elif 'def ' in source:
            name = source.split('def ')[1].split('(')[0]
    except:  # couldn't get the source, oh well
        pass
    return name
