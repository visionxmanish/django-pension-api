import time
import uuid
from PIL import Image, ExifTags
import pillow_heif
import tempfile
import os

pillow_heif.register_heif_opener()

def generate_meet_link():
    """Generates a unique Jitsi Meet link."""
    # Using a unique identifier to ensure the room is private/unique
    unique_id = uuid.uuid4().hex[:10]
    timestamp = int(time.time())
    return f"https://meet.jit.si/PensionVerification_{unique_id}_{timestamp}"

def process_uploaded_image(file_obj) -> str:
    """ Processes upload, standardizes format/orientation, compresses large files, returns temp path """
    img = Image.open(file_obj)
    
    try:
        # Handle EXIF orientation (crucial for mobile photos)
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = img._getexif()
        if exif is not None:
            exif_orientation = exif.get(orientation, 1)
            if exif_orientation == 3:
                img = img.rotate(180, expand=True)
            elif exif_orientation == 6:
                img = img.rotate(270, expand=True)
            elif exif_orientation == 8:
                img = img.rotate(90, expand=True)
    except Exception:
        pass

    # Convert alpha channels/HEIC to standard RGB
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    # Resize securely to prevent OOM errors on massive phone camera pics
    img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    img.save(tmp.name, format="JPEG", quality=90)
    tmp.close()
    return tmp.name
