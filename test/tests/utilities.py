import unittest
import sys
import os
import itertools
import copy
import logging

import ctypes
from ctypes import pointer, addressof, cast, sizeof

import data_types
from data_types import *


# ---- Logging
log = logging.getLogger(__name__)
logging.basicConfig(format='%(message)s')
#log.level = logging.DEBUG #uncomment for debug output

DLL_FILENAME_REL = 'test.so'
DLL_FILENAME_ABS = os.path.join(os.getcwd(), DLL_FILENAME_REL)


# ---- Utilities
def getdict(struct):
    """Convert structure to dict (primarily for display / debugging)"""
    # ref: http://stackoverflow.com/questions/3789372/python-can-we-convert-a-ctypes-structure-to-a-dictionary
    result = {}
    for field, _ in struct._fields_:
         value = getattr(struct, field)
         # if the type is not a primitive and it evaluates to False ...
         if (type(value) not in [int, long, float, bool]) and not bool(value):
             # it's a null pointer
             value = None
         elif hasattr(value, "_length_") and hasattr(value, "_type_"):
             # Probably an array
             value = list(value)
         elif hasattr(value, "_fields_"):
             # Probably another struct
             value = getdict(value)
         result[field] = value
    return result


def print_buffer(config, title=None):
    buffer = config.state.contents.frame.buffer
    byte_list = []
    bytes_left = None
    i = 0
    while (bytes_left is None) or (bytes_left >= 0):
        byte_list.append(buffer[i])
        if i == 1:
            bytes_left = buffer[i]
        elif bytes_left is not None:
            bytes_left -= 1
        i += 1
    log.debug(">>> {}: 0x".format(title if title else 'buffer') + " ".join(["%02X" % i for i in byte_list]))


def datagram2str(datagram, heading="datagram:"):
    assert isinstance(datagram, prlsc_datagram_t), "bad datagram type received"
    lines = [
        heading,
        "  - serviceIndex: %i" % (datagram.serviceIndex),
        "  - subServiceIndex: %i" % (datagram.subServiceIndex),
        "  - data: %s" % ([datagram.data[i] for i in range(datagram.length)]),
        "  - length: %i" % (datagram.length),
        "  - checksum: 0x%02X" % (datagram.checksum),
    ]
    return "\n".join(lines)


def frame2str(frame, heading="frame:"):
    assert isinstance(frame, prlsc_frame_t), "bad frame type received"
    lines = [
        heading,
        "  - length: %i" % (frame.length),
        "  - serviceIndex: %i" % (frame.serviceIndex),
        "  - subServiceIndex: %i" % (frame.subServiceIndex),
        "  - data: %s" % ([frame.data[i] for i in range(frame.length)]),
        "  - checksum: 0x%02X" % (frame.checksum),
    ]
    return "\n".join(lines)

# ---- ctype Builders / Helpers
def build_struct(cls, **kwargs):
    """
    Build a struct with the given class
    :param cls: ctypes Structure class to populate
    :param kwargs:
    :return: populated instance of cls
    """
    assert issubclass(cls, ctypes.Structure), "bad paramter"
    obj = cls()
    for (key, value) in kwargs.items():
        if key.endswith('__exact'):
            key = key[:-len('__exact')]
            assert key in dict(cls._fields_), "%s struct has no %s attribute" % (cls.__name__, key)
            setattr(obj, key, value)
        else:
            setattr(obj, key, dict(cls._fields_)[key](value))
    return obj

def build_array(cls, elements):
    assert isinstance(elements, (tuple, list)), "bad parameter"
    array = (cls * len(elements))()
    for (i, value) in enumerate(elements):
        array[i] = value
    return array


# ---- Test Classes
class DllLoadedTest(unittest.TestCase):
    _prlsc = None

    @classmethod
    def setUpClass(cls):
        # Re-load and re-attach to dynamic lib each time (just to be thorough)
        cls._prlsc = ctypes.cdll.LoadLibrary(DLL_FILENAME_ABS)

        for (name, ctype_class) in data_types._factory.ctypes_map.items():
            if name in data_types._factory.funcdef_map:
                _func = getattr(cls._prlsc, name)
                _func.restype = ctype_class._restype_
                _func.argtypes = ctype_class._argtypes_


def dummy_service_callback(datagram):
    """
    Process a datagram and return a code (this is a dummy, os it doesn't do anything)
    CFUNCTYPE(prlsc_responseCode_t, prlsc_datagram_t)
    :param datagram: prlsc_datagram_t instance
    :return: prlsc_responseCode_t
    """
    log.debug("dummy_service_callback: %r", datagram)
    return PRLSC_RESPONSE_CODE_POSITIVE


def dummy_callback_sendbyte(byte):
    log.debug("dummy_callback_writer: %r", byte)
    assert isinstance(byte, c_uint8)


def dummy_checksum_calc(arr, length):
    # sum and add
    checksum = sum(arr[i] for i in range(length))
    return (~checksum + 1) & 0xFF

dummy_timer = prlsc_time_t(0)

def dummy_get_time():
    return dummy_timer.value

class PrlscEngineTest(DllLoadedTest):
    # Defaults
    TIMEOUTSEQFRAMES = 500
    FRAMESTATE_MAXBYTES = 1024
    FRAME_MAX_LENGTH = 0xFF
    DATAGRAM_MAX_LENGTH = 0x1FF

    def setUp(self):
        log.debug("") # newline to avoid debug log entries appearing on the same line as test
        self.dummy_timer = dummy_timer
        self.dummy_timer.value = 0

    # --- Time
    def increment_time(self, amount=1):
        self.dummy_timer.value += amount

    def set_time(self, value):
        self.dummy_timer.value = value

    # --- Configuration & State
    def reset_state(self, config, state):
        state.receiver.frame.state = prlsc_rxFrameStateMachineState_t(PRLSC_RXFRAMESTATE_WAIT_STARTBYTE)
        state.receiver.frame.framesReceived = c_uint8(0)
        state.errorCode = prlsc_errorCode_t(PRLSC_ERRORCODE_NONE)
        for i in range(config.serviceCount):
            # Receiver States
            receiver_datagram_state = state.receiver.datagram[i]
            receiver_datagram_state.curIdx = 0
            receiver_datagram_state.state = 0
            # Transmitter State
            transmitter_state = state.transmitterBuffer[i]
            transmitter_state.bufferIdx = 0
            transmitter_state.txIdx = 0

    def get_basic_config(self, **kwargs):
        """
        Build up a bus configuration to test with
        :return: prlsc_config_t instance with bus config
        """
        return build_struct(
            prlsc_config_t,
            # Byte Encoding
            frameByteStartFrame=0xC0,
            frameByteEsc=0xDB,
            frameByteEscStart=0xDC,
            frameByteEscEsc=0xDD,
            # callback(s)
            callbackGetTime=dummy_get_time,
            callbackChecksumCalc=dummy_checksum_calc,
            callbackSendByte=dummy_callback_sendbyte,
            callbackReceivedDatagram=dummy_service_callback,
            # Limits
            frameLengthMax=self.FRAME_MAX_LENGTH,
            datagramLengthMax=self.DATAGRAM_MAX_LENGTH,
            # Service Config
            serviceCount=2,
            services__exact=build_array(
                prlsc_serviceConfig_t, [
                    build_struct(  # [0]
                        prlsc_serviceConfig_t,
                        stream=TRUE,
                        rateLimit=100,
                        onlyTxLatest=FALSE,
                    ),
                    build_struct(  # [1]
                        prlsc_serviceConfig_t,
                        stream=FALSE,
                        rateLimit=0,
                        onlyTxLatest=FALSE,
                    ),
                ]
            ),
        )

    def get_basic_state(self, **kwargs):
        # State
        return build_struct(
            prlsc_state_t,
            errorCode=PRLSC_ERRORCODE_NONE,
            receiver__exact=build_struct(
                prlsc_receiverState_t,
                frame__exact=build_struct(
                    prlsc_rxFrameState_t,
                    state=PRLSC_RXFRAMESTATE_WAIT_STARTBYTE,
                    byteCount=0,
                    curIdx=0,
                    buffer__exact=(c_uint8 * (self.FRAME_MAX_LENGTH + 4))(),
                    framesReceived=0,
                ),
                datagram__exact=build_array(
                    prlsc_rxDatagramState_t, [
                        build_struct(  # [0]
                            prlsc_rxDatagramState_t,
                            buffer__exact=(c_uint8 * self.DATAGRAM_MAX_LENGTH)(),
                            curIdx=0,
                        ),
                        build_struct(  # [1]
                            prlsc_rxDatagramState_t,
                            buffer__exact=(c_uint8 * self.DATAGRAM_MAX_LENGTH)(),
                            curIdx=0,
                        ),
                    ]
                ),
            ),
            transmitterBuffer__exact=build_array(
                prlsc_transmitterBuffer_t, [
                    build_struct(
                        prlsc_transmitterBuffer_t,
                        # Frame-buffer, Streaming service
                        #   only 1 frame is needed in the buffer, but I'd double-buffer it to make sure
                        #   frame transmission isn't blocked if delayed for whatever reason.
                        bufferSize=(self.FRAME_MAX_LENGTH + 4) * 2,
                        buffer__exact=(uint8_t * ((self.FRAME_MAX_LENGTH + 4) * 2))(),
                    ),
                    build_struct(
                        prlsc_transmitterBuffer_t,
                        # Frame-buffer, Diagnostics service
                        #   I think only 3 frames are needed, thrown in 1 more for good measure.
                        #   RAM is limited on the controller (8kB, so I'll be more careful in the real thing)
                        bufferSize=(self.FRAME_MAX_LENGTH + 4) * 4,
                        buffer__exact=(uint8_t * ((self.FRAME_MAX_LENGTH + 4) * 4))(),
                    ),
                ]
            ),
            transmitter__exact=build_struct(
                prlsc_transmitterState_t,
                frameBuffer__exact=(uint8_t * (self.FRAME_MAX_LENGTH + 4))(),
                transmitBuffer__exact=(uint8_t * (self.FRAME_MAX_LENGTH + 4))(),
            ),
            lastTransmitted__exact=build_array(prlsc_time_t, [0, 0]),
        )

    # --- Checksum
    def calc_checksum(self, config, data_bytes):
        # call configured callback
        # (I'm aware this is redundant, but it's done to remove the checksum calculation from PRLSC itself)
        return config.contents.callbackChecksumCalc(build_array(c_uint8, data_bytes), len(data_bytes))

    # --- Building stuff
    def build_datagram(self, service_index=None, subservice_index=0, length=None, data=(1, 2, 3), checksum=None, config=None):
        # Parameter defaults
        if config is None:
            config = self.config
        if service_index is None:
            service_index = self.service_index
        if length is None:
            length = len(data)
        if checksum is None:
            checksum = self.calc_checksum(pointer(config), data)

        # Build datagram struct (and return it)
        return build_struct(
            prlsc_datagram_t,
            serviceIndex=service_index,
            subServiceIndex=subservice_index,
            length=length,
            data__exact=build_array(
                uint8_t, list(data)
            ),
            checksum=checksum,
        )


# Assertion Helpers
frame_data = lambda frame: [frame.data[i] for i in range(frame.length)]
datagram_data = lambda datagram: [datagram.data[i] for i in range(datagram.length)]
build_service_code = lambda service_index, subservice_index: (((service_index & 0x07) << 5) | (subservice_index & 0x1F)) & 0xFF
