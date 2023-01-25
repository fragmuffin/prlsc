#!/usr/bin/env python
import sys
import os
from ctypes import (
    cdll, c_int16, CFUNCTYPE, PYFUNCTYPE,
)
import pycparser

DLL_FILENAME = 'prog.so'
PREPROC_FILENAME = 'prog-preproc.c'

if __name__ == "__main__":

    # c2ctypetypes
    sys.path.append('../../../')
    from ast2ctypes.ctypefactory import CTypeFactory
    ast = pycparser.parse_file(PREPROC_FILENAME)
    factory = CTypeFactory(ast)

    ret_t = factory.ctypes_map['ret_t']
    param_t = factory.ctypes_map['param_t']
    callback_t = factory.ctypes_map['callback_t']

    # Loading Dynamic Library
    dll = cdll.LoadLibrary(os.path.abspath(DLL_FILENAME))

    # --- add (sanity check)
    dll.add.argtypes = [param_t, param_t]
    dll.add.restype = ret_t

    ans = dll.add(10, 20)
    print("10 + 20 = {}".format(ans))
    assert ans == 10 + 20, "yeah, that didn't work"

    # --- function pointer
    def mult(a, b):
        return a * b

    dll.passthrough.argtypes = [callback_t, param_t, param_t]
    dll.passthrough.restype = ret_t

    ans = dll.passthrough(callback_t(mult), 30, 4)
    print("30 * 4 = {}".format(ans))
    assert ans == 30 * 4, "bugger; function pointer gave wrong answer"
