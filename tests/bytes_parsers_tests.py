# !/usr/bin/env python3
import datetime
import unittest

from Fat32exp.bytes_parsers import BytesParser
ASCII = "ascii"
UTF16 = "utf16"


class BytesParserTests(unittest.TestCase):
    def test_parse_int_simple(self):
        parser = BytesParser(b'\x5f')
        self.assertEqual(0x5f, parser.parse_int_unsigned(0, 1))

    def test_parse_int_little_big_endian(self):
        parser = BytesParser(b'\xf4\xa3\xff')
        self.assertEqual(0xffa3f4, parser.parse_int_unsigned(0, 3))

    def test_parse_int_start(self):
        parser = BytesParser(b'\xf4\x43\xff\x57\xa3\x55')
        self.assertEqual(0xff43f4, parser.parse_int_unsigned(0, 3))

    def test_parse_int_middle(self):
        parser = BytesParser(b'\xf4\x43\xff\x57\xa3\x55')
        self.assertEqual(0x57ff, parser.parse_int_unsigned(2, 2))

    def test_parse_int_end(self):
        parser = BytesParser(b'\xf4\x43\xff\x57\xa3\x55')
        self.assertEqual(0x55, parser.parse_int_unsigned(5, 1))

    def test_parse_string_start(self):
        parser = BytesParser("Я love Python".encode(encoding=UTF16))
        self.assertEqual("Я love", parser.parse_string(0, 14, encoding=UTF16))

    def test_parse_string_middle(self):
        parser = BytesParser("I love Python".encode(encoding=ASCII))
        self.assertEqual("love", parser.parse_string(2, 4, encoding=ASCII))

    def test_parse_string_end(self):
        parser = BytesParser("Hello, world!".encode(encoding=ASCII))
        self.assertEqual("world!", parser.parse_string(7, 6, encoding=ASCII))

    def test_parse_time_start(self):  # 1:25:00
        # [0010000000001011]
        parser = BytesParser(b'\x20\x0b')
        self.assertEqual(datetime.time(hour=1, minute=25, second=0),
                         parser.parse_time(0))

    def test_parse_time_middle(self):  # 1:25:00
        # 00001111[1000011001100001]1010111100000000
        parser = BytesParser(b'\x0F\x86\x61\xAF\x00')
        self.assertEqual(datetime.time(hour=12, minute=12, second=12),
                         parser.parse_time(1))

    def test_parse_time_end(self):  # 17:35:54
        # 0000101100101000[0111101110001100]
        parser = BytesParser(b'\x0B\x28\x7B\x8C')
        self.assertEqual(datetime.time(hour=17, minute=35, second=54),
                         parser.parse_time(2))
