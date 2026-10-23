from django.urls import path
from . import views

app_name = 'feedback'

urlpatterns = [
    path('forms/', views.form_list_view, name='form_list'),
    path('forms/<int:form_id>/builder/', views.form_builder_view, name='form_builder'),
    path('forms/<int:form_id>/delete-question/<int:question_id>/', views.form_delete_question_view, name='form_delete_question'),
    path('forms/<int:form_id>/preview/', views.form_preview_view, name='form_preview'),

    # Public submission endpoints via single-use secure token
    path('submit/<str:token>/', views.submit_feedback_view, name='submit_feedback'),
    path('success/', views.submission_success_view, name='submission_success'),

    # Admin feedback views
    path('events/<int:event_id>/responses/', views.event_responses_view, name='event_responses'),
    path('events/<int:event_id>/dispatch-invitations/', views.trigger_event_invitations_view, name='trigger_event_invitations'),
    path('events/<int:event_id>/send-reminders/', views.send_reminders_view, name='send_reminders'),

    # Invitations & telemetry
    path('invitations/', views.invitations_list_view, name='invitations_list'),
    path('process-automations/', views.process_automations_view, name='process_automations'),
    path('test-email/', views.test_email_view, name='test_email'),
]
