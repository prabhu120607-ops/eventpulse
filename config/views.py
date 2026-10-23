from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from events.models import Event, EventStatus, EventRegistration
from feedback.models import FeedbackResponse
from students.models import Student, EnrollmentStatus
from events.forms import StudentPublicRegistrationForm
from accounts.models import AuditLog


def home_view(request):
    """
    Public landing page with live platform statistics and featured upcoming events.
    """
    total_events = Event.objects.filter(status__in=[EventStatus.COMPLETED, EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.UPCOMING]).count()
    total_feedback = FeedbackResponse.objects.count()
    total_students = Student.objects.count()

    upcoming_events = Event.objects.filter(
        status__in=[EventStatus.UPCOMING, EventStatus.PUBLISHED, EventStatus.IN_PROGRESS]
    ).order_by('start_time')[:3]

    context = {
        'total_events': total_events,
        'total_feedback': total_feedback,
        'total_students': total_students,
        'upcoming_events': upcoming_events,
    }
    return render(request, 'public/home.html', context)


def public_events_view(request):
    """
    Public directory of upcoming campus activities that students can discover and register for.
    """
    events = Event.objects.filter(
        status__in=[EventStatus.UPCOMING, EventStatus.PUBLISHED, EventStatus.IN_PROGRESS]
    ).order_by('start_time')

    for ev in events:
        ev.update_dynamic_status()

    return render(request, 'public/events_list.html', {'events': events})


def public_register_event_view(request, event_id):
    """
    Allows a student to register for a campus event without needing an account.
    Records them in the event roster and explains exactly when feedback will be collected.
    """
    event = get_object_or_404(Event, id=event_id)
    event.update_dynamic_status()

    registered_success = False
    registered_student = None

    if request.method == 'POST':
        form = StudentPublicRegistrationForm(request.POST)
        if form.is_valid():
            s_num = form.cleaned_data['student_number'].strip()
            name = form.cleaned_data['full_name'].strip()
            email = form.cleaned_data['university_email'].strip().lower()
            dept = form.cleaned_data.get('department')
            year = form.cleaned_data.get('academic_year')

            # Upsert student
            student, _ = Student.objects.get_or_create(
                student_number=s_num,
                defaults={
                    'full_name': name,
                    'university_email': email,
                    'department': dept,
                    'academic_year': year,
                    'enrollment_status': EnrollmentStatus.ACTIVE
                }
            )
            # Update info if provided
            student.full_name = name
            student.university_email = email
            if dept:
                student.department = dept
            if year:
                student.academic_year = year
            student.save()

            # Register for event
            reg, created = EventRegistration.objects.get_or_create(
                event=event,
                student=student,
                defaults={'attended': True}
            )

            registered_success = True
            registered_student = student

            AuditLog.objects.create(
                user=None,
                action='STUDENT_EVENT_REGISTRATION',
                details=f"Student {student.full_name} ({student.student_number}) registered publicly for '{event.title}'.",
                ip_address=request.META.get('REMOTE_ADDR')
            )
    else:
        form = StudentPublicRegistrationForm()

    context = {
        'event': event,
        'form': form,
        'registered_success': registered_success,
        'registered_student': registered_student,
    }
    return render(request, 'public/register_event.html', context)


def features_view(request):
    return render(request, 'public/features.html')


def how_it_works_view(request):
    return render(request, 'public/how_it_works.html')


def about_view(request):
    return render(request, 'public/about.html')


def contact_view(request):
    submitted = False
    if request.method == 'POST':
        submitted = True
    return render(request, 'public/contact.html', {'submitted': submitted})
