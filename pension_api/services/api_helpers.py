import tempfile

from rest_framework import status
from rest_framework.response import Response

from pension_api.services.utils import generate_meet_link


_ACTIONS_MAP = {
    "smile": "smile",
    "move_head_left": "turn_left",
    "move_head_right": "turn_right",
}
_VALID_DIRECT_ACTIONS = {"turn_left", "turn_right", "smile"}


def parse_verification_actions(verification_type: str) -> list[str]:
    required_actions: list[str] = []
    for rt in [t.strip() for t in (verification_type or "").split(",")]:
        if rt in _ACTIONS_MAP:
            required_actions.append(_ACTIONS_MAP[rt])
        elif rt in _VALID_DIRECT_ACTIONS:
            required_actions.append(rt)
    return required_actions or ["smile"]


def failure_response(message: str) -> Response:
    return Response(
        {"status": "failure", "message": message, "meet_link": generate_meet_link()},
        status=status.HTTP_200_OK,
    )


def save_temp_video(uploaded_file) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        return tmp.name

