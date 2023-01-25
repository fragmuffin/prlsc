from utilities import *


class ServiceReadyTest(PrlscEngineTest):

    def setUp(self):
        super(ServiceReadyTest, self).setUp()
        self.config = self.get_basic_config()
        self.state = self.get_basic_state()
        self.service_index = prlsc_serviceIndex_t()
        self.service_index.value = 200
        self.rate_limit_lifted_in = prlsc_time_t()
        self.rate_limit_lifted_in.value = 15  # just setting to non-zero for assessment
        # --- Assert test setup
        # tests in this class may assume the following settings.
        # if these assertions fail, consider each of this class' tests
        self.assertEqual(self.config.services[0].rateLimit, 100) # stream
        self.assertEqual(self.config.services[1].rateLimit, 0) # diag
        for i in range(self.config.serviceCount):
            tx_buffer = self.state.transmitterBuffer[i]
            self.assertEqual(tx_buffer.bufferIdx, 0)
            self.assertEqual(tx_buffer.txIdx, 0) # if both are zero, buffer is empty

    def set_last_sent(self, sent_times):
        self.assertLessEqual(len(sent_times), self.config.serviceCount)
        for (service_index, sent_time) in enumerate(sent_times):
            if sent_time is None:
                continue
            self.state.lastTransmitted[service_index] = sent_time

    def call_prlsc_prepareServiceTransmission(self):
        """Standard call to prlsc_transmitServiceReady (just makes test code less repetitive)"""
        return self._prlsc.prlsc_prepareServiceTransmission(
            pointer(self.config), pointer(self.state),
            pointer(self.service_index),
            pointer(self.rate_limit_lifted_in)
        )

    def buffer_frame(self, service_index, data):
        if isinstance(data, str):
            data = [ord(c) for c in data]
        index = lambda idx: idx % self.state.transmitterBuffer[service_index].bufferSize
        tx_buffer = self.state.transmitterBuffer[service_index]
        cur_idx = tx_buffer.bufferIdx
        tx_buffer.buffer[index(cur_idx + 0)] = self.config.frameByteStartFrame
        tx_buffer.buffer[index(cur_idx + 1)] = service_index
        tx_buffer.buffer[index(cur_idx + 2)] = len(data)
        for (i, b) in enumerate(data):
            tx_buffer.buffer[index(cur_idx + 3 + i)] = b
        checksum = self.calc_checksum(pointer(self.config), [service_index, len(data)] + data)
        tx_buffer.buffer[index(cur_idx + 3 + len(data))] = checksum
        tx_buffer.bufferIdx = index(tx_buffer.bufferIdx + len(data) + 4) # advance buffer

    # --- Generic tests
    def test_no_buffers(self):
        # Get ready state
        ready = self.call_prlsc_prepareServiceTransmission()
        self.assertEqual(ready, FALSE)
        self.assertEqual(self.service_index.value, 200) # no change
        self.assertEqual(self.rate_limit_lifted_in.value, 0) # set to zero

    # --- Selection Basis: Buffer Content
    def test_buffers_service_0(self):
        tx_buffer = self.state.transmitterBuffer[0]
        tx_buffer.bufferIdx = 10  # non-zero
        # remove rate limiting
        for i in range(self.config.serviceCount):
            self.config.services[i].rateLimit = 0
        # Get ready state
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, TRUE)
        self.assertEqual(self.service_index.value, 0)
        self.assertEqual(self.rate_limit_lifted_in.value, 0)

    def test_buffers_service_1(self):
        tx_buffer = self.state.transmitterBuffer[1]
        tx_buffer.bufferIdx = 10  # non-zero
        # remove rate limiting
        for i in range(self.config.serviceCount):
            self.config.services[i].rateLimit = 0
        # Get ready state
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, TRUE)
        self.assertEqual(self.service_index.value, 1)
        self.assertEqual(self.rate_limit_lifted_in.value, 0)

    # --- Selection Basis: Rate Limiting
    def test_rate_limit_bounds_not_limited(self):
        # populate buffer (pretend)
        tx_buffer = self.state.transmitterBuffer[0]
        tx_buffer.bufferIdx = 10  # non-zero
        # 1 unit since service0 was sent (should be rate-limited)
        self.set_last_sent([999, 0])
        self.set_time(1000)
        # --- limiting (asserting test basis; avoid false positive)
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, FALSE)
        self.assertEqual(self.service_index.value, 0)
        self.assertEqual(self.rate_limit_lifted_in.value, 99)
        # --- frame sent exactly rateLimit ago
        self.service_index.value = 200
        self.set_last_sent([1000 - 100, 0])  # assuming rateLimit for service0== 100
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, TRUE)
        self.assertEqual(self.service_index.value, 0)
        self.assertEqual(self.rate_limit_lifted_in.value, 0)

    def test_rate_limit_bounds_limited(self):
        # populate buffer (pretend)
        tx_buffer = self.state.transmitterBuffer[0]
        tx_buffer.bufferIdx = 10  # non-zero
        # set way outside the scope
        self.set_last_sent([0, 0])
        self.set_time(1000)
        # --- not limiting (asserting test basis; avoid false positive)
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, TRUE)
        self.assertEqual(self.service_index.value, 0)
        # --- frame sent exactly rateLimit ago
        self.set_last_sent([1000 - 99, 0])  # assuming rateLimit for service0== 100
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, FALSE)
        self.assertEqual(self.rate_limit_lifted_in.value, 1)  # 1 tick short

    # --- Rate limit - clock overflow
    def test_rate_limit_clock_overflow(self):
        # populate buffer (pretend)
        tx_buffer = self.state.transmitterBuffer[0]
        tx_buffer.bufferIdx = 10  # non-zero
        # 99 time units since service0 sent (with uint16 overflow)
        self.set_last_sent([0x10000 - 50, 0])
        self.set_time(49)  # 99 ticks since service0
        # --- limiting (asserting test basis; avoid false positive)
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, FALSE)
        self.assertEqual(self.service_index.value, 0)
        self.assertEqual(self.rate_limit_lifted_in.value, 1)  # 1 tick short
        # --- frame sent exactly rateLimit ago
        self.service_index.value = 200
        self.set_time(50)  # 100 ticks since service0
        ready = self.call_prlsc_prepareServiceTransmission()
        # Assertions
        self.assertEqual(ready, TRUE)
        self.assertEqual(self.service_index.value, 0)
        self.assertEqual(self.rate_limit_lifted_in.value, 0)

    # --- Circular buffer overflow tests
    def test_tx_buffer_overflow(self):
        self.set_time(200)
        tx_buffer = self.state.transmitterBuffer[0]
        # Buffer a frame so the:
        #   - first part is at the end of the ring-buffer
        #   - the last part is at the start of the ring-buffer
        # adjust the error so every frame byte is tested as being the last byte
        for error in range(1, 15):
            tx_buffer.bufferIdx = tx_buffer.bufferSize - error
            tx_buffer.txIdx = tx_buffer.bufferIdx
            self.buffer_frame(0, list(range(10)))
            ready = self.call_prlsc_prepareServiceTransmission()
            # Assertions
            self.assertEqual(ready, TRUE)
            self.assertLess(tx_buffer.bufferIdx, tx_buffer.bufferSize)
            self.assertLess(tx_buffer.txIdx, tx_buffer.bufferSize)
            self.assertEqual(tx_buffer.txIdx, tx_buffer.bufferIdx)
            tx_state = self.state.transmitter
            self.assertEqual(
                tx_state.transmitBuffer[:13],
                [0xC0, 0, 10] + list(range(10)),
            )
            # clear buffer (For next eval)
            for i in range(13):
                tx_state.transmitBuffer[i] = 0x00

