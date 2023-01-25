from utilities import *


class DatagramTxTestBase(PrlscEngineTest):
    SERVICE_INDEX = 0  # streaming service (default)

    def setUp(self):
        super(DatagramTxTestBase, self).setUp()
        self.config = self.get_basic_config()
        self.state = self.get_basic_state()
        self.service_index = self.SERVICE_INDEX
        # Assert test setup
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)
        self.assertEqual(self.state.transmitterBuffer[self.service_index].txIdx, 0)
        self.assertEqual(self.state.transmitterBuffer[self.service_index].bufferIdx, 0)

    def tearDown(self):
        super(DatagramTxTestBase, self).tearDown()
        self.reset_state(self.config, self.state)

    def get_frames(self, service_index=None, frame_count=0):
        """Get a set number of frames from the transmitter circular buffer"""
        if service_index is None:
            service_index = self.service_index
        tx_state = self.state.transmitterBuffer[service_index]

        buffer = [tx_state.buffer[i] for i in range(tx_state.bufferSize)]
        buffer += buffer  # duplicate buffer so I can just treat it as a standard array (because lazy)

        frames = []
        i = tx_state.txIdx
        while frame_count > 0:
            self.assertEqual(buffer[i], self.config.frameByteStartFrame)
            # [start, serviceCode, length(2), data0, data1, checksum]
            #  0      1            2          3      4      5
            frame = build_struct(
                prlsc_frame_t,
                serviceIndex=(buffer[i+1] >> 5) & 0x07,
                subServiceIndex=buffer[i+1] & 0x1F,
                length=buffer[i+2],
                data__exact=build_array(c_uint8, buffer[i+3:i+3 + buffer[i+2]]),
                checksum=buffer[i+3 + buffer[i+2]],
            )
            frames.append(frame)

            # debug output : comparing frame stream to it's composition
            log.debug(frame2str(
                frame,
                "frame: from stream [%s]" % (",".join(["%02X" % x for x in buffer[i:i + buffer[i+2] + 4]])),
            ))

            # Increment stuff
            i += buffer[i+2] + 4
            frame_count -= 1
        self.assertLess(i - tx_state.txIdx, tx_state.bufferSize)
        return frames

    def assertFrameChecksumCorrect(self, frame):
        self.assertEqual(
            frame.checksum,
            self.calc_checksum(pointer(self.config), [build_service_code(frame.serviceIndex, frame.subServiceIndex), frame.length] + frame_data(frame))
        )


class DatagramTxTest(DatagramTxTestBase):
    """Datagram Transmit generic tests"""

    def test_bad_service(self):
        datagram = self.build_datagram(service_index=self.config.serviceCount)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.newTxDataFlag, FALSE)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_SERVICEINDEX_BOUNDS)

    def test_no_buffer_frames(self):
        # Make buffer appear full of unsent frames
        tx_state = self.state.transmitterBuffer[self.service_index]
        tx_state.txIdx = 1
        tx_state.bufferIdx = 0
        # Create & send valid datagram
        datagram = self.build_datagram(service_index=self.service_index, data=[])  # as small as possible
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.newTxDataFlag, FALSE)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)


class DatagramTxStreamTest(DatagramTxTestBase):
    """Datagram Transmit tests for streaming service"""
    SERVICE_INDEX = 0  # streaming service

    def setUp(self):
        super(DatagramTxStreamTest, self).setUp()
        # Assert test setup
        self.assertEqual(self.config.services[self.service_index].stream, TRUE) # streaming service

    # --- Boundary Testing (single frame)
    def test_empty_datagram(self):
        data = []
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 1)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertGreater(tx_state.bufferIdx, 0)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frames[0].length, 0)
        self.assertEqual(frame_data(frames[0]), data)
        self.assertEqual(frames[0].checksum, self.calc_checksum(pointer(self.config), data))

    def test_maximum_datagram_length(self):
        self.config.datagramLengthMax = 3
        data = [1, 2, 3]
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 1)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertGreater(tx_state.bufferIdx, 0)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frames[0].length, 3)
        self.assertEqual(frame_data(frames[0]), data)
        self.assertFrameChecksumCorrect(frames[0])

    def test_maximum_datagram_length_exceeded(self):
        self.config.datagramLengthMax = 3
        data = [1, 2, 3, 4]
        datagram = self.build_datagram(data=data)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_TOO_LONG)

    def test_maximum_frame_length(self):
        self.config.frameLengthMax = 3
        data = [1, 2, 3]
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 1)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertGreater(tx_state.bufferIdx, 0)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frames[0].length, 3)
        self.assertEqual(frame_data(frames[0]), data)
        self.assertFrameChecksumCorrect(frames[0])

    def test_maximum_frame_length_exceeded(self):
        self.config.frameLengthMax = 3
        data = [1, 2, 3, 4]
        datagram = self.build_datagram(data=data)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.newTxDataFlag, FALSE)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_TOO_LONG)

    def test_multi_frame_only_latest(self):
        self.config.services[0].onlyTxLatest = TRUE
        datagrams = [
            self.build_datagram(data=[1, 2, 3]),
            self.build_datagram(data=[4, 5, 6, 7]),
        ]
        # Trigger datagram buffering
        for datagram in datagrams:
            self.assertEqual(self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram), 1)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(tx_state.txIdx, 7)  # txIdx should advance over the 1st frame
        self.assertEqual(tx_state.bufferIdx, 7 + 8)
        frames = self.get_frames(frame_count=1)
        self.assertEqual(frame_data(frames[0]), [4, 5, 6, 7])
        self.assertFrameChecksumCorrect(frames[0])


class DatagramTxDiagnosticsTest(DatagramTxTestBase):
    """Datagram Transmit tests for diagnostics service"""
    SERVICE_INDEX = 1  # diagnostics service

    def setUp(self):
        super(DatagramTxDiagnosticsTest, self).setUp()
        # Assert test setup
        self.assertEqual(self.config.services[self.service_index].stream, FALSE) # diagnostics service

    # --- Boundary Testing (single frame)
    def test_empty_datagram(self):
        data = []
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 1)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertGreater(tx_state.bufferIdx, 0)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frames[0].length, 1)  # checksum byte only
        self.assertEqual(frame_data(frames[0]), data + [self.calc_checksum(pointer(self.config), data)])
        self.assertFrameChecksumCorrect(frames[0])

    def test_maximum_datagram_length(self):
        self.config.datagramLengthMax = 3
        data = [1, 2, 3]
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 1)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertGreater(tx_state.bufferIdx, 0)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frames[0].length, 4)  # + checksum byte
        self.assertEqual(frame_data(frames[0]), data + [self.calc_checksum(pointer(self.config), data)])
        self.assertFrameChecksumCorrect(frames[0])

    def test_maximum_datagram_length_exceeded(self):
        self.config.datagramLengthMax = 3
        data = [1, 2, 3, 4]
        datagram = self.build_datagram(data=data)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.newTxDataFlag, FALSE)
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_TOO_LONG)

    def test_maximum_frame_length(self):
        self.config.frameLengthMax = 4
        data = [1, 2, 3]
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.assertEqual(frames_buffered, 2)  # blank frame sent after this one
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertEqual(tx_state.bufferIdx, (4 + 4) + (0 + 4))
        frames = self.get_frames(frame_count=frames_buffered)
        # first frame : all datagram data + checksum
        self.assertEqual(frames[0].length, 4)  # + checksum byte
        self.assertEqual(frame_data(frames[0]), data + [self.calc_checksum(pointer(self.config), data)])
        self.assertFrameChecksumCorrect(frames[0])
        # second frame : empty
        self.assertEqual(frames[1].length, 0)
        self.assertFrameChecksumCorrect(frames[1])

    # --- Multi-frame
    def test_max_buffer(self):
        self.config.datagramLengthMax = 14
        self.config.frameLengthMax = 4
        data = [228, 204, 68, 211, 34, 147, 78, 139, 31, 57, 138, 40, 174, 141]  # 14 bytes (random data)
        # 15th byte will be the datagram's checksum
        # 16th byte cannot be populated without requiring another (empty) frame to transmit
        # conclusion: even though 16 bytes fits in 4 frames of 4 bytes,
        #             we can only transmit a datagram of length <= 14 bytes (when limited to 4 frames)
        # alter config
        tx_state = self.state.transmitterBuffer[self.service_index]
        # buffer bytes required will be the data length + checksum byte + 4 bytes per frame (4 frames)
        # we can't fully populate the buffer, so we also add 1 more byte
        tx_state.bufferSize = (len(data) + 1) + (4 * 4) + 1
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)
        self.assertEqual(frames_buffered, 4)  # blank frame sent after the 2 required
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertEqual(tx_state.bufferIdx, tx_state.bufferSize - 1)  # buffer is full (less 1 byte)
        expected_data = data + [self.calc_checksum(pointer(self.config), data)]
        for (i, frame) in enumerate(self.get_frames(frame_count=frames_buffered)):
            exp_frame_data = expected_data[(i*4):(i*4)+4]
            self.assertEqual(frame_data(frame), exp_frame_data)

    def test_max_buffer_exceeded(self):
        # copy of above with 1 byte less in buffer
        self.config.datagramLengthMax = 14
        self.config.frameLengthMax = 4
        data = [228, 204, 68, 211, 34, 147, 78, 139, 31, 57, 138, 40, 174, 141]  # 14 bytes (random data)
        tx_state = self.state.transmitterBuffer[self.service_index]
        tx_state.bufferSize = (len(data) + 1) + (4 * 4) # + 1
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)
        self.assertEqual(frames_buffered, 0)
        self.assertEqual(self.state.newTxDataFlag, FALSE)

    def test_max_buffer_last_frame_empty(self):
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.config.datagramLengthMax = 8
        self.config.frameLengthMax = 3
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        # buffer bytes required will be the data length + checksum byte + 4 bytes per frame (4 frames)
        # we can't fully populate the buffer, so we also add 1 more byte
        tx_state.bufferSize = (len(data) + 1) + (4 * 4) + 1
        datagram = self.build_datagram(data=data)
        # Trigger datagram buffering
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)
        self.assertEqual(frames_buffered, 4)  # blank frame sent after the 2 required
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        self.assertEqual(tx_state.txIdx, 0)
        self.assertEqual(tx_state.bufferIdx, tx_state.bufferSize - 1)  # buffer is full (index has rotated full circle)
        frames = self.get_frames(frame_count=frames_buffered)
        # frame 1
        self.assertEqual(frames[0].length, 3)
        self.assertEqual(frame_data(frames[0]), [1, 2, 3])
        # frame 2
        self.assertEqual(frames[1].length, 3)
        self.assertEqual(frame_data(frames[1]), [4, 5, 6])
        # frame 3 : last byte is datagram checksum
        self.assertEqual(frames[2].length, 3)
        self.assertEqual(frame_data(frames[2]), [7, 8, self.calc_checksum(pointer(self.config), data)])
        # frame 4 : empty
        self.assertEqual(frames[3].length, 0)

    def test_checksum_only_last_frame(self):
        self.config.datagramLengthMax = 8
        self.config.frameLengthMax = 3
        data = [1, 2, 3, 4, 5, 6]  # 3 frames, the last just contains the datagram's checksum
        datagram = self.build_datagram(data=data)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 3)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frame_data(frames[0]), [1, 2, 3])
        self.assertEqual(frame_data(frames[1]), [4, 5, 6])
        self.assertEqual(frame_data(frames[2]), [self.calc_checksum(pointer(self.config), data)])

    # --- Buffer Overflow
    def test_buffer_overflow(self):
        tx_state = self.state.transmitterBuffer[self.service_index]
        self.config.frameLengthMax = 10
        tx_state.bufferSize = 50
        tx_state.txIdx = 40
        tx_state.bufferIdx = 40
        data = list(range(15))
        datagram = self.build_datagram(data=data)
        frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config), pointer(self.state), datagram)
        # Assertions
        self.assertEqual(frames_buffered, 2)
        self.assertEqual(self.state.newTxDataFlag, TRUE)
        frames = self.get_frames(frame_count=frames_buffered)
        self.assertEqual(frame_data(frames[0]), data[:10])
        self.assertEqual(frame_data(frames[1]), data[10:] + [self.calc_checksum(pointer(self.config), data)])
