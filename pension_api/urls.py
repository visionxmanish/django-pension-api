from django.urls import path
from .views import (
    RegisterUserView, 
    VerifyUserView, 
    VerifyLivenessVideoView, 
    UserListView,
    LatestUsersView,
    UserDetailView, 
    DashboardDataView,
    RegisterNomineeView,
    VerifyNomineeLivenessView,
    MarkUserDeceasedView,
    EditNomineeView,
    DeleteNomineeView,
    AdminNomineeListCreateView,
    AdminNomineeDetailView,
    AdminUserNomineeListView,
    ParentNomineeListView,
    AdminNomineeDetailByParentAndIdView,
    AdminVerificationListView,
    AdminNomineeVerificationListView,
    HealthView,
    MetaView,
)

urlpatterns = [
    # User Registration & Verification
    path('register/', RegisterUserView.as_view(), name='register'),
    path('verify/', VerifyUserView.as_view(), name='verify'),
    path('verify-liveness-video/', VerifyLivenessVideoView.as_view(), name='verify_liveness_video'),

    # Nominee Management
    path('nominee/register/', RegisterNomineeView.as_view(), name='register_nominee'),
    path('nominee/edit/', EditNomineeView.as_view(), name='edit_nominee'),
    path('nominee/delete/', DeleteNomineeView.as_view(), name='delete_nominee'),
    path('nominee/verify-liveness/', VerifyNomineeLivenessView.as_view(), name='verify_nominee_liveness'),
    path('nominee/parent/<str:pension_id>/', ParentNomineeListView.as_view(), name='nominee_list_by_parent'),

    # User Status
    path('mark-deceased/', MarkUserDeceasedView.as_view(), name='mark_deceased'),

    # Admin APIs
    path('api-admin/users/', UserListView.as_view(), name='user_list'),
    path('api-admin/users/latest/', LatestUsersView.as_view(), name='latest_users'),
    path('api-admin/users/<str:pension_id>/', UserDetailView.as_view(), name='user_detail'),
    path('api-admin/users/<str:pension_id>/nominees/', AdminUserNomineeListView.as_view(), name='admin_user_nominees'),
    path('api-admin/parents/<str:pension_id>/nominees/', ParentNomineeListView.as_view(), name='admin_parent_nominee_list'),
    path('api-admin/nominees/', AdminNomineeListCreateView.as_view(), name='admin_nominee_list_create'),
    path('api-admin/nominees/<str:pension_id>/<str:nominee_id>/', AdminNomineeDetailByParentAndIdView.as_view(), name='admin_nominee_detail_by_parent_id'),
    path('api-admin/nominees/<str:nominee_pension_id>/', AdminNomineeDetailView.as_view(), name='admin_nominee_detail'),
    path('api-admin/verifications/', AdminVerificationListView.as_view(), name='admin_verifications'),
    path('api-admin/nominee-verifications/', AdminNomineeVerificationListView.as_view(), name='admin_nominee_verifications'),
    path('api-admin/health/', HealthView.as_view(), name='admin_health'),
    path('api-admin/meta/', MetaView.as_view(), name='admin_meta'),
    path('api-admin/dashboard/', DashboardDataView.as_view(), name='dashboard_data'),
]