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


import sys


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
    calls = object.__getattribute__(self, '__calls__')
    if calls:
      call = calls[-1]
      call['kargs'] = kargs
      call['kwargs'] = kwargs
      call['returned'] = self
    return self

  def __getattribute__(self, name):
    attr = object.__getattribute__(self, name)
    if name not in ORIGINAL_FAKE_ATTRS:
      calls = object.__getattribute__(self, '__calls__')
      calls.append({'name': name, 'returned': attr})
    return attr

  def __getattr__(self, name):
    calls = object.__getattribute__(self, '__calls__')
    calls.append({'name': name, 'returned': self})
    return self

  def _recordable(self, func):
    def inner(*kargs, **kwargs):
      calls = object.__getattribute__(self, '__calls__')
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
