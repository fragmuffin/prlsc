from utilities import *


class SendByteCallbackBuffer(object):
    buffer = []

    def __init__(self, config):
        self.config = config

    def __enter__(self):
        self.__class__.buffer = []  # clear buffer
        self._old_callback = self.config.callbackSendByte
        self.config.callbackSendByte = dict(prlsc_config_t._fields_)['callbackSendByte'](self.__class__.callback)
        return self

    def __exit__(self, type, value, traceback):
        self.config.callbackSendByte = self._old_callback

    @classmethod
    def callback(cls, byte):
        cls.buffer.append(byte)


class ByteTxTestBase(PrlscEngineTest):

    def setUp(self):
        super(ByteTxTestBase, self).setUp()
        self.config = self.get_basic_config()
        self.state = self.get_basic_state()
        self.tx_state = self.state.transmitter

    def set_buffer(self, bytes):
        for (i, b) in enumerate(bytes):
            self.tx_state.transmitBuffer[i] = b

    def setup_buffer(self, bytes=None, length=None, service_index=0):
        bytes = bytes or []
        self.set_buffer(bytes)
        if length is None:
            length = len(bytes)
        self.tx_state.transmitLength = length
        self.tx_state.transmitServiceIndex = service_index
        self.tx_state.state = PRLSC_TXBYTESTATE_START
        self.tx_state.bufferIndex = 0

    def txbyte_loop(self, max_calls=100):
        while self._prlsc.prlsc_txByte(pointer(self.config), pointer(self.state)) == TRUE:
            max_calls -= 1
            self.assertGreaterEqual(max_calls, 0, "we're stuck in a loop here")

    def encoded(self, data):
        enc_data = data[:1]
        for b in data[1:]:
            if b == self.config.frameByteStartFrame:
                enc_data += [self.config.frameByteEsc, self.config.frameByteEscStart]
            elif b == self.config.frameByteEsc:
                enc_data += [self.config.frameByteEsc, self.config.frameByteEscEsc]
            else:
                enc_data += [b]
        return enc_data

    def build_frame_bytes(self, service_index=0, subservice_index=0, service_code=None, length=None, data=None, checksum=None, include_start=True):
        """Build stream of bytes representing a frame"""
        # Parameter Defaults
        data = data or []
        if length is None:
            length = len(data)
        if service_code is None:
            service_code = build_service_code(service_index, subservice_index)
        if checksum is None:
            checksum = self.calc_checksum(pointer(self.config), [service_code, length] + list(data))

        # Build stream (& return)
        frame_stream = []
        if include_start:
            frame_stream.append(self.config.frameByteStartFrame)
        frame_stream += [service_code, length] + list(data) + [checksum]
        return frame_stream


class ByteTxTest(ByteTxTestBase):

    def test_simple_transmit(self):
        data = [1, 2, 3]
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))

    def test_nothing_prepared_to_transmit(self):
        data = []
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            #self.assertEqual(callback_obj.buffer, self.encoded(data))
            # Note: transmission buffer is designed to send a frame, which cannot be empty, so
            #       as a result, a length of zero will actually transmit the first 2 bytes
            #       (which are initialised as 0's)
            self.assertEqual(callback_obj.buffer, [0, 0])  # meh, close enough

    def test_empty_frame(self):
        data = self.build_frame_bytes()
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))

    def test_encoding_service_code(self):
        data = self.build_frame_bytes(service_code=self.config.frameByteStartFrame)
        self.setup_buffer(bytes=data)  # setup ignore the service_code in the stream
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))

    def test_encoding_length(self):
        data = self.build_frame_bytes(length=self.config.frameByteStartFrame)
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))

    def test_encoding_data_startbyte(self):
        data = self.build_frame_bytes(data=[self.config.frameByteStartFrame])
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))
            # Redundant, but also enforces the behaviour of "self.encoded()"
            self.assertEqual(callback_obj.buffer[0], self.config.frameByteStartFrame)  # un-encoded
            self.assertEqual(callback_obj.buffer[3:5], [self.config.frameByteEsc, self.config.frameByteEscStart])

    def test_encoding_data_esc(self):
        data = self.build_frame_bytes(data=[self.config.frameByteEsc])
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))
            # Redundant, but also enforces the behaviour of "self.encoded()"
            self.assertEqual(callback_obj.buffer[0], self.config.frameByteStartFrame)  # un-encoded
            self.assertEqual(callback_obj.buffer[3:5], [self.config.frameByteEsc, self.config.frameByteEscEsc])

    def test_encoding_data_multiple_esc(self):
        # Tests that the state machine gets back to normal transmission after an escape byte
        data = self.build_frame_bytes(data=[self.config.frameByteStartFrame, 1, 2, 3, self.config.frameByteEsc, 4, 5, 6])
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))
            # Redundant, but also enforces the behaviour of "self.encoded()"
            self.assertEqual(callback_obj.buffer[0], self.config.frameByteStartFrame)  # un-encoded
            self.assertEqual(
                callback_obj.buffer[3:13],
                [self.config.frameByteEsc, self.config.frameByteEscStart, 1, 2, 3] +
                [self.config.frameByteEsc, self.config.frameByteEscEsc, 4, 5, 6]
            )

    def test_encoding_checksum(self):
        data = self.build_frame_bytes(checksum=self.config.frameByteStartFrame)
        self.setup_buffer(bytes=data)
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, self.encoded(data))

    def test_state_donothing(self):
        self.setup_buffer()
        self.tx_state.state = PRLSC_TXBYTESTATE_DO_NOTHING;
        with SendByteCallbackBuffer(self.config) as callback_obj:
            self.txbyte_loop()
            self.assertEqual(callback_obj.buffer, [])  # callback never called
