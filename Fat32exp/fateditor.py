# !/usr/bin/env python3
import datetime
import itertools
import math
import os
import pathlib

import Fat32exp.dirbrowser as dirbrowser
import Fat32exp.fsobjects as fsobjects
from Fat32exp.bytes_parsers import FileBytesParser, BytesParser

BYTES_PER_DIR_ENTRY = 32
BYTES_PER_FAT32_ENTRY = 4


def format_fat_address(address):
    return address & 0x0FFFFFFF


def parse_file_first_cluster_number(entry_parser):
    cluster_number = (entry_parser.parse_int_unsigned(20, 2) << 16) + \
                     entry_parser.parse_int_unsigned(26, 2)
    return format_fat_address(cluster_number)


def parse_creation_datetime(entry_parser):
    try:
        creation_time_millis = entry_parser.parse_int_unsigned(13, 1)
        creation_datetime = entry_parser.parse_time_date(14)
        creation_datetime += datetime.timedelta(
            milliseconds=creation_time_millis)
    except ValueError:
        return None
    return creation_datetime


def get_lfn_part(entry_bytes):
    utf8_chars_pos = itertools.chain(range(1, 11, 2), range(14, 26, 2),
                                     range(28, 32, 2))
    lfn_part = ""
    for pos in utf8_chars_pos:
        char = entry_bytes[pos:pos + 2]
        if char != b'\x00\x00' and char != b'\xFF\xFF':
            lfn_part += char.decode("utf_16")
        else:
            break
    return lfn_part, entry_bytes[0x0D]


def parse_file_info(entry_parser, long_file_name_buffer=""):
    attributes = entry_parser.parse_int_unsigned(11, 1)
    is_directory = bool(attributes & fsobjects.DIRECTORY)

    name_part = entry_parser.parse_string(0, 8, "cp866", "strict").strip()
    extension_part = entry_parser.parse_string(8, 3, "cp866",
                                               "strict").strip()
    short_name = name_part + (
        ('.' + extension_part) if not is_directory else "")

    creation_datetime = parse_creation_datetime(entry_parser)

    try:
        last_access_date = entry_parser.parse_date(18)
    except ValueError:
        last_access_date = None
    try:
        last_modification_datetime = entry_parser.parse_time_date(22)
    except ValueError:
        last_modification_datetime = None

    file_size_bytes = entry_parser.parse_int_unsigned(0 + 28, 4)

    return fsobjects.File(short_name,
                          long_file_name_buffer,
                          attributes,
                          creation_datetime,
                          last_access_date,
                          last_modification_datetime,
                          file_size_bytes)


def validate_fs_info(fs_info_bytes):
    if (fs_info_bytes[0:4] != b'\x52\x52\x61\x41' or
                fs_info_bytes[0x1E4:0x1E4 + 4] != b'\x72\x72\x41\x61' or
                fs_info_bytes[0x1FC:0x1FC + 4] != b'\x00\x00\x55\xAA'):
        raise ValueError("Incorrect format of FS Info sector")


def find_directory(source, internal_path):
    dir = dirbrowser.find(
        name=internal_path,
        source=source,
        priority='directory')
    if dir is None:
        raise dirbrowser. \
            DirectoryBrowserError('"' + internal_path + '" not found.')
    if not dir.is_directory:
        raise dirbrowser. \
            DirectoryBrowserError(
            '"' + internal_path + '" is not a directory.')
    return dir


def get_time_stamps(external_path):
    stats = os.stat(external_path)
    modification_datetime = datetime.datetime.fromtimestamp(stats.st_mtime)
    creation_datetime = datetime.datetime.fromtimestamp(stats.st_ctime)
    last_access_date = datetime.datetime. \
        fromtimestamp(stats.st_atime).date()
    return creation_datetime, last_access_date, modification_datetime


def print_no_new_line(s, **kwargs):
    print(s, end='', flush=True, **kwargs)


class Fat32Reader:
    log_clusters_usage = False
    log_clusters_usage_adv = False
    repair_file_size_mode = False
    used_clusters = dict()
    errors_found = 0
    errors_repaired = 0

    def __init__(self, fat_image_file,):
        self.valid = True

        self._fat_image_file = fat_image_file
        self._read_fat32_boot_sector()
        self._parse_data_area()

    def _parse_data_area(self):
        self._data_area_start = self._sectors_to_bytes(self.reserved_sectors
                                                       + self.fat_amount
                                                       * self.sectors_per_fat)

    def _read_fat32_boot_sector(self):
        bytes_parser = FileBytesParser(self._fat_image_file)
        self._parse_boot_sector(bytes_parser)

        self.sectors_per_fat = bytes_parser.parse_int_unsigned(0x24, 4)
        self.active_fat_number = bytes_parser.parse_int_unsigned(0x28, 2)
        self.root_catalog_first_cluster = bytes_parser.parse_int_unsigned(0x2c,
                                                                          4)
        self._fs_info_sector = bytes_parser.parse_int_unsigned(0x30, 2)
        self._parse_boot_sector(bytes_parser)
        self.boot_sector_copy_sector = bytes_parser.parse_int_unsigned(0x32, 2)


    def _parse_boot_sector(self, bytes_parser):
        self.bytes_per_sector = bytes_parser.parse_int_unsigned(0x0b, 2)
        self.sectors_per_cluster = bytes_parser.parse_int_unsigned(0x0d, 1)
        self.reserved_sectors = bytes_parser.parse_int_unsigned(0x0e, 2)
        self.fat_amount = bytes_parser.parse_int_unsigned(0x10, 1)

        self.total_sectors = bytes_parser.parse_int_unsigned(0x13, 2)
        self.hidden_sectors_before_partition = bytes_parser.parse_int_unsigned(
            0x1c, 4)

        if self.total_sectors == 0:
            self.total_sectors = bytes_parser.parse_int_unsigned(0x20, 4)

    def _sectors_to_bytes(self, sectors):
        return self.bytes_per_sector * sectors

    def _sector_slice(self, start_sector, end_sector=None):
        if end_sector is None:
            end_sector = start_sector + 1
        start = self._sectors_to_bytes(start_sector)
        end = self._sectors_to_bytes(end_sector)
        length = end - start
        self._fat_image_file.seek(start)
        return self._fat_image_file.read(length)

    def _cluster_slice(self, start_cluster, end_cluster=None):
        if end_cluster is None:
            end_cluster = start_cluster + 1
        return self._sector_slice(
            start_cluster * self.sectors_per_cluster,
            end_cluster * self.sectors_per_cluster
        )

    def _get_fat_start_end_sectors(self, fat_number):
        start = self.reserved_sectors + fat_number * self.sectors_per_fat
        end = start + self.sectors_per_fat
        return start, end

    def _get_active_fat_start_end_sectors(self):
        return self._get_fat_start_end_sectors(self.active_fat_number)

    def _get_fat(self, fat_number):
        start, end = self._get_fat_start_end_sectors(fat_number)
        return self._sector_slice(start, end)

    def get_root_directory(self):
        if self.log_clusters_usage or self.log_clusters_usage_adv:
            for cluster in self._get_cluster_chain(
                    self.root_catalog_first_cluster):
                self.used_clusters[cluster] = True
        root = fsobjects.File("", "", fsobjects.DIRECTORY, None, None, None,
                              0, self.root_catalog_first_cluster)
        root.content = self._parse_dir_files(
            self.get_data_from_cluster_chain(self.root_catalog_first_cluster),
            root)
        return root

    def _parse_dir_files(self, data, directory):
        files = list()
        long_file_name_buffer = ""
        lfn_checksum_buffer = -1
        for start in range(0, len(data) - BYTES_PER_DIR_ENTRY,
                           BYTES_PER_DIR_ENTRY):
            entry_bytes = data[start:start + BYTES_PER_DIR_ENTRY]
            if entry_bytes[0] == 0x00:
                # directory has no more entries
                break
            if entry_bytes[0] == 0xE5:
                # unused entry
                continue
            if entry_bytes[0] == 0x05:
                entry_bytes = b'\xe5' + entry_bytes[1:]

            entry_parser = BytesParser(entry_bytes)
            attributes = entry_parser.parse_int_unsigned(11, 1)

            if attributes == fsobjects.LFN:  # Long file name entry
                lfn_part, lfn_checksum = get_lfn_part(entry_bytes)
                long_file_name_buffer = lfn_part + \
                                        long_file_name_buffer
                lfn_checksum_buffer = lfn_checksum

            elif attributes & fsobjects.VOLUME_ID:
                pass
            else:
                try:
                    file = self._parse_file_entry(entry_parser,
                                                  long_file_name_buffer,
                                                  lfn_checksum_buffer)
                    requires_size_check = self.repair_file_size_mode and \
                                          not file.is_directory
                    requires_cluster_usage_logging = \
                        self.log_clusters_usage \
                        or self.log_clusters_usage_adv
                    if requires_cluster_usage_logging or \
                            requires_size_check:
                        cluster_size = self.get_cluster_size()
                        cluster_seq_num = start // cluster_size
                        entry_start_in_cluster = start % cluster_size
                        chain = self._get_cluster_chain(
                            directory._start_cluster)
                        cluster_num = \
                            chain[
                                cluster_seq_num]
                        start_bytes, _ = \
                            self._get_cluster_start_end_relative_to_data_start(
                                cluster_num)
                        entry_start = start_bytes + entry_start_in_cluster + self._data_area_start
                    if requires_cluster_usage_logging:
                        self._log_file_clusters_usage(file=file,
                                                      entry_start=entry_start)
                except ValueError:
                    continue

                if requires_size_check:
                    self._repair_file_size(file, entry_start)

                file.parent = directory
                files.append(file)
                long_file_name_buffer = ""
                lfn_checksum_buffer = -1
        return files

    def _parse_file_entry(self, entry_parser,
                          long_file_name_buffer,
                          lfn_checksum):

        file = parse_file_info(entry_parser, long_file_name_buffer)

        if file.short_name == ".." or file.short_name == ".":
            # ".." - parent directory
            # "." - current directory
            raise ValueError("Entry refers to the " +
                             ("directory itself" if
                              file.short_name == "." else
                              "parent directory."))

        if long_file_name_buffer:
            checksum = fsobjects.get_short_name_checksum(file.short_name)

        name = "directory" if file.is_directory else "file"
        file.content = self._parse_file_content(entry_parser, file)
        return file

    def _parse_file_content(self, entry_parser, file):
        first_cluster = file._start_cluster = \
            parse_file_first_cluster_number(entry_parser)

        if first_cluster == 0:
            return list() if file.is_directory else None

        return None if not file.is_directory else \
            self._parse_dir_files(
                self.get_data_from_cluster_chain(first_cluster), file
            )

    def _get_data(self, cluster):
        parser = FileBytesParser(self._fat_image_file, self._data_area_start)
        start, end = self._get_cluster_start_end_relative_to_data_start(
            cluster)
        data = parser.get_bytes_end(start, end)
        return data

    def _get_cluster_start_end_relative_to_data_start(self, cluster_number):
        start = self._sectors_to_bytes(
            self.sectors_per_cluster * (cluster_number - 2))
        end = self._sectors_to_bytes(
            self.sectors_per_cluster * (cluster_number - 2 + 1))
        return start, end

    def get_data_from_cluster_chain(self, first_cluster):
        current_cluster = first_cluster
        data = bytes()
        cluster_chain = str(first_cluster)
        while True:
            data += self._get_data(current_cluster)
            try:
                current_cluster = self._get_next_file_cluster(current_cluster)
                cluster_chain += "-" + str(current_cluster)
            except EOFError:
                return data

    def _get_next_file_cluster(self, prev_cluster):
        table_value = self.get_fat_value(prev_cluster)
        if table_value < 0x0FFFFFF7 and table_value != 1:
            return table_value
        else:
            raise EOFError

    def _validate_fat(self, do_raise=True):
        self.scan_info("Validating FAT tables equality...")
        prev_fat = None
        for i in range(self.fat_amount):
            fat = self._get_fat(i)
            if prev_fat is not None:
                self.scan_info("Comparing FAT #{:d} and #{:d} ... "
                               "".format(i - 1, i),
                               flush=True, end='')
                if prev_fat != fat:
                    error_message = "File allocation tables #{:d} " \
                                    "and #{:d} are not equal!".format(i - 1, i)
                    self.valid = False
                    if do_raise:
                        raise FATReaderError(error_message)
                    else:
                        self.scan_info(error_message)
                else:
                    self.scan_info("OK")
            prev_fat = fat

    def get_fat_value(self, cluster):
        active_fat_start, _ = self._get_active_fat_start_end_sectors()
        fat_parser = FileBytesParser(self._fat_image_file,
                                     active_fat_start * self.bytes_per_sector)

        value_start = cluster * BYTES_PER_FAT32_ENTRY
        return format_fat_address(
            fat_parser.parse_int_unsigned(value_start, BYTES_PER_FAT32_ENTRY))

    def get_cluster_size(self):
        return self.sectors_per_cluster * self.bytes_per_sector

    def _get_cluster_chain(self, first_cluster):
        cluster_chain = [first_cluster]
        current_cluster = first_cluster
        while True:
            try:
                current_cluster = self._get_next_file_cluster(current_cluster)
                cluster_chain.append(current_cluster)
            except EOFError:
                break
        return cluster_chain

    def _repair_file_size(self, file, start):
        pass

    def _log_file_clusters_usage(self, file, entry_start):
        pass


def is_cluster_reserved(cluster_fat_value):
    return 0xFFFFFF0 >= cluster_fat_value >= 0xFFFFFF6


def is_cluster_bad(cluster_fat_value):
    return cluster_fat_value == 0xFFFFFF7


class Fat32Editor(Fat32Reader):
    def _write_fat_value(self, cluster, value):
        reserved = self.get_fat_value(cluster) & 0xF0000000
        self._write_fat_bytes(cluster,
                              int.to_bytes(
                                  reserved | (value & 0x0FFFFFFF),
                                  length=BYTES_PER_FAT32_ENTRY,
                                  byteorder='little'
                              ))

    def _write_eof_fat_value(self, cluster):
        self._write_fat_value(cluster, 0x0FFFFFFF)

    def _write_fat_bytes(self, cluster, bytes_):
        for i in range(self.fat_amount):
            fat_start, _ = self._get_fat_start_end_sectors(i)

            value_start = self._sectors_to_bytes(fat_start) + \
                          cluster * BYTES_PER_FAT32_ENTRY
            self._write_content_to_image(value_start, bytes_)

    def _find_free_clusters(self, clusters_amount):
        required = clusters_amount
        if clusters_amount < 0:
            raise ValueError("Cluster amount cannot be negative!")
        if clusters_amount == 0:
            return list()

        free_clusters = list()
        start_sector, end_sector = self._get_active_fat_start_end_sectors()
        fat = self._sector_slice(start_sector, end_sector)
        fat_parser = BytesParser(fat)

        empty_fat_value = b'\x00' * BYTES_PER_FAT32_ENTRY
        for i in range(self._first_free_cluster * BYTES_PER_FAT32_ENTRY,
                       len(fat), BYTES_PER_FAT32_ENTRY):
            if clusters_amount == 0:
                self._first_free_cluster = i // BYTES_PER_FAT32_ENTRY
                self._update_first_free_cluster()
                self._decrease_free_clusters_amount_by(required)
                break
            value = fat_parser.get_bytes(i, BYTES_PER_FAT32_ENTRY)
            if value == empty_fat_value:
                free_clusters.append(i // BYTES_PER_FAT32_ENTRY)
                clusters_amount -= 1
        if clusters_amount > 0:
            raise ValueError("Have not found enough free clusters "
                             "(Required: {}, Found: {})."
                             .format(required, required - clusters_amount))
        return free_clusters

    def write_to_image(self, external_path, internal_path,
                       directory=None) -> fsobjects.File:
        """
        Writes file to image, returns File
        """
        path = pathlib.Path(external_path)
        if not path.exists():
            raise FileNotFoundError(str(path) + " not found.")

        if directory is None:
            directory = find_directory(self.get_root_directory(),
                                       internal_path)

        name = ("/" + str(path.absolute()).replace("\\", "/")).split("/")[-1]
        short_name = fsobjects.get_short_name(name, directory=directory)
        attributes = fsobjects.DIRECTORY if path.is_dir() else 0

        creation_datetime, last_access_date, modification_datetime = \
            get_time_stamps(external_path)

        file = fsobjects.File(
            long_name=name,
            short_name=short_name,
            create_datetime=creation_datetime,
            change_datetime=modification_datetime,
            last_open_date=last_access_date,
            attributes=attributes)

        file.parent = directory
        first_cluster, size_bytes = self._write_external_file_content(path,
                                                                      file)

        file._start_cluster = first_cluster
        file._size_bytes = size_bytes

        self._append_content_to_dir(directory, file.to_directory_entries())

        return file

    def _write_external_file_content(self, external_path, file):
        cluster_size = self.get_cluster_size()
        clusters = list()
        size_bytes = 0
        ext_path_abs = str(external_path.absolute())
        if external_path.is_dir():
            file.content = list()
            first_cluster = file._start_cluster = \
                self._write_content_and_get_first_cluster(bytes(cluster_size))
            file._size_bytes = 0

            self._append_content_to_dir(file, file.to_directory_entries(
                is_dot_self_entry=True))
            if file.parent:
                self._append_content_to_dir(file,
                                            file.parent.to_directory_entries(
                                                is_dot_parent_entry=True))

            for name in os.listdir(ext_path_abs):
                path = os.path.join(ext_path_abs, name)
                file.content.append(self.write_to_image(path, "", file))
        else:
            with open(ext_path_abs, 'rb') as f:
                f.seek(0)
                while True:
                    b = f.read(cluster_size)
                    size_bytes += len(b)
                    if len(b) == 0:
                        break
                    if len(clusters) == 0:
                        clusters.append(
                            self._write_content_and_get_first_cluster(b))
                    else:
                        clusters.append(
                            self.append_cluster_to_file(clusters[-1], b))
            first_cluster = clusters[0] if len(clusters) > 0 else 0
        return first_cluster, size_bytes

    def append_cluster_to_file(self, last_cluster_number, cluster):
        """
        Appends cluster-sized content to cluster chain and returns number
        of the cluster appended to chain
        """
        cluster_size = self.get_cluster_size()
        if len(cluster) > cluster_size:
            raise ValueError('"cluster" is too big!')
        elif len(cluster) < cluster_size:
            cluster = cluster + b'\x00' * (cluster_size - len(cluster))

        cluster_num = self._write_content_and_get_first_cluster(cluster)
        if last_cluster_number >= 0:
            self._write_fat_value(last_cluster_number, cluster_num)
        self._write_eof_fat_value(cluster_num)
        return cluster_num

    def _write_content_and_get_first_cluster(self, content):
        """
        Writes content and returns number of first cluster
        """
        if len(content) == 0:
            return -1
        cluster_size = self.get_cluster_size()
        clusters_required = math.ceil(len(content) / cluster_size)
        clusters = self._find_free_clusters(clusters_required)
        prev_cluster = -1

        for content_start, cluster_num in \
                zip(range(0, len(content), cluster_size), clusters):
            if prev_cluster != -1:
                self._write_fat_value(prev_cluster, cluster_num)
            content_end = content_start + cluster_size

            cluster_start, _ = self._get_cluster_start_end_relative_to_data_start(
                cluster_num)
            cluster_start += self._data_area_start
            _ += self._data_area_start
            writing_content = content[content_start:content_end]
            self._write_content_to_image(cluster_start, writing_content)

            prev_cluster = cluster_num

        self._write_eof_fat_value(clusters[-1])
        return clusters[0]

    def _write_content_to_image(self, start, content):
        self._fat_image_file.seek(start)
        self._fat_image_file.write(content)
        self._fat_image_file.flush()

    def _append_content_to_dir(self, directory, entries):
        for entry, start in zip(entries,
                                self._find_dir_empty_entries(directory,
                                                             len(entries))):
            self._write_content_to_image(start, entry)

    def _find_dir_empty_entries(self, directory, amount_required):
        if amount_required <= 0:
            raise ValueError("Amount must be positive")
        fat_parser = FileBytesParser(self._fat_image_file)
        clusters = self._get_cluster_chain(directory._start_cluster)

        entries_start = list()

        data_start = self._data_area_start
        for cluster_num in clusters:
            start, end = self._get_cluster_start_end_relative_to_data_start(
                cluster_num)
            for entry_start in range(data_start + start, data_start + end,
                                     BYTES_PER_DIR_ENTRY):
                entry_bytes = fat_parser.get_bytes(entry_start, 1)
                if entry_bytes[0] == 0x00 or entry_bytes[0] == 0xE5:
                    entries_start.append(entry_start)
                    if len(entries_start) == amount_required:
                        return entries_start
                else:
                    entries_start.clear()

        entries_required = amount_required - len(entries_start)
        clusters_required = math.ceil(
            entries_required * BYTES_PER_DIR_ENTRY / self.get_cluster_size()
        )
        clusters = self._get_cluster_chain(
            self._append_clusters_to_chain(
                last_cluster=clusters[-1],
                clusters_required=clusters_required
            )
        )
        for cluster_num in clusters:
            start, end = self._get_cluster_start_end_relative_to_data_start(
                cluster_num)
            for entry_start in range(data_start + start, data_start + end,
                                     BYTES_PER_DIR_ENTRY):
                entries_start.append(entry_start)
                if len(entries_start) == amount_required:
                    return entries_start
        raise ValueError("Unexpected error -"
                         " appended clusters were not enough!")

    def _append_clusters_to_chain(self, last_cluster, clusters_required):
        """
        Дополняет цепочку кластеров на clusters_required и возвращает первый
        из номеров добавленных кластеров.
        """
        if clusters_required <= 0:
            return last_cluster

        cluster_size = self.get_cluster_size()

        first_appended_cluster = self._write_content_and_get_first_cluster(
            bytes(cluster_size)
        )
        self._write_fat_value(last_cluster, first_appended_cluster)

        prev_cluster = first_appended_cluster
        for i in range(1, clusters_required):
            next_cluster = \
                self._write_content_and_get_first_cluster(bytes(cluster_size))
            self._write_fat_value(prev_cluster, next_cluster)
            prev_cluster = next_cluster

        self._write_eof_fat_value(prev_cluster)

        return first_appended_cluster

    def _update_first_free_cluster(self):
        fs_info_start = self._sectors_to_bytes(self._fs_info_sector)
        self._fat_image_file.seek(fs_info_start + 0x1e8)
        self._fat_image_file.write(
            int.to_bytes(self._first_free_cluster, length=4,
                         byteorder='little'))

    def _decrease_free_clusters_amount_by(self, amount):
        if self._free_clusters > 0:
            self._free_clusters -= amount
            self._update_free_clusters_amount()

    def _update_free_clusters_amount(self):
        fs_info_start = self._sectors_to_bytes(self._fs_info_sector)
        self._write_content_to_image(fs_info_start + 0x1e8,
                                     int.to_bytes(self._free_clusters,
                                                  length=4,
                                                  byteorder='little'))


class FATReaderError(Exception):
    def __init__(self, message='', *args):
        super().__init__(*args)
        self.message = message
