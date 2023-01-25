import sys
import os
import inspect
import unittest
import pycparser

from ctypes import (
    c_char,
    c_uint8, c_uint16, c_uint32,
    c_int8, c_int16, c_int32,
    Structure,
    sizeof,
)


# Utility Function(s)
def code2ast(c_code):
    parser = pycparser.c_parser.CParser()
    return parser.parse(c_code)


# Units Under Test
_this_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append(os.path.join(_this_path, '..'))
from ctypefactory import CTypeFactory


class TestTypedef(unittest.TestCase):
    def test_basic_types(self):
        for (names, base_class) in CTypeFactory.BASE_CTYPES_CLASS_MAP.items():
            if base_class is not None:
                c_code = 'typedef {type} var_t;'.format(type=' '.join(names))
                f = CTypeFactory(code2ast(c_code))
                self.assertEqual(set(f.ctypes_map.keys()), {'var_t'})
                self.assertTrue(issubclass(f.ctypes_map['var_t'], base_class))

    def test_pointer(self):
        f = CTypeFactory(code2ast('typedef short int *var_ptr_t;'))
        self.assertEqual(set(f.ctypes_map.keys()), {'var_ptr_t'})
        ptr_type = f.ctypes_map['var_ptr_t']
        self.assertTrue(hasattr(ptr_type, 'contents'))

    def test_struct(self):
        f = CTypeFactory(code2ast("""
            typedef struct {
                unsigned char a;
                short int b;
            } struct_t;
        """))
        self.assertEqual(set(f.ctypes_map.keys()), {'struct_t'})
        self.assertTrue(issubclass(f.ctypes_map['struct_t'], Structure))
        self.assertTrue(issubclass(dict(f.ctypes_map['struct_t']._fields_)['a'], c_uint8))
        self.assertTrue(issubclass(dict(f.ctypes_map['struct_t']._fields_)['b'], c_int16))

    def test_func_ptr_void_void(self):
        f = CTypeFactory(code2ast('typedef void (*callback_t)(void);'))
        self.assertEqual(set(f.ctypes_map.keys()), {'callback_t'})
        self.assertIsNone(f.ctypes_map['callback_t']._restype_)
        self.assertEqual(len(f.ctypes_map['callback_t']._argtypes_), 0)

    def test_func_ptr_void_int(self):
        f = CTypeFactory(code2ast('typedef void (*callback_t)(unsigned char);'))
        self.assertEqual(set(f.ctypes_map.keys()), {'callback_t'})
        self.assertIsNone(f.ctypes_map['callback_t']._restype_)
        self.assertEqual(len(f.ctypes_map['callback_t']._argtypes_), 1)
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._argtypes_[0], c_uint8))

    def test_func_ptr_int_void(self):
        f = CTypeFactory(code2ast('typedef unsigned short int (*callback_t)(void);'))
        self.assertEqual(set(f.ctypes_map.keys()), {'callback_t'})
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._restype_, c_uint16))
        self.assertEqual(len(f.ctypes_map['callback_t']._argtypes_), 0)

    def test_func_ptr_int_int(self):
        f = CTypeFactory(code2ast('typedef unsigned short int (*callback_t)(unsigned char);'))
        self.assertEqual(set(f.ctypes_map.keys()), {'callback_t'})
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._restype_, c_uint16))
        self.assertEqual(len(f.ctypes_map['callback_t']._argtypes_), 1)
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._argtypes_[0], c_uint8))

    def test_func_ptr_int_int_int(self):
        f = CTypeFactory(code2ast('typedef unsigned short int (*callback_t)(unsigned char, unsigned int);'))
        self.assertEqual(set(f.ctypes_map.keys()), {'callback_t'})
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._restype_, c_uint16))
        self.assertEqual(len(f.ctypes_map['callback_t']._argtypes_), 2)
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._argtypes_[0], c_uint8))
        self.assertTrue(issubclass(f.ctypes_map['callback_t']._argtypes_[1], c_uint32))

    def test_nested_basic(self):
        f = CTypeFactory(code2ast("""
            typedef unsigned char uint8_t;
            typedef uint8_t prlsc_checksum_t;
        """))
        self.assertEqual(set(f.ctypes_map.keys()), {'uint8_t', 'prlsc_checksum_t'})
        self.assertTrue(issubclass(f.ctypes_map['uint8_t'], c_uint8))
        self.assertTrue(issubclass(f.ctypes_map['prlsc_checksum_t'], c_uint8))

    def test_nested_struct(self):
        f = CTypeFactory(code2ast("""
            typedef unsigned char uint8_t;
            typedef uint8_t length_t;
            typedef uint8_t data_t;
            typedef struct {
                length_t l;
                data_t *d;
            } struct_t;
        """))
        self.assertTrue(
            set(f.ctypes_map.keys()),
            {'uint8_t', 'length_t', 'data_t'}
        )
        self.assertEqual(
            dict(f.ctypes_map['struct_t']._fields_)['l'],
            f.ctypes_map['length_t']
        )
        self.assertTrue(issubclass(f.ctypes_map['length_t'], f.ctypes_map['uint8_t']))
        self.assertTrue(issubclass(f.ctypes_map['uint8_t'], c_uint8))

    def test_class_name_retention(self):
        """Check that a class name always reflects the typedef it's mapped to"""
        f = CTypeFactory(code2ast("""
            typedef unsigned char uint8_t;
            typedef uint8_t length_t;
            typedef uint8_t data_t;
        """))
        self.assertEqual(set(f.ctypes_map.keys()), {'uint8_t', 'length_t', 'data_t'})
        for key in f.ctypes_map.keys():
            self.assertEqual(f.ctypes_map[key].__name__, key)

    def test_custom_class_map(self):
        """Check that a new class map is picked up and used"""
        c_code_sample = """
            typedef char foo_t;
            typedef int  bar_t;
        """
        # default mapping
        f1 = CTypeFactory(code2ast(c_code_sample))  # using defaults
        self.assertTrue(issubclass(f1.ctypes_map['foo_t'], c_char))
        self.assertTrue(issubclass(f1.ctypes_map['bar_t'], c_int32))
        # custom mapping
        f2 = CTypeFactory(code2ast(c_code_sample), ctypes_class_map={
            ('char',): c_uint8,  # normally c_char
            ('int',): c_int16,  # normally c_int32
        })
        self.assertTrue(issubclass(f2.ctypes_map['foo_t'], c_uint8))
        self.assertTrue(issubclass(f2.ctypes_map['bar_t'], c_int16))

    def test_packing(self):
        c_code_sample = """
            typedef unsigned char uint8_t;
            typedef unsigned short int uint16_t;
            typedef struct {
                uint8_t a;
                uint16_t b;
            } struct_t;
        """
        # -- Without Packing (default ctypes behaviour)
        # Assumption: tests are being run on a > 8-bit OS (not an unreasonable assumption)
        f1 = CTypeFactory(code2ast(c_code_sample))  # using defaults
        self.assertTrue(sizeof(f1.ctypes_map['struct_t']), 4) # uint8_t is padded to 2 bytes
        # -- With Packing
        f2 = CTypeFactory(code2ast(c_code_sample), pack=True)
        self.assertTrue(sizeof(f2.ctypes_map['struct_t']), 3)
