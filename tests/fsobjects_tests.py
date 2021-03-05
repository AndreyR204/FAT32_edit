# !/usr/bin/env python3
import unittest

from Fat32exp import fsobjects



class FileTests(unittest.TestCase):
    def test_get_absolute_path(self):
        root = fsobjects.File("root", "root", fsobjects.DIRECTORY)
        self.assertEqual(root.get_absolute_path(), "root")

        folder1 = fsobjects.File("Folder1", "Folder1", fsobjects.DIRECTORY)
        folder1.parent = root
        self.assertEqual(folder1.get_absolute_path(), "root/Folder1")

        folder2 = fsobjects.File("Folder2", "Folder2", fsobjects.DIRECTORY)
        folder2.parent = folder1
        self.assertEqual(folder2.get_absolute_path(), "root/Folder1/Folder2")

    def test_size_format_byte(self):
        file = fsobjects.File("file", "file", size_bytes=1)
        self.assertEqual("1 byte", file.get_size_str())

    def test_size_format_bytes(self):
        file = fsobjects.File("file", "file", size_bytes=5)
        self.assertEqual("5 bytes", file.get_size_str())

    def test_size_format_kibibytes(self):
        file = fsobjects.File("file", "file", size_bytes=855310)
        self.assertEqual("835.26 KiB (855310 bytes)", file.get_size_str())

    def test_size_format_mebibytes(self):
        file = fsobjects.File("file", "file", size_bytes=6389353)
        self.assertEqual("6.09 MiB (6389353 bytes)", file.get_size_str())

    def test_size_format_gibibytes(self):
        file = fsobjects.File("file", "file", size_bytes=281382002220)
        self.assertEqual("262.06 GiB (281382002220 bytes)",
                         file.get_size_str())

    def test_attr_str_full(self):
        file = fsobjects.File("file", "file",
                              fsobjects.READ_ONLY |
                              fsobjects.HIDDEN |
                              fsobjects.SYSTEM |
                              fsobjects.VOLUME_ID |
                              fsobjects.DIRECTORY |
                              fsobjects.ARCHIVE)
        self.assertEqual("read_only, hidden, system, "
                         "volume_id, directory, archive"
                         , file.get_attributes_str())

    def test_attr_str_part(self):
        file = fsobjects.File("file", "file",
                              fsobjects.READ_ONLY |
                              fsobjects.HIDDEN |
                              fsobjects.ARCHIVE)
        self.assertEqual("read_only, hidden, archive",
                         file.get_attributes_str())

    def test_attr_str_empty(self):
        file = fsobjects.File("file", "file")
        self.assertEqual("no attributes", file.get_attributes_str())