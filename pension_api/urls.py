from django.urls import path, re_path
from .views import (
    RegisterUserView, 
    VerifyUserView, 
    VerifyLivenessVideoView, 
    UserListView, 
    UserDetailView, 
    DashboardDataView
)

urlpatterns = [
    re_path(r'^register/?$', RegisterUserView.as_view(), name='register'),
    re_path(r'^verify/?$', VerifyUserView.as_view(), name='verify'),
    re_path(r'^verify_liveness_video/?$', VerifyLivenessVideoView.as_view(), name='verify_liveness_video'),
    re_path(r'^api-admin/users/?$', UserListView.as_view(), name='user-list'),
    re_path(r'^api-admin/users/(?P<pension_id>[^/]+)/?$', UserDetailView.as_view(), name='user-detail'),
    re_path(r'^api-admin/dashboard/?$', DashboardDataView.as_view(), name='dashboard-data'),
]
