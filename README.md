# Update Media files timestamps

Often when we upload our photoes and media files somewhere and then download, the file modification timestamps are updated and thus the file managers cannot sort the files properly in chronological order.

This simple script is to help me to avoid this issue by:

- Read metadata (Exif data) from photos and videos.
- Get the media creation time from that.
- update the file modification time accordingly.

## Requirements:

```
sudo apt-get install -y exiftool
pip install -r requirements.txt
```

## Usage:

```
python run.py PATH_TO_DIRECTORY
```
