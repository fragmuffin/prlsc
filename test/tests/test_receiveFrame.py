from utilities import *


class DatagramTest(PrlscEngineTest):

    def setUp(self):
        super(DatagramTest, self).setUp()
        self.config = self.get_basic_config()
        self.state = self.get_basic_state()

    def tearDown(self):
        super(DatagramTest, self).tearDown()
        self.reset_state(self.config, self.state)

    def build_frame(self, **kwargs):
        frame = prlsc_frame_t()
        # service code
        service_index = kwargs.get('serviceIndex', 0)
        subservice_index = kwargs.get('subServiceIndex', 0)
        frame.serviceIndex = service_index
        frame.subServiceIndex = subservice_index
        # data
        frame_databytes = kwargs.get('data', [])
        frame.length = c_uint8(kwargs.get('length', len(frame_databytes)))
        frame.data = (c_uint8 * len(frame_databytes))()
        for (i, byte) in enumerate(frame_databytes):
            frame.data[i] = c_uint8(byte)
        # checksum
        if 'checksum' in kwargs:
            frame.checksum = prlsc_checksum_t(kwargs['checksum'])
        else:
            if self.config.services[service_index].stream == TRUE:
                frame.checksum = prlsc_checksum_t(0x00)
            else:
                frame.checksum = self.calc_checksum(pointer(self.config), frame_data(frame))

        return frame

    def build_diag_frames(self, service_index=1, subservice_index=0, frame_max_data=None, data=(1, 2, 3), checksum=None):
        if frame_max_data is None:
            frame_max_data = self.config.frameLengthMax
        if checksum is None:
            checksum = self.calc_checksum(pointer(self.config), data)

        # add checksum to data
        data = list(data) + [checksum]

        self.assertEqual(self.config.services[service_index].stream, FALSE)
        frames = []
        for chunk_index in range(0, len(data), frame_max_data):
            frame = prlsc_frame_t()

            # build frame data
            frame_bytes = data[chunk_index:chunk_index + frame_max_data]
            frame_data = (c_uint8 * len(frame_bytes))()
            for (i, value) in enumerate(frame_bytes):
                frame_data[i] = c_uint8(value)

            # build frame struct
            frame = build_struct(
                prlsc_frame_t,
                serviceIndex=service_index,
                subServiceIndex=subservice_index,
                length=len(frame_bytes),
                data__exact=frame_data,
                checksum=self.calc_checksum(pointer(self.config), frame_bytes),
            )
            frames.append(frame)

        # add empty frame if data size exactly divides
        if len(data) % frame_max_data == 0:
            frames.append(build_struct(
                prlsc_frame_t,
                serviceIndex=service_index,
                subServiceIndex=subservice_index,
                length=0,
            ))

        return frames

def display_datagram_callback(datagram):
    """Display datagram as info (for debugging)"""
    log.warning(datagram2str(datagram, "display_datagram_callback(%r):" % datagram))
    return PRLSC_RESPONSE_CODE_POSITIVE


class DatagramCallbackBuffer(object):
    buffer = []

    def __init__(self, config, service_index=0):
        self.config = config
        self.service_index = service_index

    def __enter__(self):
        self.__class__.buffer = []  # clear buffer
        # temporarily configure configured callback to this class
        self._old_callback = self.config.callbackReceivedDatagram
        self.config.callbackReceivedDatagram = dict(prlsc_config_t._fields_)['callbackReceivedDatagram'](self.__class__.callback)
        return self

    def __exit__(self, type, value, traceback):
        self.config.callbackReceivedDatagram = self._old_callback

    @classmethod
    def callback(cls, datagram):
        cls.buffer.append(datagram)
        log.info(datagram2str(datagram, "DatagramCallbackBuffer.callback(%r):" % datagram))


class TestDatagramStreamBasics(DatagramTest):
    """Test Frames building Stream Datagrams"""

    def test_basic(self):
        """Simple stream frame is passed upstream as a datagram"""
        service_index = 0
        self.assertEqual(self.config.services[service_index].stream, TRUE)  # verify test setup
        frame = self.build_frame(serviceIndex=service_index, data=[1, 2, 3, 4])
        log.info(frame2str(frame))
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame)
            self.assertEqual(len(buffer_obj.buffer), 1)
            datagram = buffer_obj.buffer[0]
            self.assertEqual(datagram.serviceIndex, service_index)
            self.assertEqual(datagram.length, frame.length)
            self.assertEqual(
                [datagram.data[i] for i in range(datagram.length)],
                [frame.data[i] for i in range(frame.length)]
            )
            self.assertEqual(datagram.checksum, 0)

    def test_multiple_datagrams(self):
        service_index = 0
        frame1 = self.build_frame(serviceIndex=service_index, data=[1, 2, 3, 4])
        frame2 = self.build_frame(serviceIndex=service_index, data=[5, 6, 7, 8])
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            # First Frame
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame1)
            self.assertEqual(len(buffer_obj.buffer), 1)
            datagram1 = buffer_obj.buffer[0]
            self.assertEqual(
                [datagram1.data[i] for i in range(datagram1.length)],
                [frame1.data[i] for i in range(frame1.length)]
            )

            # Second Frame
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame2)
            self.assertEqual(len(buffer_obj.buffer), 2)
            datagram2 = buffer_obj.buffer[1]
            self.assertEqual(
                [datagram2.data[i] for i in range(datagram2.length)],
                [frame2.data[i] for i in range(frame2.length)]
            )

    def test_multiple_streams(self):
        new_service = build_struct(
            prlsc_serviceConfig_t,
            stream=TRUE,
            rateLimit=100,
        )
        self.assertEqual(self.config.services[0].stream, TRUE)
        self.config.services[1] = new_service  # replace default diagnostic service with another stream

        # Manually configure datagram callbacks
        # (DatagramCallbackBuffer can only handle one callback assignment at a time)
        datagram_buffer = {0: [], 1: []}
        def callback(datagram):
            datagram_buffer[datagram.serviceIndex].append(datagram)
        self.config.callbackReceivedDatagram = dict(prlsc_config_t._fields_)['callbackReceivedDatagram'](callback)

        # Assertion helpers
        buffer_lengths = lambda: [len(datagram_buffer[i]) for i in range(2)]

        # Define Frames (in the order they're to be sent; interlaced)
        frame0_1 = self.build_frame(serviceIndex=0, data=[1, 2])
        frame1_1 = self.build_frame(serviceIndex=1, data=[4, 5])
        frame0_2 = self.build_frame(serviceIndex=0, data=[2, 3])
        frame1_2 = self.build_frame(serviceIndex=1, data=[6, 7])

        # Send through frames
        self.assertEqual(buffer_lengths(), [0, 0])
        # frame0_1
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame0_1)
        self.assertEqual(buffer_lengths(), [1, 0])
        self.assertEqual(datagram_data(datagram_buffer[0][0]), [1, 2])
        # frame1_1
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame1_1)
        self.assertEqual(buffer_lengths(), [1, 1])
        self.assertEqual(datagram_data(datagram_buffer[1][0]), [4, 5])
        # frame0_2
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame0_2)
        self.assertEqual(buffer_lengths(), [2, 1])
        self.assertEqual(datagram_data(datagram_buffer[0][1]), [2, 3])
        # frame1_2
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame1_2)
        self.assertEqual(buffer_lengths(), [2, 2])
        self.assertEqual(datagram_data(datagram_buffer[1][1]), [6, 7])


class TestDatagramDiag(DatagramTest):
    """Test Frames building Diagnostics Datagrams"""

    def test_basic(self):
        """Simple diag frame is passed upstream as a datagram"""
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # verify test setup
        frame = self.build_frame(serviceIndex=service_index, data=[1, 2, 3, 4, 0xF6])
        log.info(frame2str(frame))
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frame)
            self.assertEqual(len(buffer_obj.buffer), 1)
            datagram = buffer_obj.buffer[0]
            self.assertEqual(datagram.serviceIndex, service_index)
            self.assertEqual(datagram.length, frame.length - 1)
            self.assertEqual(
                [datagram.data[i] for i in range(datagram.length)],
                [frame.data[i] for i in range(frame.length - 1)]  # only works if single frame
            )
            self.assertEqual(datagram.checksum, frame.data[frame.length - 1])  # only works if single frame

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_multi_frame_typical(self):
        """Multiple frames form a single diagnostics datagram, not partial"""
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # verify test setup
        self.config.frameLengthMax = 3
        frames = self.build_diag_frames(service_index=service_index, data=[1, 2, 3, 4])

        # Check test setup
        self.assertEqual(len(frames), 2)
        self.assertEqual(frame_data(frames[0]), [1, 2, 3])
        self.assertEqual(frame_data(frames[1]), [4, self.calc_checksum(pointer(self.config), [1, 2, 3, 4])])

        # Send frames
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[0])
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[1])
            self.assertEqual(len(buffer_obj.buffer), 1)
            self.assertEqual(datagram_data(buffer_obj.buffer[0]), [1, 2, 3, 4])

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_multi_frame_last_empty(self):
        """
        Multiple frames form a single diagnostics datagram, last frame is empty
        (signifying end of datagram, without adding any data to it)
        """
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # verify test setup
        self.config.frameLengthMax = 3
        frames = self.build_diag_frames(service_index=service_index, data=[1, 2, 3, 4, 5])
        # checksum of whole datagram is added to data, causing byte count to == 6

        # Check test setup
        self.assertEqual(len(frames), 3)
        self.assertEqual(frame_data(frames[0]), [1, 2, 3])
        self.assertEqual(frame_data(frames[1]), [4, 5, self.calc_checksum(pointer(self.config), [1, 2, 3, 4, 5])])
        self.assertEqual(frame_data(frames[2]), [])

        # Send frames
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[0])
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[1])
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[2])
            self.assertEqual(len(buffer_obj.buffer), 1)
            self.assertEqual(datagram_data(buffer_obj.buffer[0]), [1, 2, 3, 4, 5])

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_empty_datagram(self):
        """Datagram with no data"""
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # verify test setup
        self.config.frameLengthMax = 3
        frames = self.build_diag_frames(service_index=service_index, data=[])

        # Check Test Setup
        self.assertEqual(len(frames), 1)
        self.assertEqual(frame_data(frames[0]), [self.calc_checksum(pointer(self.config), [])])

        # Send Frame
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self.assertEqual(len(buffer_obj.buffer), 0)
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[0])
            self.assertEqual(len(buffer_obj.buffer), 1)
            datagram = buffer_obj.buffer[0]
            self.assertEqual(datagram_data(datagram), [])
            self.assertEqual(datagram.length, 0)

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_multiple_datagrams(self):
        """Send multiple datagrams"""
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # verify test setup
        self.config.frameLengthMax = 10
        dg_data = [
            list(range(15)),  # multiple frames (normal)
            [],         # empty data
            list(range(19)),  # multiple frames (last one has no data)
            list(range(38)),  # another normal one
        ]

        grouped_frames = [self.build_diag_frames(service_index=service_index, data=d) for d in dg_data]

        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            for (i, frames) in enumerate(grouped_frames):
                self.assertEqual(len(buffer_obj.buffer), i)
                for f in frames:
                    self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
                self.assertEqual(len(buffer_obj.buffer), i + 1)
                datagram = buffer_obj.buffer[i]
                self.assertEqual(datagram_data(datagram), dg_data[i])

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_multiple_diagnostic_services(self):
        self.config.frameLengthMax = 6
        new_service = build_struct(
            prlsc_serviceConfig_t,
            stream=FALSE,
            rateLimit=0,
        )
        self.config.services[0] = new_service  # replace default stream service with a diagnostic service
        self.assertEqual(self.config.services[1].stream, FALSE)

        # Manually configure datagram callbacks
        # (DatagramCallbackBuffer can only handle one callback assignment at a time)
        datagram_buffer = {0: [], 1: []}
        def callback(datagram):
            datagram_buffer[datagram.serviceIndex].append(datagram)
        self.config.callbackReceivedDatagram = dict(prlsc_config_t._fields_)['callbackReceivedDatagram'](callback)

        # Assertion helpers
        buffer_lengths = lambda: [len(datagram_buffer[i]) for i in range(2)]

        # Define Frames
        frames0 = self.build_diag_frames(service_index=0, data=list(range(11)))
        frames1 = self.build_diag_frames(service_index=1, data=list(range(100, 0, -1)))

        # Send frames (in an interlaced fashion)
        self.assertEqual(buffer_lengths(), [0, 0])
        # frames1[0:10]
        for f in frames1[0:10]:
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
        self.assertEqual(buffer_lengths(), [0, 0])
        # frames0[0:1]
        for f in frames0[0:2]:
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
        self.assertEqual(buffer_lengths(), [0, 0])
        # frames1[10:16]
        for f in frames1[10:16]:
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
        self.assertEqual(buffer_lengths(), [0, 0])
        # frames0[2]
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames0[2])
        self.assertEqual(buffer_lengths(), [1, 0])
        self.assertEqual(datagram_data(datagram_buffer[0][0]), list(range(11)))
        # frames1[16]
        self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames1[16])
        self.assertEqual(buffer_lengths(), [1, 1])
        self.assertEqual(datagram_data(datagram_buffer[1][0]), list(range(100, 0, -1)))

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_datagram_max_length_boundary(self):
        self.config.datagramLengthMax = 5
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # check test setup
        frames = self.build_diag_frames(service_index=service_index, data=list(range(5)))
        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), frames[0])
            self.assertEqual(len(buffer_obj.buffer), 1)
            datagram = buffer_obj.buffer[0]
            self.assertEqual(datagram_data(datagram), list(range(5)))

        self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

    def test_datagram_max_length_exceeded(self):
        self.config.frameLengthMax = 8
        self.config.datagramLengthMax = 5
        service_index = 1
        self.assertEqual(self.config.services[service_index].stream, FALSE)  # check test setup

        with DatagramCallbackBuffer(self.config, service_index) as buffer_obj:
            # Send datagram that's too big
            for f in self.build_diag_frames(service_index=service_index, data=list(range(6))):
                self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
            self.assertEqual(len(buffer_obj.buffer), 0)
            self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_TOO_LONG)

            # Send good datagram
            self.state.errorCode = PRLSC_ERRORCODE_NONE
            for f in self.build_diag_frames(service_index=service_index, data=list(range(3))):
                self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
            self.assertEqual(len(buffer_obj.buffer), 1) # got one!
            datagram = buffer_obj.buffer[0]
            self.assertEqual(datagram_data(datagram), list(range(3)))
            self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)

            # Send multiframe datagram that's too big
            # (this holds state machine in an error state until current over-sized datagram is done sending)
            for f in self.build_diag_frames(service_index=service_index, data=list(range(10))):
                self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
            self.assertEqual(len(buffer_obj.buffer), 1) # no more datagrams
            self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_DATAGRAM_TOO_LONG)

            # Send good datagram
            self.state.errorCode = PRLSC_ERRORCODE_NONE
            for f in self.build_diag_frames(service_index=service_index, data=list(range(4, 0, -1))):
                self._prlsc.prlsc_receiveFrame(pointer(self.config), pointer(self.state), f)
            self.assertEqual(len(buffer_obj.buffer), 2)  # got another one!
            datagram = buffer_obj.buffer[1]
            self.assertEqual(datagram_data(datagram), list(range(4, 0, -1)))
            self.assertEqual(self.state.errorCode, PRLSC_ERRORCODE_NONE)


