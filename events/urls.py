from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list_view, name='event_list'),
    path('new/', views.event_create_view, name='event_create'),
    path('<int:event_id>/', views.event_detail_view, name='event_detail'),
    path('<int:event_id>/edit/', views.event_edit_view, name='event_edit'),
    path('<int:event_id>/associate-students/', views.event_associate_students_view, name='associate_students'),
    path('<int:event_id>/toggle-pause/', views.event_toggle_pause_view, name='toggle_pause'),
]
