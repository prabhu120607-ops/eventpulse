from django.contrib import admin
from django.urls import path, include
from . import views

# Public URL patterns
public_patterns = ([
    path('', views.home_view, name='home'),
    path('events/', views.public_events_view, name='events_list'),
    path('events/<int:event_id>/register/', views.public_register_event_view, name='register_event'),
    path('features/', views.features_view, name='features'),
    path('how-it-works/', views.how_it_works_view, name='how_it_works'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
], 'public')

urlpatterns = [
    # Django Admin site
    path('django-admin/', admin.site.urls),

    # Public pages
    path('', include(public_patterns, namespace='public')),

    # Accounts & Admin Portal
    path('portal/', include('accounts.urls', namespace='accounts')),

    # Students Management
    path('portal/students/', include('students.urls', namespace='students')),

    # Events Management
    path('portal/events/', include('events.urls', namespace='events')),

    # Feedback Engine & Public Submission Endpoints
    path('feedback/', include('feedback.urls', namespace='feedback')),

    # Analytics & Reports
    path('portal/analytics/', include('analytics.urls', namespace='analytics')),
]
