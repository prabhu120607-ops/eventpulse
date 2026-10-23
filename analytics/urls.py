from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.analytics_dashboard_view, name='dashboard'),
    path('reports/', views.reports_home_view, name='reports_home'),
    path('reports/event/<int:event_id>/csv/', views.export_event_report_csv, name='event_report_csv'),
    path('reports/university-audit/csv/', views.export_university_report_csv, name='university_report_csv'),
]
