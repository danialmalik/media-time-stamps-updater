import pytz
from datetime import datetime
from dateutil import parser
import os
import sys
import subprocess
import logging

from exif import Image as ExifImage
from tqdm import tqdm
from PIL import Image
from pillow_heif import register_heif_opener

# Ref: https://stackoverflow.com/questions/38537905/set-logging-levels
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)  # Change logging level to DEBUG for more info.

LOCAL_TIMEZONE = "Asia/Karachi"
DEFAULT_TZ_OFFSET = "+0500"

# for iPhone's .HEIC image files.
register_heif_opener()

# PWD
SOURCE_DIRECTORY = ""

EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
EXIF_DATE_FORMAT_TZ = "%Y:%m:%d %H:%M:%S %z"

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
            process_image_file(file)
        elif is_video(file):
            logger.debug(f"File {file} is a video.")
            process_video_file(file)
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


def process_image_file(image_file_path):
    if image_file_path.lower().endswith("heic"):    # iPhone image
        logger.debug(f"Found HEIC image: {image_file_path}")
        process_heic_image_file(image_file_path)
    else:
        logger.debug(f"Found non-HEIC image: {image_file_path}")
        process_non_heic_image_file(image_file_path)


def process_heic_image_file(image_file_path):
    # TODO: Add timezone support?
    image = Image.open(image_file_path)
    image.verify()

    datetime_str = image.getexif().get(306)
    datetime_stamp = datetime.strptime(datetime_str, EXIF_DATE_FORMAT)

    update_timestamp(image_file_path, datetime_stamp)


def process_non_heic_image_file(image_file_path):
    exif_image = ExifImage(open(image_file_path, "rb"))

    if exif_image.has_exif:
        offset = exif_image.get("offset_time", DEFAULT_TZ_OFFSET).replace(":", "")
        datetime_str = f"{exif_image.datetime} {offset}"
        datetime_stamp = datetime.strptime(datetime_str, EXIF_DATE_FORMAT_TZ)
        datetime_stamp = datetime_stamp.astimezone(pytz.timezone(LOCAL_TIMEZONE))
        update_timestamp(image_file_path, datetime_stamp)
        return

    # No exif data, trying other approach.
    image = Image.open(image_file_path)
    image.verify()

    try:
        datetime_str = image._getexif()[36867]
        datetime_stamp = datetime.strptime(datetime_str, EXIF_DATE_FORMAT)
        update_timestamp(image_file_path, datetime_stamp)
        return
    except (KeyError, IndexError, TypeError):
        pass

    # Second approach failed, so final attempt. Call the subprocess.
    datetime_stamp = _run_exiftool_process(image_file_path, "createdate", is_timestamp=True)
    update_timestamp(image_file_path, datetime_stamp)


def process_video_file(file):
    timestamp = read_video_creation_date(file)
    update_video_file_metadata(file, timestamp)
    update_timestamp(file, timestamp)


def read_video_creation_date(video_path):
    """
    Ref: https://stackoverflow.com/questions/60576891/how-to-read-exif-data-of-movies-in-python
    """
    return _run_exiftool_process(video_path, "creationdate", is_timestamp=True)


def _run_exiftool_process(file_path, required_key, is_timestamp=False):
    absolute_path = os.path.join(os.getcwd(), file_path)
    process = subprocess.Popen(
        ["exiftool", f"-{required_key}", absolute_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    out, err = process.communicate()

    lines = out.decode("utf-8").split("\n")

    if len(lines) < 1 or err:
        logger.error("Error while running exif tool for {file_path} with getter {required_key}")
        logger.error(err)
        return None

    required_output = str(lines[0].split(" : ")[1].strip())
    logger.debug(f"Got {required_key}: {required_output} for video file {video_path}")

    if is_timestamp:
        datetime_str = required_output
        timezone = "0500"

        # TODO: fix for -ve timezones
        if "+" in datetime_str:
            datetime_str_wo_tz, timezone = datetime_str.split("+")
            timezone = timezone.replace(":", "")
        else:
            datetime_str_wo_tz = datetime_str

        full_datetime_str = f'{datetime_str_wo_tz} +{timezone}'
        logger.debug(f"Date after formatting the timezone info: {full_datetime_str}")
        return datetime.strptime(full_datetime_str, EXIF_DATE_FORMAT_TZ)

    else:
        return required_output


def update_timestamp(file, timestamp):
    stats = os.stat(file)

    new_access_time = stats.st_atime
    new_modified_time = str(timestamp)
    new_modified_time_epoch = timestamp.timestamp()
    logger.debug(f"Setting access time for file: {file}, to {new_access_time}")
    logger.debug(f"Setting modified time for file: {file}, to {new_modified_time}")
    os.utime(file, (new_modified_time_epoch, new_modified_time_epoch))


def update_video_file_metadata(file, timestamp):
    EXIF_TAGS_TO_UPDATE = [
        "modifydate",
        "trackcreatedate",
        "trackmodifydate",
        "mediacreatedate",
        "mediamodifydate",
        "createdate",
    ]

    DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"
    new_datetime_stamp = timestamp.strftime(DATETIME_FORMAT)

    absolute_path = os.path.join(os.getcwd(), file)
    process = subprocess.Popen(
        [
            "exiftool",
            *[
                f"-{tag}='{new_datetime_stamp}'" for tag in EXIF_TAGS_TO_UPDATE
            ],
            absolute_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    output = out.decode("utf-8")

    logger.info(f"Updated metdata for file: {file}")
    logger.debug(output)

    process = subprocess.Popen(
        [
            "exiftool",
            "-delete_original!",
            absolute_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    output = out.decode("utf-8")

    logger.info("Deleted backed-up original file.")
    logger.debug(output)


if __name__ == "__main__":
    source_directory = sys.argv[1] if len(sys.argv) > 1 else SOURCE_DIRECTORY
    main(source_directory)
