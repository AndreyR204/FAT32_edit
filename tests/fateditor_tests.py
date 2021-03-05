# !/usr/bin/env python3
import datetime
import os
import unittest

from Fat32exp import fsobjects, fateditor
from Fat32exp.bytes_parsers import BytesParser
TEST_IMAGE_ARCHIVE_URL = ""


class FatReaderStaticTests(unittest.TestCase):
    def test_file_parse(self):
        file_expected = fsobjects.File('SHORT.TXT', '', fsobjects.ARCHIVE,
                                       datetime.datetime(day=29, month=7,
                                                         year=2017, hour=14,
                                                         minute=53, second=16,
                                                         microsecond=76000),
                                       datetime.date(day=29, month=7,
                                                     year=2017),
                                       datetime.datetime(day=14, month=7,
                                                         year=2017, hour=20,
                                                         minute=24,
                                                         second=10),
                                       1699)

        parser = BytesParser(
            b'\x53\x48\x4F\x52\x54\x20\x20\x20\x54\x58\x54\x20\x18\x4C\xA8\x76'
            b'\xFD\x4A\xFD\x4A\x00\x00\x05\xA3\xEE\x4A\x55\x00\xA3\x06\x00\x00'
        )
        file_actual = fateditor.parse_file_info(parser)
        self.assertEqual(file_actual, file_expected)

    def test_lfn_part(self):
        lfn_bytes = b'\x43\x38\x04\x38\x04\x2E\x00\x74\x00\x78\x00' \
                    b'\x0F\x00\x31\x74\x00\x00\x00\xFF\xFF\xFF\xFF' \
                    b'\xFF\xFF\xFF\xFF\x00\x00\xFF\xFF\xFF\xFF'
        self.assertEqual(fateditor.get_lfn_part(lfn_bytes)[0],
                         "ии.txt")


TEST_IMAGE_NAME = "TEST-IMAGE"
TESTS_RES_DIR_NAME = "tests_tmp_resources"


def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


class FatReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path_str = get_test_image_path()
        ensure_dir(path_str)
        zip_path_str = get_test_image_path() + ".zip"

        if os.path.exists(path_str):
            os.remove(path_str)
        if os.path.exists(zip_path_str):
            os.remove(zip_path_str)

        print("Downloading TEST-IMAGE.zip...")
        from urllib import request
        request.urlretrieve(TEST_IMAGE_ARCHIVE_URL, zip_path_str)
        print("Download complete.")

        print("Extracting test images... ", end='')
        import zipfile
        with zipfile.ZipFile(zip_path_str, "r") as zip_ref:
            zip_ref.extractall(TESTS_RES_DIR_NAME)
        print("Done.")

    # noinspection SpellCheckingInspection
    def test_image(self):
        with open(get_test_image_path(), "rb") as fi:
            f = fateditor.Fat32Editor(fi, silent_scan=True)
            self.assert_test_image(f)

    def test_image_corrupted(self):
        with open(get_test_image_path() + "-CORRUPTED", "r+b") as fi:
            f = fateditor.Fat32Editor(fi, True, silent_scan=True)
            f.scandisk(True, True, True)
            self.assert_test_image(f)

    def assert_test_image(self, test_image_file):
        names = test_image_file.get_root_directory().get_dir_hierarchy()
        self.assertEqual(names,
                         {
                             "System Volume Information": {
                                 "WPSettings.dat": {},
                                 "IndexerVolumeGuid": {}},
                             "Folder1": {"Astaf.txt": {}, "SHORT.TXT": {}},
                             "Файл.txt": {},
                             "FileQWERTYUIOPASDFGHJKLZXCVBNMAZQWSXEDCRF"
                             "VTGBYHNUJMIKZAWSXEDCRGBY"
                             "HUJNMZQAWSXEDCRTGBYHNUJMIK.txt": {},
                             "VXlZSvgG0z0.jpg": {},
                             "Файл с кириллицей в названии.txt": {},
                             "$RECYCLE": {"DESKTOP.INI": {}}, }
                         )

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(TESTS_RES_DIR_NAME)


def get_test_image_path():
    return TESTS_RES_DIR_NAME + "/" + TEST_IMAGE_NAME


class WriterTests(unittest.TestCase):
    def test_lfn_encoding(self):
        name = "qwertyuioiuhgfdsxdcfgtDASDASDAdd12312312.png"
        parts = fsobjects.to_lfn_parts(name)
        actual = ""
        for part in parts:
            actual = fateditor.get_lfn_part(part)[0] + actual
        self.assertEqual(actual, name)

    def test_turn_short(self):
        name = "qwertyuioiuhgfdsxdcfgtDASDASDAdd12312312.png"
        short_name = fsobjects.get_short_name(name, None)
        self.assertEqual(short_name, "QWERTY~1.PNG")


