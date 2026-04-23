"""
Serializer package split out of the original monolithic `serializers.py`.

`pension_api.serializers` (module) remains as a backward-compatible shim that
re-exports the public serializer classes.
"""

from .inputs import (  # noqa: F401
    RegisterInputSerializer,
    VerifyInputSerializer,
    VerifyLivenessVideoInputSerializer,
    RegisterNomineeInputSerializer,
    VerifyNomineeLivenessVideoInputSerializer,
    MarkDeceasedInputSerializer,
    EditNomineeInputSerializer,
    DeleteNomineeInputSerializer,
)
from .outputs import (  # noqa: F401
    FaceEncodingSerializer,
    NomineeFaceEncodingSerializer,
    NomineeSerializer,
    UserSerializer,
    VerificationSerializer,
    UserResponseSerializer,
    NomineeResponseSerializer,
    VerificationResponseSerializer,
    ParentUserSummarySerializer,
    ParentNomineeListResponseSerializer,
    HealthResponseSerializer,
    MetaResponseSerializer,
    DashboardResponseSerializer,
)
from .admin import (  # noqa: F401
    UserAdminUpdateSerializer,
    UserAdminCreateSerializer,
    AdminNomineeCreateUpdateSerializer,
)

