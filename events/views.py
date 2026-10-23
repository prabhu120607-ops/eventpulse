from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator

from .models import Event, EventRegistration, ManagementAction, EventStatus, FeedbackMode
from .forms import EventForm, ManagementActionForm
from accounts.models import Department, AuditLog, UserRole
from students.models import Student
from feedback.models import (
    FeedbackForm, FeedbackQuestion, QuestionType,
    FeedbackInvitation, FeedbackResponse, InvitationStatus
)


def create_default_feedback_questions(form):
    """
    Provisions a comprehensive set of institutional feedback questions for newly created events.
    """
    questions_data = [
        {
            'text': 'Overall Event Experience & Satisfaction',
            'type': QuestionType.STAR_RATING,
            'tag': 'OVERALL',
            'required': True,
            'order': 1,
            'choices': ''
        },
        {
            'text': 'Content Depth, Relevance & Quality',
            'type': QuestionType.STAR_RATING,
            'tag': 'CONTENT',
            'required': True,
            'order': 2,
            'choices': ''
        },
        {
            'text': 'Speaker / Instructor Effectiveness & Clarity',
            'type': QuestionType.STAR_RATING,
            'tag': 'SPEAKER',
            'required': True,
            'order': 3,
            'choices': ''
        },
        {
            'text': 'Event Organization, Schedule & Coordination',
            'type': QuestionType.STAR_RATING,
            'tag': 'ORGANIZATION',
            'required': True,
            'order': 4,
            'choices': ''
        },
        {
            'text': 'Venue, Audio/Visual Setup & Facilities',
            'type': QuestionType.STAR_RATING,
            'tag': 'VENUE',
            'required': False,
            'order': 5,
            'choices': ''
        },
        {
            'text': 'How was the duration and pacing of the session?',
            'type': QuestionType.SINGLE_CHOICE,
            'tag': 'TIME',
            'required': True,
            'order': 6,
            'choices': 'Too Short - Needed more time\nJust Right - Well balanced\nToo Long - Pacing was slow'
        },
        {
            'text': 'What aspects of this event did you find most valuable?',
            'type': QuestionType.LONG_TEXT,
            'tag': 'CONTENT',
            'required': False,
            'order': 7,
            'choices': ''
        },
        {
            'text': 'What constructive suggestions do you have for future sessions?',
            'type': QuestionType.LONG_TEXT,
            'tag': 'SUGGESTIONS',
            'required': False,
            'order': 8,
            'choices': ''
        },
        {
            'text': 'Would you recommend similar events to your fellow university peers?',
            'type': QuestionType.YES_NO,
            'tag': 'OVERALL',
            'required': True,
            'order': 9,
            'choices': 'Yes\nNo'
        },
    ]

    for q in questions_data:
        FeedbackQuestion.objects.create(
            form=form,
            question_text=q['text'],
            question_type=q['type'],
            category_tag=q['tag'],
            is_required=q['required'],
            order=q['order'],
            choices_raw=q['choices']
        )


@login_required
def event_list_view(request):
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    dept_id = request.GET.get('dept', '')

    events_qs = Event.objects.select_related('department', 'organizer').all()

    # Scope by user role
    profile = getattr(request.user, 'profile', None)
    if profile:
        if profile.role == UserRole.DEPT_ADMIN and profile.department:
            events_qs = events_qs.filter(department=profile.department)
        elif profile.role == UserRole.ORGANIZER and not (profile.is_univ_admin or profile.is_super_admin):
            events_qs = events_qs.filter(Q(organizer=request.user) | Q(co_organizers=request.user))

    if query:
        events_qs = events_qs.filter(Q(title__icontains=query) | Q(venue__icontains=query) | Q(description__icontains=query))
    if category:
        events_qs = events_qs.filter(category=category)
    if status:
        events_qs = events_qs.filter(status=status)
    if dept_id:
        events_qs = events_qs.filter(department_id=dept_id)

    # Dynamic status update check
    for ev in events_qs[:20]:
        ev.update_dynamic_status()

    paginator = Paginator(events_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'departments': Department.objects.all(),
        'query': query,
        'selected_category': category,
        'selected_status': status,
        'selected_dept': dept_id,
        'total_count': events_qs.count(),
    }
    return render(request, 'events/event_list.html', context)


@login_required
def event_create_view(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            form.save_m2m()

            # Automatically generate associated FeedbackForm with standard institutional questions
            feedback_form = FeedbackForm.objects.create(
                event=event,
                title=f"Feedback: {event.title}",
                description=f"Thank you for attending {event.title}. Please provide your candid evaluation below."
            )
            create_default_feedback_questions(feedback_form)

            AuditLog.objects.create(
                user=request.user,
                action='CREATE_EVENT',
                details=f"Created event '{event.title}' with default feedback form.",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f"Event '{event.title}' created successfully with feedback questions configured!")
            return redirect('events:event_detail', event_id=event.id)
    else:
        # Prepopulate sensible defaults
        now = timezone.now()
        initial_data = {
            'start_time': (now + timezone.timedelta(days=1)).replace(minute=0, second=0).strftime('%Y-%m-%dT%H:%M'),
            'end_time': (now + timezone.timedelta(days=1, hours=2)).replace(minute=0, second=0).strftime('%Y-%m-%dT%H:%M'),
            'feedback_deadline': (now + timezone.timedelta(days=5)).replace(minute=0, second=0).strftime('%Y-%m-%dT%H:%M'),
            'status': EventStatus.UPCOMING,
            'feedback_mode': FeedbackMode.ANONYMOUS,
        }
        form = EventForm(initial=initial_data)

    return render(request, 'events/event_create.html', {'form': form})


@login_required
def event_edit_view(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE_EVENT',
                details=f"Updated parameters for event '{event.title}'.",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f"Event '{event.title}' updated successfully.")
            return redirect('events:event_detail', event_id=event.id)
    else:
        initial = {}
        if event.start_time:
            initial['start_time'] = event.start_time.strftime('%Y-%m-%dT%H:%M')
        if event.end_time:
            initial['end_time'] = event.end_time.strftime('%Y-%m-%dT%H:%M')
        if event.feedback_deadline:
            initial['feedback_deadline'] = event.feedback_deadline.strftime('%Y-%m-%dT%H:%M')
        form = EventForm(instance=event, initial=initial)

    return render(request, 'events/event_edit.html', {'form': form, 'event': event})


@login_required
def event_detail_view(request, event_id):
    event = get_object_or_404(Event.objects.select_related('department', 'organizer'), id=event_id)
    event.update_dynamic_status()

    # Registrations & feedback metrics
    registrations = event.registrations.select_related('student').all()
    reg_count = registrations.count()
    attended_count = registrations.filter(attended=True).count()
    response_count = event.responses.count()

    response_rate = round((response_count / attended_count * 100), 1) if attended_count > 0 else 0.0
    avg_rating = event.responses.aggregate(avg=Avg('overall_rating'))['avg']
    avg_rating = round(avg_rating, 2) if avg_rating else 0.0

    # Invitations telemetry
    invitations = event.invitations.select_related('student').all()
    sent_count = invitations.filter(status__in=[InvitationStatus.SENT, InvitationStatus.COMPLETED]).count()
    pending_count = invitations.filter(status=InvitationStatus.PENDING).count()
    completed_invite_count = invitations.filter(status=InvitationStatus.COMPLETED).count()

    # Management actions
    actions = event.actions.select_related('assigned_to').all()

    # Form to add action
    if request.method == 'POST' and 'add_action' in request.POST:
        action_form = ManagementActionForm(request.POST)
        if action_form.is_valid():
            act = action_form.save(commit=False)
            act.event = event
            act.save()
            messages.success(request, "Management improvement action logged.")
            return redirect('events:event_detail', event_id=event.id)
    else:
        action_form = ManagementActionForm()

    context = {
        'event': event,
        'registrations': registrations[:50],
        'reg_count': reg_count,
        'attended_count': attended_count,
        'response_count': response_count,
        'response_rate': response_rate,
        'avg_rating': avg_rating,
        'invitations': invitations[:50],
        'sent_count': sent_count,
        'pending_count': pending_count,
        'completed_invite_count': completed_invite_count,
        'actions': actions,
        'action_form': action_form,
        'all_students': Student.objects.filter(enrollment_status='ACTIVE').exclude(event_registrations__event=event)[:100],
    }
    return render(request, 'events/event_detail.html', context)


@login_required
def event_associate_students_view(request, event_id):
    """
    Enrolls students into an event roster directly from database.
    """
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        student_ids = request.POST.getlist('selected_students')
        enrolled_count = 0
        for s_id in student_ids:
            reg, created = EventRegistration.objects.get_or_create(
                event=event,
                student_id=s_id,
                defaults={'attended': True}
            )
            if created:
                enrolled_count += 1

        AuditLog.objects.create(
            user=request.user,
            action='ENROLL_STUDENTS_EVENT',
            details=f"Enrolled {enrolled_count} students into event '{event.title}'."
        )
        messages.success(request, f"Successfully added {enrolled_count} students to '{event.title}'.")

    return redirect('events:event_detail', event_id=event.id)


@login_required
def event_toggle_pause_view(request, event_id):
    """
    Allows organizer to pause or resume automated feedback emails for this event.
    """
    event = get_object_or_404(Event, id=event_id)
    event.invitations_paused = not event.invitations_paused
    event.save(update_fields=['invitations_paused'])

    status_str = "PAUSED" if event.invitations_paused else "ACTIVE / RESUMED"
    AuditLog.objects.create(
        user=request.user,
        action='TOGGLE_EVENT_AUTOMATION',
        details=f"Automated invitations for '{event.title}' set to {status_str}."
    )
    messages.info(request, f"Automated invitation triggers for '{event.title}' are now {status_str}.")
    return redirect('events:event_detail', event_id=event.id)
