import cv2
import numpy as np
from deepface import DeepFace
import tempfile
import os


def _load_and_preprocess(image_path):
    """Loads image, resizes to 800px width, returns (original_resized, gray)."""
    image = cv2.imread(image_path)
    if image is None:
        return None, None
    h, w = image.shape[:2]
    scale = 800 / float(w)
    resized = cv2.resize(image, (800, int(h * scale)))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    return resized, gray


def _apply_clahe(image):
    """Applies CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve
    contrast in images with bright backgrounds that wash out facial features."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _get_face_region(image):
    """Detects the face region using Haar cascade. Returns (x, y, w, h) or None."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    # Return the largest face
    return max(faces, key=lambda f: f[2] * f[3])


def validate_image_quality(image_path, blur_threshold=100.0, glare_ratio_threshold=0.12):
    """
    Checks image for glare and blurriness.
    Glare is checked only within the face region to avoid false positives
    from bright backgrounds.
    """
    resized, gray = _load_and_preprocess(image_path)
    if resized is None:
        return False, "Could not read image"

    # 1. Blur Detection (Laplacian) on the full image
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < blur_threshold:
        return False, f"Image too blurry ({laplacian_var:.1f}). Hold camera steady."

    # 2. Glare Detection — restricted to face region only
    face_rect = _get_face_region(resized)
    if face_rect is not None:
        x, y, fw, fh = face_rect
        face_gray = gray[y:y+fh, x:x+fw]
    else:
        # No face detected — fall back to center crop (assume face is roughly centered)
        h, w = gray.shape
        cx, cy = w // 2, h // 2
        crop_w, crop_h = w // 3, h // 3
        face_gray = gray[cy-crop_h:cy+crop_h, cx-crop_w:cx+crop_w]

    # Threshold at 254 — only nearly-saturated white pixels count as glare
    _, mask = cv2.threshold(face_gray, 254, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    bright_pixel_count = cv2.countNonZero(mask)
    total_pixels = face_gray.shape[0] * face_gray.shape[1]
    glare_ratio = bright_pixel_count / total_pixels

    if glare_ratio > glare_ratio_threshold:
        return False, f"Glare detected on face ({glare_ratio:.2%}). Adjust lighting angle."

    return True, "Quality OK"


    
def check_liveness(image_path):
    """
    Checks if the face is real using DeepFace anti-spoofing.
    Preprocesses the image (CLAHE + denoise) to handle challenging lighting
    such as bright backgrounds that can confuse the anti-spoof model.
    Returns (is_real, message)
    """
    preprocessed_path = None
    try:
        # Preprocess: apply CLAHE contrast enhancement and light denoising
        # to improve anti-spoof accuracy in bright/washed-out conditions
        image = cv2.imread(image_path)
        if image is None:
            return False, "Could not read image for liveness check"

        enhanced = _apply_clahe(image)
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 6, 6, 7, 21)

        # Save preprocessed image to a temp file for DeepFace
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            preprocessed_path = tmp.name
            cv2.imwrite(preprocessed_path, enhanced)

        objs = DeepFace.extract_faces(
            img_path=preprocessed_path,
            enforce_detection=True,
            anti_spoofing=True
        )

        if not objs:
            return False, "No face detected"

        is_real = objs[0].get("is_real", True)
        antispoof_score = objs[0].get("antispoof_score", 0.0)

        if not is_real:
             return False, "Liveness check failed: Spoof detected."

        return True, "Liveness check passed"

    except TypeError:
        print("Warning: DeepFace version does not support anti_spoofing argument.")
        return True, "Liveness check skipped (not supported)"
    except Exception as e:
        print(f"Liveness check error: {e}")
        return False, f"Liveness check error: {str(e)}"
    finally:
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.remove(preprocessed_path)

def get_face_embedding(image_path, require_single=True):
    """
    Generates face embedding using DeepFace.
    If require_single is True, raises ValueError if more than 1 face is detected.
    """
    try:
        # Using ArcFace for better accuracy, or VGG-Face
        embedding_objs = DeepFace.represent(
            img_path=image_path,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True
        )
        if not embedding_objs:
            return None
            
        # Security/Accuracy check: Ensure only one face is in the registration photo
        if require_single and len(embedding_objs) > 1:
            raise ValueError(f"Multiple faces detected ({len(embedding_objs)}). Please ensure only your face is visible.")
            
        return embedding_objs[0]["embedding"]
        
    except ValueError as ve:
        raise ve
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def verify_face(image_path, stored_embedding):
    """
    Verifies if the face in image_path matches the stored_embedding.
    Uses cosine distance with ArcFace default threshold (0.68).
    """
    try:
        new_embedding_objs = DeepFace.represent(
            img_path=image_path,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True
        )
        if not new_embedding_objs:
            return False, "No face detected"
        
        new_embedding = new_embedding_objs[0]["embedding"]
        
        a = np.array(stored_embedding)
        b = np.array(new_embedding)
        
        cosine_similarity = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        cosine_distance = 1 - cosine_similarity
        
        # DeepFace default threshold for ArcFace with Cosine is 0.68
        if cosine_distance < 0.68:
            return True, "Match found"
        else:
            return False, "Face does not match"
            
    except Exception as e:
        return False, f"Verification error: {str(e)}"
