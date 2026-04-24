"""
View package split out of the original monolithic `views.py`.

`pension_api.views` (module) remains as a backward-compatible shim that
re-exports the public API view classes referenced by urls.py.
"""

from .admin_users import UserListView, UserDetailView  # noqa: F401
from .dashboard import DashboardDataView, LatestUsersView  # noqa: F401
from .health import HealthView, MetaView  # noqa: F401
from .nominees import (  # noqa: F401
    RegisterNomineeView,
    EditNomineeView,
    DeleteNomineeView,
    VerifyNomineeLivenessView,
)
from .admin_nominees import (  # noqa: F401
    AdminNomineeListCreateView,
    AdminNomineeDetailView,
    AdminUserNomineeListView,
    ParentNomineeListView,
    AdminNomineeDetailByParentAndIdView,
)
from .verifications import (  # noqa: F401
    AdminVerificationListView,
    AdminNomineeVerificationListView,
)
from .registration import (  # noqa: F401
    RegisterUserView,
    VerifyUserView,
    VerifyLivenessVideoView,
    MarkUserDeceasedView,
)

