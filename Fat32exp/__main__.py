# !/usr/bin/env python3
import argparse
import platform
from pathlib import Path

import fateditor
from dirbrowser import DirectoryBrowser


def main():
    parsed_args = parse_args()

    image_file_name = parsed_args.image_path
    image_file_path = Path(image_file_name)

    if not image_file_path.exists():
        print('File "' + image_file_name + '" not found.')
        return

    try:
        with open(image_file_name, "r+b") as fi:
            f = fateditor.Fat32Editor(fi)
            if f.valid:
                print("Image successfully parsed.")
                DirectoryBrowser(fat_editor=f).start_interactive_mode()
    except fateditor.FATReaderError as e:
        print("Error: " + e.message)
        return
    except PermissionError:
        error_message = "Error: permission denied."
        system = platform.system()
        if system == 'Linux':
            error_message += " You might want to run this command " \
                             "as superuser."
        elif system == 'Windows':
            error_message += " You might want to run this command " \
                             "as administrator."
        print(error_message)
    except OSError as e:
        print("OSError: " + str(e))
        if not image_file_path.exists():
            print('File "' + image_file_name + '" not found.')


def parse_args():
    parser = argparse.ArgumentParser(description="Open FAT32 image")

    parser.add_argument("image_path", type=str,
                        help="Path to the FAT32 image")
    return parser.parse_args()


if __name__ == '__main__':
    main()
