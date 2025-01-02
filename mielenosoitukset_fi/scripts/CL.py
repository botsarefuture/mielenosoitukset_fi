import os
import time
from datetime import datetime, timedelta
from mielenosoitukset_fi.utils.logger import logger


def remove_files_in_directory(directory):
    """
    Remove all files in the specified directory.

    Parameters
    ----------
    directory : str
        The path to the directory where files will be removed.
    """
    if not os.path.exists(directory):
        logger.error(f"Directory does not exist: {directory}")
        return

    if not os.path.isdir(directory):
        logger.error(f"Path is not a directory: {directory}")
        return

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
                logger.info(f"Removed file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove {file_path}. Reason: {e}")


def main():
    """
    Main function to remove files in the 'mielenosoitukset_fi/uploads' directory every 24 hours.
    """
    directory = "mielenosoitukset_fi/uploads"
    remove_files_in_directory(directory)


if __name__ == "__main__":
    main()
