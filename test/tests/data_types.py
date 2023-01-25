import sys
import pycparser
import ctypes
import os
import inspect
from ctypes import (
    c_uint8, c_uint16, c_uint32, c_uint64,
    c_int8, c_int16, c_int32, c_int64,
    POINTER, CFUNCTYPE,
    Structure,
)

__all__ = []
__all__ += ['c_uint%i' % i for i in [8, 16, 32, 64]]
__all__ += ['c_int%i'  % i for i in [8, 16, 32, 64]]

_this_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

try:
    from ast2ctypes import CTypeFactory
except ImportError:
    sys.path.append(os.path.join(_this_path, '../../../../pylib'))
    from ast2ctypes import CTypeFactory

# ========================== Enumerations =========================
# prlsc_errorCode_t
PRLSC_ERRORCODE_NONE                         = 0
PRLSC_ERRORCODE_RXFRAME_BAD_ESC              = 1
PRLSC_ERRORCODE_RXFRAME_SERVICEINDEX_BOUNDS  = 2
PRLSC_ERRORCODE_RXFRAME_TOO_LONG             = 3
PRLSC_ERRORCODE_RXFRAME_BAD_CHECKSUM         = 4
PRLSC_ERRORCODE_DATAGRAM_BAD_CHECKSUM        = 5
PRLSC_ERRORCODE_DATAGRAM_TOO_LONG            = 6
PRLSC_ERRORCODE_DATAGRAM_SERVICEINDEX_BOUNDS = 7

# prlsc_responseCode_t
PRLSC_RESPONSE_CODE_POSITIVE        = 0x00
PRLSC_RESPONSE_CODE_INVALID_REQUEST = 0x01
PRLSC_RESPONSE_CODE_UNKNOWN_REQUEST = 0x02

# prlsc_rxFrameStateMachineState_t
PRLSC_RXFRAMESTATE_WAIT_STARTBYTE = 0
PRLSC_RXFRAMESTATE_COLLECTING     = 1
PRLSC_RXFRAMESTATE_ESC            = 2

# prlsc_rxDatagramStateMachineState_t
PRLSC_RXDATAGRAMSTATE_POPULATING  = 0
PRLSC_RXDATAGRAMSTATE_ERROR       = 1

# prlsc_txByteState_t
PRLSC_TXBYTESTATE_DO_NOTHING    = 0
PRLSC_TXBYTESTATE_START         = 1
PRLSC_TXBYTESTATE_NORMAL_BYTE   = 2
PRLSC_TXBYTESTATE_ESCAPED_BYTE  = 3

# prlsc_serviceType_t
PRLSC_TYPE_STREAM       = 1
PRLSC_TYPE_DIAGNOSTICS  = 2

# bool
TRUE  = 1
FALSE = 0


__all__ += [
    k for k in globals().keys()
    if (not k.startswith('_')) and (k == k.upper())
]

# ========================== typedef ==========================
# Add factory built classes to global scope
_ast = pycparser.parse_file(os.path.join(_this_path, '../test-preproc.c'))
_factory = CTypeFactory(_ast)

_dynamic_lib = ctypes.cdll.LoadLibrary(os.path.join(_this_path, '../test.so'))

for (name, ctype_class) in _factory.ctypes_map.items():
    assert not name.startswith('_'), "strictly speaking, can't allow importing of types prefixed with '_'"
    assert name not in ['globals', 'NotImplementedError'], "can't allow importing of types with these names"

    if name in _factory.funcdef_map:
        # function call to imported dll with respective restype and par
        _func = getattr(_dynamic_lib, name)
        _func.restype = ctype_class._restype_
        _func.argtypes = ctype_class._argtypes_
        globals()[name] = _func
        __all__.append(name)

        # If you want access to the function's type (eg: to pass a c function pointer
        # to a python function) you may also want to map the function declaration class itself.
        # I've just thrown a "__t" on the end, not pretty, which is why it's unlikely to clash
        # with somebody elses naming convention... ugly isn't all bad.
        globals()[name + "__t"] = ctype_class
        __all__.append(name + "__t")

    elif name in _factory.typedef_map:
        # typedef ctype is exportable function
        globals()[name] = ctype_class
        __all__.append(name)

    else:
        raise NotImplementedError("something's not right here")

