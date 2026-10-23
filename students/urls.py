from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list_view, name='student_list'),
    path('import-csv/', views.student_import_csv_view, name='import_csv'),
    path('sample-csv/', views.download_sample_csv_view, name='download_sample_csv'),
]
