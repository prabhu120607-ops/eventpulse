from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Avg, Q

from .models import (
    FeedbackForm, FeedbackQuestion, FeedbackInvitation, InvitationStatus,
    FeedbackResponse, FeedbackAnswer, EmailDeliveryAttempt, QuestionType
)
from .forms import FeedbackQuestionForm, DynamicStudentFeedbackForm
from .services import (
    generate_invitations_for_event, dispatch_invitation_email,
    process_pending_event_automations
)
from events.models import Event, EventStatus
from accounts.models import AuditLog, Notification
from analytics.services import run_ai_analysis_for_event, analyze_sentiment


@login_required
def form_list_view(request):
    forms = FeedbackForm.objects.select_related('event', 'event__department').order_by('-event__start_time')
    return render(request, 'feedback/form_list.html', {'forms': forms})


@login_required
def form_builder_view(request, form_id):
    feedback_form = get_object_or_404(FeedbackForm.objects.select_related('event'), id=form_id)
    questions = feedback_form.questions.all().order_by('order', 'id')

    if request.method == 'POST':
        question_form = FeedbackQuestionForm(request.POST)
        if question_form.is_valid():
            new_q = question_form.save(commit=False)
            new_q.form = feedback_form
            # Auto-assign next order number
            max_order = questions.last().order if questions.exists() else 0
            new_q.order = max_order + 1
            new_q.save()

            AuditLog.objects.create(
                user=request.user,
                action='ADD_FEEDBACK_QUESTION',
                details=f"Added question '{new_q.question_text[:40]}' to form for event '{feedback_form.event.title}'"
            )
            messages.success(request, "New question added to feedback form.")
            return redirect('feedback:form_builder', form_id=feedback_form.id)
    else:
        question_form = FeedbackQuestionForm()

    context = {
        'feedback_form': feedback_form,
        'event': feedback_form.event,
        'questions': questions,
        'question_form': question_form,
    }
    return render(request, 'feedback/form_builder.html', context)


@login_required
def form_delete_question_view(request, form_id, question_id):
    feedback_form = get_object_or_404(FeedbackForm, id=form_id)
    question = get_object_or_404(FeedbackQuestion, id=question_id, form=feedback_form)
    question_text = question.question_text
    question.delete()

    AuditLog.objects.create(
        user=request.user,
        action='DELETE_FEEDBACK_QUESTION',
        details=f"Removed question '{question_text[:40]}' from form for event '{feedback_form.event.title}'"
    )
    messages.info(request, "Question removed from form.")
    return redirect('feedback:form_builder', form_id=feedback_form.id)


def form_preview_view(request, form_id):
    """
    Renders the exact student form in preview mode without saving responses.
    """
    feedback_form = get_object_or_404(FeedbackForm.objects.select_related('event'), id=form_id)
    form = DynamicStudentFeedbackForm(feedback_form=feedback_form)

    context = {
        'feedback_form': feedback_form,
        'event': feedback_form.event,
        'form': form,
        'is_preview': True,
    }
    return render(request, 'feedback/submit_feedback.html', context)


def submit_feedback_view(request, token):
    """
    Secure feedback submission endpoint reached exclusively via cryptographic token.
    Validates token, checks expiration and single-use status, enforces anonymity or identity,
    and records answers.
    """
    invitation = FeedbackInvitation.objects.select_related('event', 'student', 'feedback_form').filter(token=token).first()

    # 1. Check token validity
    if not invitation:
        return render(request, 'feedback/submission_error.html', {
            'error_title': 'Invalid Invitation Link',
            'error_message': 'This feedback invitation link does not exist or has been corrupted. Please check your invitation email.'
        })

    event = invitation.event
    feedback_form = invitation.feedback_form

    # 2. Check if already submitted (duplicate submission prevention)
    if invitation.status == InvitationStatus.COMPLETED:
        return render(request, 'feedback/submission_error.html', {
            'error_title': 'Feedback Already Submitted',
            'error_message': f'Thank you! Feedback for {event.title} has already been recorded from this invitation link. Responses cannot be submitted more than once.',
            'event': event,
            'is_duplicate': True
        })

    # 3. Check expiration & deadline
    if invitation.is_expired or not event.is_feedback_open:
        return render(request, 'feedback/submission_error.html', {
            'error_title': 'Feedback Period Closed',
            'error_message': f'The evaluation window for {event.title} closed on {event.feedback_deadline.strftime("%b %d, %Y at %I:%M %p") if event.feedback_deadline else "the deadline"}. No further submissions are accepted.',
            'event': event,
            'is_expired': True
        })

    # 4. Handle Submission
    if request.method == 'POST':
        dyn_form = DynamicStudentFeedbackForm(request.POST, feedback_form=feedback_form)
        if dyn_form.is_valid():
            # Calculate overall rating
            overall_rating = 5
            all_text_comments = []

            # Determine anonymity
            is_anon = (event.feedback_mode == 'ANONYMOUS')
            student_ref = None if is_anon else invitation.student

            # Create FeedbackResponse
            # Note: For anonymous mode, student is strictly NULL and invitation foreign key is omitted!
            response_obj = FeedbackResponse.objects.create(
                event=event,
                feedback_form=feedback_form,
                student=student_ref,
                is_anonymous=is_anon,
                overall_rating=5,  # updated below
                ip_address=request.META.get('REMOTE_ADDR')
            )

            for q in feedback_form.questions.all():
                field_name = f"question_{q.id}"
                raw_val = dyn_form.cleaned_data.get(field_name)

                rating_val = None
                text_val = ""
                selected_choices = []

                if q.question_type == QuestionType.STAR_RATING:
                    if raw_val is not None:
                        rating_val = int(raw_val)
                        if q.category_tag == 'OVERALL' or q.order == 1:
                            overall_rating = rating_val
                elif q.question_type == QuestionType.MULTIPLE_CHOICE:
                    selected_choices = raw_val or []
                elif q.question_type in [QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT]:
                    text_val = str(raw_val or '').strip()
                    if text_val:
                        all_text_comments.append(text_val)
                elif q.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.YES_NO]:
                    text_val = str(raw_val or '').strip()

                FeedbackAnswer.objects.create(
                    response=response_obj,
                    question=q,
                    rating_value=rating_val,
                    text_value=text_val,
                    selected_choices=selected_choices
                )

            # Sentiment calculation on submitted text comments
            combined_text = " ".join(all_text_comments)
            score, sentiment_label = analyze_sentiment(combined_text)

            response_obj.overall_rating = overall_rating
            response_obj.sentiment = sentiment_label
            response_obj.sentiment_score = score
            response_obj.save(update_fields=['overall_rating', 'sentiment', 'sentiment_score'])

            # 5. Consume the invitation token permanently
            now = timezone.now()
            invitation.status = InvitationStatus.COMPLETED
            invitation.completed_at = now
            invitation.save(update_fields=['status', 'completed_at'])

            # 6. Run NLP theme analyzer to refresh event insights
            try:
                run_ai_analysis_for_event(event)
            except Exception:
                pass  # analysis runs safely in background

            return redirect('feedback:submission_success')
    else:
        dyn_form = DynamicStudentFeedbackForm(feedback_form=feedback_form)

    context = {
        'feedback_form': feedback_form,
        'event': event,
        'form': dyn_form,
        'invitation': invitation,
        'is_anonymous': (event.feedback_mode == 'ANONYMOUS'),
    }
    return render(request, 'feedback/submit_feedback.html', context)


def submission_success_view(request):
    return render(request, 'feedback/submission_success.html')


@login_required
def event_responses_view(request, event_id):
    """
    Shows submitted feedback responses and answers for an event.
    Respects anonymity: If anonymous, no student IDs or identities are shown.
    """
    event = get_object_or_404(Event.objects.select_related('department'), id=event_id)
    responses_qs = event.responses.prefetch_related('answers', 'answers__question', 'student').all().order_by('-submitted_at')

    avg_rating = responses_qs.aggregate(avg=Avg('overall_rating'))['avg']
    avg_rating = round(avg_rating, 2) if avg_rating else 0.0

    paginator = Paginator(responses_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'event': event,
        'page_obj': page_obj,
        'total_responses': responses_qs.count(),
        'avg_rating': avg_rating,
        'ai_analysis': getattr(event, 'ai_analysis', None),
    }
    return render(request, 'feedback/feedback_responses.html', context)


@login_required
def invitations_list_view(request):
    event_id = request.GET.get('event', '')
    status = request.GET.get('status', '')

    invitations_qs = FeedbackInvitation.objects.select_related('event', 'student').all()

    if event_id:
        invitations_qs = invitations_qs.filter(event_id=event_id)
    if status:
        invitations_qs = invitations_qs.filter(status=status)

    paginator = Paginator(invitations_qs, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'events': Event.objects.all().order_by('-start_time'),
        'selected_event': event_id,
        'selected_status': status,
        'total_invitations': invitations_qs.count(),
    }
    return render(request, 'feedback/invitations_list.html', context)


@login_required
def trigger_event_invitations_view(request, event_id):
    """
    Manually creates and dispatches invitation tokens for all eligible attendees of an event.
    """
    event = get_object_or_404(Event, id=event_id)
    created_count = generate_invitations_for_event(event)

    # Dispatch pending invitations
    pending = event.invitations.filter(status=InvitationStatus.PENDING)
    sent_count = 0
    fail_count = 0

    for inv in pending:
        success, _ = dispatch_invitation_email(inv, request=request)
        if success:
            sent_count += 1
        else:
            fail_count += 1

    AuditLog.objects.create(
        user=request.user,
        action='TRIGGER_INVITATIONS',
        details=f"Dispatched feedback invitations for '{event.title}': {sent_count} sent, {fail_count} failed."
    )

    messages.success(request, f"Feedback invitation dispatch complete: {sent_count} invitations emailed ({fail_count} failures).")
    return redirect('events:event_detail', event_id=event.id)


@login_required
def send_reminders_view(request, event_id):
    """
    Dispatches reminder emails to students whose invitations are pending or sent but not completed.
    """
    event = get_object_or_404(Event, id=event_id)
    uncompleted = event.invitations.filter(status__in=[InvitationStatus.SENT, InvitationStatus.PENDING])

    sent_count = 0
    for inv in uncompleted:
        success, _ = dispatch_invitation_email(inv, request=request)
        if success:
            sent_count += 1

    AuditLog.objects.create(
        user=request.user,
        action='SEND_FEEDBACK_REMINDERS',
        details=f"Dispatched {sent_count} reminders for event '{event.title}'."
    )
    messages.success(request, f"Dispatched {sent_count} reminder emails to pending attendees.")
    return redirect('events:event_detail', event_id=event.id)


@login_required
def process_automations_view(request):
    """
    Triggers the automated checks manually from dashboard button.
    """
    host = request.get_host()
    summary = process_pending_event_automations(domain=host)

    messages.success(
        request,
        f"Automations checked {summary['events_checked']} events: {summary['invitations_created']} invitations created, "
        f"{summary['emails_sent']} emails dispatched."
    )
    return redirect('accounts:dashboard')


@login_required
def test_email_view(request):
    """
    Sends a test email to verify that the configured Django email backend operates correctly.
    """
    recipient = request.POST.get('test_email', request.user.email)
    try:
        send_mail(
            subject="EventPulse Test Email Verification",
            message="This is a test notification verifying that the EventPulse email subsystem is operating correctly.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False
        )
        EmailDeliveryAttempt.objects.create(
            recipient_email=recipient,
            subject="EventPulse Test Email Verification",
            attempt_type='TEST',
            status='SUCCESS'
        )
        messages.success(request, f"Test email sent successfully to {recipient} (printed to console if using console backend).")
    except Exception as e:
        EmailDeliveryAttempt.objects.create(
            recipient_email=recipient,
            subject="EventPulse Test Email Verification",
            attempt_type='TEST',
            status='FAILED',
            error_message=str(e)
        )
        messages.error(request, f"Test email delivery failed: {str(e)}")

    return redirect('feedback:invitations_list')
