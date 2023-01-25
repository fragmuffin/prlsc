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


class ClosedLoopTestBase(PrlscEngineTest):

    def setUp(self):
        super(ClosedLoopTestBase, self).setUp()
        self.config_tx = self.get_basic_config()
        self.state_tx = self.get_basic_state()
        self.config_rx = self.get_basic_config()
        self.state_rx = self.get_basic_state()

        # --- Configure Transmission
        def send_byte_callback(byte):
            # immediately send it back through to the receiver of the same
            self._prlsc.prlsc_receiveByte(pointer(self.config_rx), pointer(self.state_rx), byte)
        self.config_tx.callbackSendByte = dict(prlsc_config_t._fields_)['callbackSendByte'](send_byte_callback)

        # --- Configure Reception
        self.datagrams = dict((i, []) for i in range(self.config_rx.serviceCount))
        def receive_datagram(datagram):
            # datagram is expected to be consumed by function (because it's memory is re-used for the next
            # incoming datagram... so it's content is copied for the purposes of this test.
            log.debug(datagram2str(datagram, "received frame:"))
            self.datagrams[datagram.serviceIndex].append(build_struct(
                prlsc_datagram_t,
                serviceIndex=datagram.serviceIndex,
                subServiceIndex=datagram.subServiceIndex,
                length=datagram.length,
                data__exact=build_array(uint8_t, datagram_data(datagram)),
                checksum=datagram.checksum,
            ))
        self.config_rx.callbackReceivedDatagram = dict(prlsc_config_t._fields_)['callbackReceivedDatagram'](receive_datagram)

    def txbyte_loop(self, max_calls=100):
        while self._prlsc.prlsc_txByte(pointer(self.config_tx), pointer(self.state_tx)) == TRUE:
            max_calls -= 1
            self.assertGreaterEqual(max_calls, 0, "prlsc_txByte continually returns TRUE")

    def send_datagrams(self, datagrams):
        # --- Buffer datagram(s) frames
        for (i, datagram) in enumerate(datagrams):
            log.debug(datagram2str(datagram, "buffering frame [%s]" % i))
            frames_buffered = self._prlsc.prlsc_transmitDatagram(pointer(self.config_tx), pointer(self.state_tx), datagram)
            self.assertGreater(frames_buffered, 0)  # non-zero returned

        # --- Prepare for transmission
        prepared_service_index = prlsc_serviceIndex_t()
        rate_limit_lifted_in = prlsc_time_t()
        prep = lambda: self._prlsc.prlsc_prepareServiceTransmission(
            pointer(self.config_tx), pointer(self.state_tx),
            pointer(prepared_service_index),
            pointer(rate_limit_lifted_in)
        )

        loop_limit = 20
        while True:
            # infinite loop catch
            loop_limit -= 1
            self.assertGreaterEqual(loop_limit, 0, "prlsc_prepareServiceTransmission continually returns TRUE")

            if prep() == TRUE:
                self.txbyte_loop()
            else:
                if rate_limit_lifted_in.value > 0:
                    # advance time to lift rate-limit
                    self.increment_time(rate_limit_lifted_in.value)
                    continue
                break


class ClosedLoopStreamTest(ClosedLoopTestBase):

    service_index = 0

    def test_empty(self):
        data = []
        self.send_datagrams([self.build_datagram(data=data, config=self.config_tx)])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 1)  # 1 datagram received
        self.assertEqual(len(self.datagrams[1]), 0)
        self.assertEqual(datagram_data(self.datagrams[0][0]), data)
        self.assertEqual(self.datagrams[0][0].checksum, 0)  # no checksum for streamed datagrams

    def test_short(self):
        data = [1, 2, 3]
        self.send_datagrams([self.build_datagram(data=data, config=self.config_tx)])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 1)  # 1 datagram received
        self.assertEqual(len(self.datagrams[1]), 0)
        self.assertEqual(datagram_data(self.datagrams[0][0]), data)
        self.assertEqual(self.datagrams[0][0].checksum, 0) # no checksum for streamed datagrams

    def test_stream_2_frames(self):
        self.send_datagrams([
            self.build_datagram(data=[1, 2, 3], config=self.config_tx),
            self.build_datagram(data=[4, 5, 6], config=self.config_tx),
        ])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 2)
        self.assertEqual(len(self.datagrams[1]), 0)
        self.assertEqual(datagram_data(self.datagrams[0][0]), [1, 2, 3])
        self.assertEqual(datagram_data(self.datagrams[0][1]), [4, 5, 6])

        # rate-limit was obeyed (and time was advanced to overcome tx limitation)?
        self.assertEqual(self.dummy_timer.value, self.config_tx.services[0].rateLimit * len(self.datagrams[0]))


    def test_stream_2_frames_onlylatest(self):
        # Set flag in service
        for config in (self.config_rx, self.config_tx):
            config.services[0].onlyTxLatest = TRUE

        self.send_datagrams([
            self.build_datagram(data=[1, 2, 3], config=self.config_tx), # this frame should be dropped
            self.build_datagram(data=[4, 5, 6], config=self.config_tx),
        ])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 1)
        self.assertEqual(len(self.datagrams[1]), 0)
        self.assertEqual(datagram_data(self.datagrams[0][0]), [4, 5, 6])


class ClosedLoopDiagTest(ClosedLoopTestBase):

    service_index = 1

    def test_empty(self):
        data = []
        self.send_datagrams([self.build_datagram(data=data, config=self.config_tx)])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 0)
        self.assertEqual(len(self.datagrams[1]), 1)  # 1 datagram received
        self.assertEqual(datagram_data(self.datagrams[1][0]), data)
        self.assertEqual(self.datagrams[1][0].checksum, self.calc_checksum(pointer(self.config_rx), data))

    def test_short(self):
        data = [1, 2, 3]
        self.send_datagrams([self.build_datagram(data=data, config=self.config_tx)])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 0)
        self.assertEqual(len(self.datagrams[1]), 1)  # 1 datagram received
        self.assertEqual(datagram_data(self.datagrams[1][0]), data)
        self.assertEqual(self.datagrams[1][0].checksum, self.calc_checksum(pointer(self.config_rx), data))

    def test_multi_frame(self):
        # re-config to shorten limits:
        # target: 3 frames, where last frame is empty
        # Assert test-setup
        for config in [self.config_tx, self.config_rx]:  # both configurations must be the same
            config.frameLengthMax = 3
            self.assertEqual(config.services[1].rateLimit, 0)

        data = [1, 2, 3, 4, 5]  # last byte will be the datagram's checksum
        self.send_datagrams([self.build_datagram(data=data, config=self.config_tx)])

        # Assertions
        self.assertEqual(len(self.datagrams[0]), 0)
        self.assertEqual(len(self.datagrams[1]), 1)  # 1 datagram received
        self.assertEqual(datagram_data(self.datagrams[1][0]), data)
        self.assertEqual(self.datagrams[1][0].checksum, self.calc_checksum(pointer(self.config_rx), data))
