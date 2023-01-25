from utilities import *

class MemcpyTest(PrlscEngineTest):
    pass

    #def startUp(self):
    #    super(MemcpyTest, self).setUp()

    def cast_and_call(self, call, params):
        for (i, param) in enumerate(params):
            if isinstance(param, tuple):
                (arr, index) = param
                params[i] = cast(addressof(arr) + (sizeof(arr._type_) * index), call.argtypes[i])
        call(*params)

def array_to_list(arr):
    return [arr[i] for i in range(len(arr))]


class MemcpyUtilTest_memcpy_flat2circular(MemcpyTest):

    def test_copy_nothing(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, [0xFF] * 5)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 0), (arr, 0), 0, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])  # original content; no change
        self.assertEqual(circle[10], 0)

    def test_single_item(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, [0xFF] * 5)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 0), (arr, 0), 1, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(circle[10], 0)

    def test_partial_no_overflow(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, [1, 2, 3, 4, 5])
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 0), (arr, 0), 4, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [1, 2, 3, 4, 0, 0, 0, 0, 0, 0])
        self.assertEqual(circle[10], 0)

    def test_partial_with_overflow(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, [1, 2, 3, 4, 5])
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 8), (arr, 0), 4, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [3, 4, 0, 0, 0, 0, 0, 0, 1, 2])
        self.assertEqual(circle[10], 0)

    def test_one_revolution_from_zero(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, list(range(1, 11, 1)))
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 0), (arr, 0), 10, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(circle[10], 0)

    def test_one_revolution_from_middle(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, list(range(1, 11, 1)))
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 3), (arr, 0), 10, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [8, 9, 10, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(circle[10], 0)

    def test_multiple_revolutions(self):
        circle = build_array(c_uint8, [0] * 11)
        arr = build_array(c_uint8, list(range(50)))
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_flat2circular,
            [(circle, 3), (arr, 0), 35, circle, 10]
        )
        self.assertEqual(array_to_list(circle)[:10], [27, 28, 29, 30, 31, 32, 33, 34, 25, 26])
        self.assertEqual(circle[10], 0)


class MemcpyUtilTest_memcpy_circular2flat(MemcpyTest):

    def test_copy_nothing(self):
        circle = build_array(c_uint8, [0xFF] * 3)
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 0), (circle, 0), 0, circle, 3]
        )
        self.assertEqual(array_to_list(circle), [0xFF] * 3)
        self.assertEqual(array_to_list(arr), [0] * 10)  # original content; no change

    def test_single_item(self):
        circle = build_array(c_uint8, [1, 2, 3])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 0), (circle, 0), 1, circle, 3]
        )
        self.assertEqual(array_to_list(circle), [1, 2, 3])
        self.assertEqual(array_to_list(arr), [1] + [0] * 9)  # original content; no change

    def test_partial_no_overflow(self):
        # circle start : arr start
        circle = build_array(c_uint8, [1, 2, 3, 4, 5])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 0), (circle, 0), 3, circle, 5]
        )
        self.assertEqual(array_to_list(circle), [1, 2, 3, 4, 5])
        self.assertEqual(array_to_list(arr), [1, 2, 3, 0, 0, 0, 0, 0, 0, 0])  # original content; no change
        # circle end : arr end
        circle = build_array(c_uint8, [1, 2, 3, 4, 5])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 7), (circle, 2), 3, circle, 5]
        )
        self.assertEqual(array_to_list(circle), [1, 2, 3, 4, 5])
        self.assertEqual(array_to_list(arr), [0, 0, 0, 0, 0, 0, 0, 3, 4, 5])  # original content; no change
        # circle end : arr start
        circle = build_array(c_uint8, [1, 2, 3, 4, 5])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 0), (circle, 2), 3, circle, 5]
        )
        self.assertEqual(array_to_list(circle), [1, 2, 3, 4, 5])
        self.assertEqual(array_to_list(arr), [3, 4, 5, 0, 0, 0, 0, 0, 0, 0])  # original content; no change
        # circle start : arr end
        circle = build_array(c_uint8, [1, 2, 3, 4, 5])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 7), (circle, 0), 3, circle, 5]
        )
        self.assertEqual(array_to_list(circle), [1, 2, 3, 4, 5])
        self.assertEqual(array_to_list(arr), [0, 0, 0, 0, 0, 0, 0, 1, 2, 3])  # original content; no change

    def test_partial_with_overflow(self):
        circle = build_array(c_uint8, [1, 2, 3, 4, 5, 6])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 2), (circle, 4), 4, circle, 6]
        )
        self.assertEqual(array_to_list(arr), [0, 0, 5, 6, 1, 2, 0, 0, 0, 0])  # original content; no change

    def test_one_revolution_from_zero(self):
        circle = build_array(c_uint8, [1, 2, 3, 4, 5, 6])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 1), (circle, 0), 6, circle, 6]
        )
        self.assertEqual(array_to_list(arr), [0, 1, 2, 3, 4, 5, 6, 0, 0, 0])  # original content; no change

    def test_one_revolution_from_middle(self):
        circle = build_array(c_uint8, [1, 2, 3, 4, 5, 6])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 1), (circle, 3), 6, circle, 6]
        )
        self.assertEqual(array_to_list(arr), [0, 4, 5, 6, 1, 2, 3, 0, 0, 0])  # original content; no change

    def test_multiple_revolutions(self):
        circle = build_array(c_uint8, [1, 2, 3, 4, 5, 6])
        arr = build_array(c_uint8, [0] * 10)
        self.cast_and_call(
            self._prlsc.prlsc_memcpy_circular2flat,
            [(arr, 3), (circle, 2), 20, circle, 6]
        )
        self.assertEqual(array_to_list(arr), [0, 0, 0, 3, 4, 5, 6, 1, 2, 0])  # original content; no change

