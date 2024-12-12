import os
import time
from datetime import datetime, timedelta


def remove_files_in_directory(directory):
    """
    Remove all files in the specified directory.

    Parameters
    ----------
    directory : str
        The path to the directory where files will be removed.
    """
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                print(f"Removed file: {file_path}")
        except Exception as e:
            print(f"Failed to remove {file_path}. Reason: {e}")


def main():
    """
    Main function to remove files in the 'mielenosoitukset_fi/uploads' directory every 24 hours.
    """
    directory = "mielenosoitukset_fi/uploads"
    remove_files_in_directory(directory)


if __name__ == "__main__":
    main()
