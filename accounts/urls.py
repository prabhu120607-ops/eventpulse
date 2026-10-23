from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('users/', views.users_list_view, name='users_list'),
    path('users/new/', views.user_create_view, name='user_create'),
    path('audit-logs/', views.audit_logs_view, name='audit_logs'),
    path('notifications/', views.notifications_list_view, name='notifications_list'),
]
