import os
import sys
import inspect
import pycparser
import ctypes as _ctypes

# Any variables defined here are prefixed with a '_'.
# This is because the globals()[name] code below will replace anything with the same name.
# and if we're still expecting to use it after it's renamed, that could have some very
# very interesting results (where interesting = bad).
# ctypes


# path to this directory (irrespective of where os.getcwd() is)
_this_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

# import the ast2ctypes lib
try:
    from ast2ctypes import CTypeFactory
except ImportError:
    # this 'try' block is not required if ast2ctypes is installed properly
    sys.path.append(os.path.join(_this_path, '../../../..'))  # path containing ast2ctypes relative to this example
    from ast2ctypes import CTypeFactory

# --- Define & assert existence of required Build Files
_DLL_PATH_LOCAL = 'something.so'
_DLL_PATH_ABS = os.path.join(_this_path, _DLL_PATH_LOCAL)

_PREPROC_PATH_LOCAL = 'something-preproc.c'
_PREPROC_PATH_ABS = os.path.join(_this_path, _PREPROC_PATH_LOCAL)

# to enable useful debugging user prompts
for check_file in [_DLL_PATH_ABS, _PREPROC_PATH_ABS]:
    assert os.path.isfile(check_file), "required file '%s' does not exist; run 'make' in that directory" % (check_file)


# --- Build ctypes from ast
# ok, this is the meat you actually want; everything above is just house-keeping.

# Make AST from preprocessed c file
_ast = pycparser.parse_file(_PREPROC_PATH_ABS)
_factory = CTypeFactory(_ast)

# Import dll
_dynamic_lib = _ctypes.cdll.LoadLibrary(_DLL_PATH_ABS)

__all__ = []


def _add_exportable_obj(name, obj):
    # Add given object to
    #   - globals scoped to this module (so it will not be garbage collected)
    #   - __all__ so it may be imported with `from something import *`
    globals()[name] = obj
    __all__.append(name)


for (name, ctype_class) in _factory.ctypes_map.items():
    assert not name.startswith('_'), "strictly speaking, can't allow importing of types prefixed with '_'"
    assert name not in ['globals', 'NotImplementedError'], "can't allow importing of types with these names"

    if name in _factory.funcdef_map:
        # function call to imported dll with respective restype and argtypes
        _func = getattr(_dynamic_lib, name)
        _func.restype = ctype_class._restype_
        _func.argtypes = ctype_class._argtypes_
        _add_exportable_obj(name, _func)

        # If you want access to the function's type (eg: to pass a c function pointer
        # to a python function) you may also want to map the function declaration class itself.
        # I've just thrown a "__t" on the end, not pretty, which is why it's unlikely to clash
        # with somebody elses naming convention... ugly isn't all bad.
        _add_exportable_obj(name + "__t", ctype_class)

    elif name in _factory.typedef_map:
        # typedef ctype is exportable function
        _add_exportable_obj(name, ctype_class)

    else:
        raise NotImplementedError("something's not right here")

