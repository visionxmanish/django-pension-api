import cv2
import numpy as np
import math
import os
import tempfile


class LivenessDetector:
    def __init__(self):
        self.facemark = cv2.face.createFacemarkLBF()
        model_path = "lbfmodel.yaml"
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file {model_path} not found. Please download it.")
        self.facemark.loadModel(model_path)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        )

    def get_landmarks(self, image):
        """
        Processes the image and returns face landmarks (68 points).
        Returns None if no face or landmarks found.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            success, landmarks = self.facemark.fit(image, faces)
            if success:
                return landmarks[0][0]  # Return first face's landmarks
        return None

    def calculate_pose(self, landmarks, image_shape):
        """
        Calculates head pose (pitch, yaw, roll) from face landmarks.
        Returns (pitch, yaw, roll) in degrees.
        """
        img_h, img_w, img_c = image_shape

        image_points = np.array([
            landmarks[30],  # Nose tip
            landmarks[8],   # Chin
            landmarks[36],  # Left eye left corner
            landmarks[45],  # Right eye right corner
            landmarks[48],  # Left mouth corner
            landmarks[54]   # Right mouth corner
        ], dtype="double")

        model_points = np.array([
            (0.0, 0.0, 0.0),          # Nose tip
            (0.0, -330.0, -65.0),     # Chin
            (-225.0, 170.0, -135.0),  # Left eye left corner
            (225.0, 170.0, -135.0),   # Right eye right corner
            (-150.0, -150.0, -125.0), # Left mouth corner
            (150.0, -150.0, -125.0)   # Right mouth corner
        ])

        focal_length = img_w
        center = (img_w / 2, img_h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype="double")

        dist_coeffs = np.zeros((4, 1))

        (success, rotation_vector, translation_vector) = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        rmat, jac = cv2.Rodrigues(rotation_vector)
        ret = cv2.RQDecomp3x3(rmat)
        angles = ret[0]

        return angles[0], angles[1], angles[2]  # pitch, yaw, roll

    def detect_expression(self, landmarks):
        left_corner  = landmarks[48]
        right_corner = landmarks[54]
        top_lip      = landmarks[51]
        bottom_lip   = landmarks[57]
        left_eye_out = landmarks[36]
        right_eye_out= landmarks[45]

        mouth_width  = np.linalg.norm(right_corner - left_corner)
        eye_dist     = np.linalg.norm(right_eye_out - left_eye_out)
        width_ratio  = mouth_width / (eye_dist + 1e-6)

        mouth_height = np.linalg.norm(bottom_lip - top_lip)
        height_ratio = mouth_height / (mouth_width + 1e-6)

        w_pass = width_ratio  > 0.72
        h_pass = height_ratio < 0.45

        print(
            f"  [smile] width={width_ratio:.3f}({'OK' if w_pass else 'FAIL'}) | "
            f"height={height_ratio:.3f}({'OK' if h_pass else 'FAIL'})"
        )

        return {
            "smile":       w_pass and h_pass,
            "width_ratio": width_ratio,
            "height_ratio": height_ratio,
        }


def verify_video_liveness(video_path, required_actions=["turn_left", "turn_right", "smile"]):
    """
    Processes a video to verify if the user performs the required actions.

    Smile detection requires the expression to be held for SMILE_FRAMES_REQUIRED
    consecutive sampled frames to avoid single-frame false positives.

    Returns (success, message, best_frame_path)
    """
    SMILE_FRAMES_REQUIRED = 3  # consecutive sampled frames (~15 real frames at every-3rd sampling)
    YAW_THRESHOLD = 15          # degrees

    cap = cv2.VideoCapture(video_path)
    try:
        detector = LivenessDetector()
    except FileNotFoundError as e:
        return False, str(e), None

    action_status     = {action: False for action in required_actions}
    best_frame        = None
    max_face_quality  = -float("inf")
    smile_frame_count = 0
    frame_count       = 0

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            frame_count += 1
            if frame_count % 3 != 0:
                continue

            landmarks = detector.get_landmarks(frame)

            if landmarks is not None:
                pitch, yaw, roll = detector.calculate_pose(landmarks, frame.shape)
                expressions      = detector.detect_expression(landmarks)

                # Debug — remove or comment out in production
                print(
                    f"Frame {frame_count} | yaw={yaw:.1f} | smile={expressions['smile']} | "
                    f"width={expressions['width_ratio']:.3f} | "
                    f"height={expressions['height_ratio']:.3f} | "
                )

                # --- Head turn left ---
                if "turn_left" in required_actions and not action_status["turn_left"]:
                    if yaw < -YAW_THRESHOLD:
                        action_status["turn_left"] = True
                        print("Detected Turn Left")

                # --- Head turn right ---
                if "turn_right" in required_actions and not action_status["turn_right"]:
                    if yaw > YAW_THRESHOLD:
                        action_status["turn_right"] = True
                        print("Detected Turn Right")

                # --- Smile (must hold for consecutive frames) ---
                if "smile" in required_actions and not action_status["smile"]:
                    if expressions["smile"]:
                        smile_frame_count += 1
                        if smile_frame_count >= SMILE_FRAMES_REQUIRED:
                            action_status["smile"] = True
                            print("Detected Smile")
                    else:
                        smile_frame_count = 0  # reset on any non-smile frame

                # --- Track best frontal frame for face verification ---
                score = 100 - (abs(yaw) + abs(pitch))
                if score > max_face_quality:
                    max_face_quality = score
                    best_frame = frame.copy()

        cap.release()

        missing_actions = [action for action, done in action_status.items() if not done]

        if not missing_actions:
            if best_frame is not None and best_frame.size > 0:
                print(f"Saving best frame. Shape: {best_frame.shape}")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    cv2.imwrite(tmp.name, best_frame)
                    return True, "Liveness verified", tmp.name
            else:
                return False, "Liveness verified but could not extract a valid face frame.", None
        else:
            return False, f"Liveness check failed. Missing actions: {', '.join(missing_actions)}", None

    except Exception as e:
        print(f"Error in video processing: {e}")
        return False, f"Error processing video: {str(e)}", None

    finally:
        cap.release()