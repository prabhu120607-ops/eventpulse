"""
Feedback Services: Token generation, invitation dispatch, email delivery, and reminder engine.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
import hashlib

from .models import (
    FeedbackInvitation, InvitationStatus, EmailDeliveryAttempt,
    FeedbackResponse, FeedbackForm
)
from events.models import Event, EventStatus, EventRegistration


def generate_invitations_for_event(event):
    """
    Creates unique secure feedback invitation tokens for all eligible registered students of an event.
    Safe to run repeatedly; uses get_or_create to prevent duplicates.
    """
    if not hasattr(event, 'feedback_form'):
        return 0

    feedback_form = event.feedback_form
    eligible_registrations = event.registrations.filter(attended=True).select_related('student')

    created_count = 0
    for reg in eligible_registrations:
        invitation, created = FeedbackInvitation.objects.get_or_create(
            event=event,
            student=reg.student,
            defaults={
                'feedback_form': feedback_form,
                'status': InvitationStatus.PENDING,
            }
        )
        if created:
            created_count += 1

    return created_count


def dispatch_invitation_email(invitation, request=None, domain="127.0.0.1:8000"):
    """
    Sends an invitation email containing the unique secure feedback link.
    Records EmailDeliveryAttempt for auditability.
    """
    student = invitation.student
    event = invitation.event

    # Build unique feedback submission URL
    feedback_path = reverse('feedback:submit_feedback', kwargs={'token': invitation.token})
    protocol = "https" if (request and request.is_secure()) else "http"
    if request:
        host = request.get_host()
    else:
        host = domain

    feedback_url = f"{protocol}://{host}{feedback_path}"

    privacy_note = (
        "Your feedback is completely ANONYMOUS. Your identity will never be associated with your responses."
        if event.feedback_mode == 'ANONYMOUS'
        else "Your feedback is IDENTIFIED to allow faculty coordinators to follow up on specific academic questions."
    )

    subject = f"Feedback Invitation: {event.title}"
    message_body = f"""Dear {student.full_name},

Thank you for participating in {event.title} at {event.venue}.

We value your student experience and invite you to share your feedback to help us enhance future campus events.

Please complete your evaluation using your secure personal link:
{feedback_url}

Important Information:
• {privacy_note}
• This link is single-use and will automatically expire on {event.feedback_deadline.strftime('%b %d, %Y at %I:%M %p') if event.feedback_deadline else '7 days from now'}.
• No login or password is required.

Thank you for contributing to campus excellence!

EventPulse University Operations Platform
{settings.DEFAULT_FROM_EMAIL}
"""

    attempt_type = 'REMINDER' if invitation.reminder_count > 0 else 'INVITATION'

    try:
        send_mail(
            subject=subject,
            message=message_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.university_email],
            fail_silently=False
        )

        # Update invitation status
        now = timezone.now()
        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.SENT
            invitation.sent_at = now
        else:
            invitation.reminder_count += 1
            invitation.last_reminder_at = now
        invitation.save()

        # Log delivery attempt
        EmailDeliveryAttempt.objects.create(
            invitation=invitation,
            recipient_email=student.university_email,
            subject=subject,
            attempt_type=attempt_type,
            status='SUCCESS'
        )
        return True, "Delivered"

    except Exception as e:
        invitation.status = InvitationStatus.FAILED
        invitation.delivery_error = str(e)
        invitation.save()

        EmailDeliveryAttempt.objects.create(
            invitation=invitation,
            recipient_email=student.university_email,
            subject=subject,
            attempt_type=attempt_type,
            status='FAILED',
            error_message=str(e)
        )
        return False, str(e)


def process_pending_event_automations(domain="127.0.0.1:8000"):
    """
    Automated job: Checks completed events, generates invitations, dispatches pending emails,
    and sends reminders for pending responses.
    """
    now = timezone.now()
    summary = {
        'events_checked': 0,
        'invitations_created': 0,
        'emails_sent': 0,
        'reminders_sent': 0,
        'errors': 0,
    }

    # Find events that are finished and not paused
    eligible_events = Event.objects.filter(
        status__in=[EventStatus.COMPLETED, EventStatus.IN_PROGRESS, EventStatus.PUBLISHED],
        invitations_paused=False
    )

    for event in eligible_events:
        event.update_dynamic_status()
        summary['events_checked'] += 1

        # Check if event has ended based on time or completed status
        if event.is_finished:
            # Check schedule delay
            should_dispatch = False
            if event.invitation_schedule == 'IMMEDIATE':
                should_dispatch = True
            elif event.invitation_schedule == 'AFTER_1_HOUR' and now >= (event.end_time + timedelta(hours=1)):
                should_dispatch = True
            elif event.invitation_schedule == 'AFTER_6_HOURS' and now >= (event.end_time + timedelta(hours=6)):
                should_dispatch = True
            elif event.invitation_schedule == 'AFTER_24_HOURS' and now >= (event.end_time + timedelta(hours=24)):
                should_dispatch = True

            if should_dispatch:
                # 1. Create invitations for all registered eligible attendees
                created = generate_invitations_for_event(event)
                summary['invitations_created'] += created

                # 2. Dispatch pending invitations
                pending_invites = event.invitations.filter(status=InvitationStatus.PENDING)
                for invite in pending_invites:
                    success, _ = dispatch_invitation_email(invite, domain=domain)
                    if success:
                        summary['emails_sent'] += 1
                    else:
                        summary['errors'] += 1

    return summary
