from utilities import *

class ByteStreamTest(PrlscEngineTest):
    def feed_stream(self, config, state, byte_list, actively_assert=True):
        prlsc = self._prlsc
        log.debug("feed_stream: 0x" + " ".join(["%02X" % b for b in byte_list]))
        accum_list = []
        for byte in byte_list:
            if actively_assert:
                self.assertEqual(state.receiver.frame.framesReceived, 0)
            prlsc.prlsc_receiveByte(pointer(config), pointer(state), byte)
            accum_list.append(int(state.receiver.frame.curIdx))
        log.debug("acc        : 0x" + " ".join(["%02X" % b for b in accum_list]))


class TestReceiveByte(ByteStreamTest):
    # frameByteStartFrame    = 0xC0
    # frameByteEsc           = 0xDB
    # frameByteEscStart      = 0xDC
    # frameByteEscEsc        = 0xDD
    SEQ_C0 = [0xDB, 0xDC]
    SEQ_DB = [0xDB, 0xDD]

    def encode_stream(self, service_index=0, subservice_index=0, service_code=None, length=None, data=(1, 2, 3), checksum=None):
        # Frame Composition:
        #   - start_byte
        #   - service_code (service_index << 5 | subservice_index)
        #   - data_length
        #   - [data bytes]
        #   - checksum

        # pre-fills
        if service_code is None:
            service_code = build_service_code(service_index, subservice_index)
        if length is None:
            length = len(data)
        if checksum is None:
            checksum = self.calc_checksum(pointer(self.config), [service_code, length] + list(data))

        # encode stream
        encoded = [self.config.frameByteStartFrame]
        for byte in [service_code, length] + list(data) + [checksum]:
            if byte == self.config.frameByteStartFrame:
                encoded += [self.config.frameByteEsc, self.config.frameByteEscStart]
            elif byte == self.config.frameByteEsc:
                encoded += [self.config.frameByteEsc, self.config.frameByteEscEsc]
            else:
                encoded += [byte]

        return encoded

    FRAME_ERROR_CODES = [
        PRLSC_ERRORCODE_RXFRAME_BAD_ESC,
        PRLSC_ERRORCODE_RXFRAME_SERVICEINDEX_BOUNDS,
        PRLSC_ERRORCODE_RXFRAME_TOO_LONG,
        PRLSC_ERRORCODE_RXFRAME_BAD_CHECKSUM,
    ]

    def setUp(self):
        super(TestReceiveByte, self).setUp()
        self.config = self.get_basic_config()
        self.state = self.get_basic_state()

    def tearDown(self):
        super(TestReceiveByte, self).tearDown()
        self.reset_state(self.config, self.state)

    def frames_received(self):
        return self.state.receiver.frame.framesReceived

    def test_single(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream())
        self.assertEqual(self.frames_received(), 1)
        self.assertNotIn(self.state.errorCode, self.FRAME_ERROR_CODES)

    def test_multiple(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(), False)
        self.assertEqual(self.frames_received(), 1)
        self.feed_stream(self.config, self.state, self.encode_stream(), False)
        self.assertEqual(self.frames_received(), 2)
        self.assertNotIn(self.state.errorCode, self.FRAME_ERROR_CODES)

    def test_long(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(data=range(100)))
        self.assertEqual(self.frames_received(), 1)
        self.assertNotIn(self.state.errorCode, self.FRAME_ERROR_CODES)

    def test_mid_stream(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, [1, 2, 3, 4] + self.encode_stream())
        self.assertEqual(self.frames_received(), 1)
        self.assertNotIn(self.state.errorCode, self.FRAME_ERROR_CODES)

    def test_escape_bytes(self):
        # shortcut variables (non-functional)
        startByte = self.config.frameByteStartFrame
        escByte = self.config.frameByteEsc

        # Build streams with characters to escape
        escape_streams = (
            # Escape Characters : Start Byte
            #('esc_start_service', self.encode_stream(service_index=startByte)),
            ('esc_start_checksum',   self.encode_stream(service_code=1, data=[62], checksum=startByte)),
            ('esc_start_data_end',   self.encode_stream(service_code=1, data=[1, 2, startByte])),
            ('esc_start_data_start', self.encode_stream(service_code=1, data=[startByte, 2, 3])),
            ('esc_start_dlc',        self.encode_stream(service_code=1, length=startByte, data=[1] * startByte)),
            ('esc_start_multiple',   self.encode_stream(service_code=1, data=[startByte] * 4)),
            # Escape Characters : Esc Byte
            #('esc_esc_service', self.encode_stream(service_index=escByte)),
            ('esc_esc_checksum',     self.encode_stream(service_code=1, data=[35], checksum=escByte)),
            ('esc_esc_data_end',     self.encode_stream(service_code=1, data=[1, 2, escByte])),
            ('esc_esc_data_start',   self.encode_stream(service_code=1, data=[escByte, 2, 3])),
            ('esc_esc_dlc',          self.encode_stream(service_code=1, length=escByte, data=[1] * escByte)),
            ('esc_esc_multiple',     self.encode_stream(service_code=1, data=[escByte] * 4)),
        )
        # All escaped streams should come through without a problem
        for (name, data) in escape_streams:
            self.assertEqual(
                self.frames_received(), 0  # nothing to start with
            )
            self.feed_stream(self.config, self.state, data, actively_assert=False)
            self.assertEqual(
                self.frames_received(), 1, # just 1 received
                "stream '%s' received wrong number of frames" % name
            )
            self.assertNotIn(  # error codes expected, but none reporting 'frame' issues
                self.state.errorCode, self.FRAME_ERROR_CODES,
                "stream '%s' raised error code #%i" % (name, self.state.errorCode)
            )
            self.reset_state(self.config, self.state)

    def test_bad_checksum(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(service_index=1, data=[0x5A], checksum=0xFF))
        self.assertEqual(self.frames_received(), 0)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_RXFRAME_BAD_CHECKSUM)

    def test_bad_esc(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, [self.config.frameByteStartFrame, 1, 1, self.config.frameByteEsc, 0xFF, 0x24])
        self.assertEqual(self.frames_received(), 0)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_RXFRAME_BAD_ESC)

    def test_bad_service(self):
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(service_index=10))
        self.assertEqual(self.frames_received(), 0)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_RXFRAME_SERVICEINDEX_BOUNDS)

    def test_length_inside_boundary(self):
        self.config.frameLengthMax = 3
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(length=3, data=[1, 2, 3]))
        self.assertEqual(self.frames_received(), 1)
        self.assertNotIn(self.state.errorCode, self.FRAME_ERROR_CODES)

    def test_length_outside_boundary(self):
        self.config.frameLengthMax = 3
        self.assertEqual(self.frames_received(), 0)
        self.feed_stream(self.config, self.state, self.encode_stream(length=4, data=[1, 2, 3, 4]))
        self.assertEqual(self.frames_received(), 0)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_RXFRAME_TOO_LONG)

