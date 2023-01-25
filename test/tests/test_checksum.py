from utilities import *


class TestChecksumCalc(PrlscEngineTest):

    def test_checksum(self):
        config = self.get_basic_config()
        self.assertEqual(self.calc_checksum(pointer(config), []),               0)
        self.assertEqual(self.calc_checksum(pointer(config), [0xFF]),           1)
        self.assertEqual(self.calc_checksum(pointer(config), [0x5A, 0xA5]),     1)
        self.assertEqual(self.calc_checksum(pointer(config), [0xFE]),           2)
        self.assertEqual(self.calc_checksum(pointer(config), [1]),              0xFF)
        self.assertEqual(self.calc_checksum(pointer(config), list(range(100))), 0xAA)
