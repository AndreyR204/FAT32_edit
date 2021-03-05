# !/usr/bin/env python3
import unittest

from Fat32exp import fsobjects, dirbrowser


def generate_files_from_names(names):
    for name in names:
        yield fsobjects.File("", name)


class DirectoryBrowserTests(unittest.TestCase):
    def test_get_dir_content_names(self):
        names = ["File1.txt", "File2.txt", "File3.txt"]
        d = fsobjects.File("DIR", "",
                           fsobjects.DIRECTORY)
        d.content = list(generate_files_from_names(names))
        self.assertEqual(list(dirbrowser._get_dir_content_names(d)),
                         names)

    def test_get_dir_content_names_empty_dir(self):
        d = fsobjects.File("DIR", "",
                           fsobjects.DIRECTORY)
        d.content = []
        self.assertEqual(list(dirbrowser._get_dir_content_names(d)), [])

    def test_get_dir_content_names_not_a_dir(self):
        file = fsobjects.File("", "File.txt")
        with self.assertRaises(NotADirectoryError):
            list(dirbrowser._get_dir_content_names(file))

    def test_cd(self):
        d = fsobjects.File("DIR", "", fsobjects.DIRECTORY)
        d1 = fsobjects.File("DIR1", "", fsobjects.DIRECTORY)
        d.content = [d1]
        names = ["File1.txt", "File2.txt", "File3.txt"]
        d1.content = list(generate_files_from_names(names))

        db = dirbrowser.DirectoryBrowser(root=d)
        db.change_directory("DIR1")

        self.assertEqual(db.current, d1)

    def test_cd_fail_not_found(self):
        d = fsobjects.File("DIR", "", fsobjects.DIRECTORY)
        d1 = fsobjects.File("DIR1", "", fsobjects.DIRECTORY)
        d.content = [d1]
        names = ["File1.txt", "File2.txt", "File3.txt"]
        d1.content = list(generate_files_from_names(names))

        db = dirbrowser.DirectoryBrowser(root=d)

        with self.assertRaises(dirbrowser.DirectoryBrowserError):
            db.change_directory("dir")

    def test_cd_fail_not_a_directory(self):
        d = fsobjects.File("DIR", "", fsobjects.DIRECTORY)
        d1 = fsobjects.File("DIR1", "", fsobjects.DIRECTORY)
        d.content = [d1]
        names = ["File1.txt", "File2.txt", "File3.txt"]
        d1.content = list(generate_files_from_names(names))

        db = dirbrowser.DirectoryBrowser(root=d)

        with self.assertRaises(dirbrowser.DirectoryBrowserError):
            db.change_directory("DIR1/File1.txt")

    def test_cd_deep(self):
        d_root = fsobjects.File("DIR", "", fsobjects.DIRECTORY)
        d = fsobjects.File("DIR1", "", fsobjects.DIRECTORY)
        d1 = fsobjects.File("DIR2", "", fsobjects.DIRECTORY)
        d_root.content = [d]
        d.content = [d1]
        names = ["File1.txt", "File2.txt", "File3.txt"]
        d1.content = list(generate_files_from_names(names))

        db = dirbrowser.DirectoryBrowser(root=d_root)
        db.change_directory("DIR1/DIR2")

        self.assertEqual(db.current, d1)

