
from datetime import datetime
import os
import sys
import subprocess
import logging

from tqdm import tqdm
from PIL import Image
from pillow_heif import register_heif_opener

# Ref: https://stackoverflow.com/questions/38537905/set-logging-levels
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Change logging level to DEBUG for more info.


# for iPhone's .HEIC image files.
register_heif_opener()

# PWD
SOURCE_DIRECTORY = ""

EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

IMAGE_EXTENSIONS = [
    "jpg",
    "heic",
]
VIDEO_EXTENSIONS = [
    "mp4",
    "mov"
]


def main(source_directory):
    source_directory = os.path.abspath(source_directory)

    logger.info(f"Reading directory: {source_directory}")

    for root, subdirs, files in os.walk(source_directory):
        logger.info(f"Reading files in directory: {root}")
        update_files_stamps(root, files)


def update_files_stamps(root_dir, files):
    for file in tqdm(files, desc=f"Files in the directory {root_dir}"):
        file = os.path.join(root_dir, file)
        logger.debug(f"Checking file {file}...")
        if is_image(file):
            logger.debug(f"File {file} is an image.")
            update_timestamp(file, read_image_creation_date(file))
        elif is_video(file):
            logger.debug(f"File {file} is a video.")
            update_timestamp(file, read_video_creation_date(file))
        else:
            logger.error(f"Unidentified media file: {file}")


def is_image(file):
    return get_extension(file) in IMAGE_EXTENSIONS


def is_video(file):
    return get_extension(file) in VIDEO_EXTENSIONS


def get_extension(file: str):
    try:
        return file.lower().split(".")[1:][-1]
    except IndexError:
        logger.error(f"Error: no extension found: {file}")
        return None


def read_image_creation_date(image_file_path):
    image = Image.open(image_file_path)
    image.verify()

    if image_file_path.lower().endswith("heic"):    # iPhone image
        logger.debug(f"Found HEIC image: {image_file_path}")
        datetime_str = image.getexif().get(306)
    else:
        logger.debug(f"Found non-HEIC image: {image_file_path}")
        datetime_str = image._getexif()[36867]

    logger.debug(f"Got creation date: {datetime_str} for file {image_file_path}")
    return datetime.strptime(datetime_str, EXIF_DATE_FORMAT)


def read_video_creation_date(video_path):
    """
    Ref: https://stackoverflow.com/questions/60576891/how-to-read-exif-data-of-movies-in-python
    """
    EXIFTOOL_DATE_TAG_VIDEOS = "Creation Date"

    absolute_path = os.path.join(os.getcwd(), video_path )
    process = subprocess.Popen(["exiftool", absolute_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    lines = out.decode("utf-8").split("\n")

    for line in lines:
        if EXIFTOOL_DATE_TAG_VIDEOS in str(line):
            datetime_str = str(line.split(" : ")[1].strip())
            logger.debug(f"Got creation date: {datetime_str} for video file {video_path}")
            # TODO: for now, we are only interested in date so removing the timezone
            # information from the timestamp. But we need to be able to parse this
            # timezone info as well.
            datetime_str_wo_tz = datetime_str.split("+")[0]
            logger.debug(f"Date after stripping the timezone info: {datetime_str_wo_tz}")
            return datetime.strptime(datetime_str_wo_tz, EXIF_DATE_FORMAT)


def update_timestamp(file, timestamp):
    stats = os.stat(file)

    new_access_time = stats.st_atime
    new_modified_time = str(timestamp)
    new_modified_time_epoch = timestamp.timestamp()
    logger.debug(f"Setting access time for file: {file}, to {new_access_time}")
    logger.debug(f"Setting modified time for file: {file}, to {new_modified_time}")
    os.utime(file, (new_modified_time_epoch, new_modified_time_epoch))


if __name__ == "__main__":
    source_directory = sys.argv[1] if len(sys.argv) > 1 else SOURCE_DIRECTORY
    main(source_directory)
