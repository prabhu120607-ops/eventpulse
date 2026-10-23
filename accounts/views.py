from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
import json

from .forms import UniversityLoginForm, UserCreationWithRoleForm, UserProfileUpdateForm
from .models import AuditLog, Notification, UserRole, UserProfile, Department
from events.models import Event, EventStatus, EventRegistration
from feedback.models import (
    FeedbackResponse, FeedbackInvitation, InvitationStatus,
    EmailDeliveryAttempt, FeedbackAnswer, FeedbackQuestion
)
from students.models import Student


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UniversityLoginForm(request, data=request.POST)
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Allow login using either username OR email address
        user = authenticate(request, username=username_or_email, password=password)
        if user is None and '@' in username_or_email:
            try:
                user_obj = User.objects.get(email__iexact=username_or_email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is not None:
            login(request, user)
            # Remember me logic
            if request.POST.get('remember_me'):
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Browser close

            # Record in AuditLog
            ip = request.META.get('REMOTE_ADDR')
            AuditLog.objects.create(
                user=user,
                action='ADMIN_LOGIN',
                details=f"Successful login from IP {ip}",
                ip_address=ip
            )
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            next_url = request.GET.get('next')
            return redirect(next_url if next_url else 'accounts:dashboard')
        else:
            messages.error(request, "Invalid university credentials. Please verify your username/email and password.")
    else:
        form = UniversityLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    user = request.user
    ip = request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        user=user,
        action='ADMIN_LOGOUT',
        details="User logged out",
        ip_address=ip
    )
    logout(request)
    messages.info(request, "You have been securely logged out.")
    return redirect('public:home')


@login_required
def dashboard_view(request):
    """
    Main Administration Dashboard with verified, real-time database metrics.
    """
    # Department or status filters
    selected_dept = request.GET.get('dept')
    selected_category = request.GET.get('category')
    selected_status = request.GET.get('status')

    events_qs = Event.objects.all()

    # Role-based scoping for Department Admins and Organizers
    profile = getattr(request.user, 'profile', None)
    if profile:
        if profile.role == UserRole.DEPT_ADMIN and profile.department:
            events_qs = events_qs.filter(department=profile.department)
        elif profile.role == UserRole.ORGANIZER and not (profile.is_univ_admin or profile.is_super_admin):
            events_qs = events_qs.filter(Q(organizer=request.user) | Q(co_organizers=request.user))

    # Apply URL query filters
    if selected_dept:
        events_qs = events_qs.filter(department_id=selected_dept)
    if selected_category:
        events_qs = events_qs.filter(category=selected_category)
    if selected_status:
        events_qs = events_qs.filter(status=selected_status)

    # Core Metrics
    total_events = events_qs.count()
    upcoming_events_count = events_qs.filter(status=EventStatus.UPCOMING).count()
    completed_events_count = events_qs.filter(status=EventStatus.COMPLETED).count()

    event_ids = events_qs.values_list('id', flat=True)

    # Eligible students registered for these events
    eligible_students_count = EventRegistration.objects.filter(
        event_id__in=event_ids, attended=True
    ).values('student_id').distinct().count()

    total_registrations = EventRegistration.objects.filter(
        event_id__in=event_ids, attended=True
    ).count()

    # Feedback responses
    responses_qs = FeedbackResponse.objects.filter(event_id__in=event_ids)
    submitted_feedback_count = responses_qs.count()

    # Response Rate formula: submitted responses / total eligible registrations * 100
    if total_registrations > 0:
        response_rate = round((submitted_feedback_count / total_registrations) * 100, 1)
    else:
        response_rate = 0.0

    # Average Satisfaction
    avg_rating_dict = responses_qs.aggregate(avg=Avg('overall_rating'))
    average_satisfaction = round(avg_rating_dict['avg'], 2) if avg_rating_dict['avg'] else 0.0

    # Invitations pending & failed deliveries
    pending_invitations_count = FeedbackInvitation.objects.filter(
        event_id__in=event_ids, status=InvitationStatus.PENDING
    ).count()

    failed_email_deliveries_count = EmailDeliveryAttempt.objects.filter(
        status='FAILED', invitation__event_id__in=event_ids
    ).count()

    # Rating distribution [1, 2, 3, 4, 5]
    rating_counts = [
        responses_qs.filter(overall_rating=1).count(),
        responses_qs.filter(overall_rating=2).count(),
        responses_qs.filter(overall_rating=3).count(),
        responses_qs.filter(overall_rating=4).count(),
        responses_qs.filter(overall_rating=5).count(),
    ]

    # Department comparison
    dept_labels = []
    dept_values = []
    for dept in Department.objects.all():
        dept_events = events_qs.filter(department=dept).values_list('id', flat=True)
        avg_d = FeedbackResponse.objects.filter(event_id__in=dept_events).aggregate(avg=Avg('overall_rating'))['avg']
        if avg_d:
            dept_labels.append(dept.code)
            dept_values.append(round(avg_d, 2))

    # Response trends over past 7 days
    now = timezone.now()
    trend_labels = []
    trend_counts = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        count = responses_qs.filter(submitted_at__gte=day_start, submitted_at__lte=day_end).count()
        trend_labels.append(day.strftime('%b %d'))
        trend_counts.append(count)

    # Lists for display
    upcoming_events_list = events_qs.filter(status=EventStatus.UPCOMING).order_by('start_time')[:5]
    completed_events_list = events_qs.filter(status=EventStatus.COMPLETED).order_by('-end_time')[:5]

    # Events requiring attention (completed events with 0 responses or low response rate)
    attention_events = []
    for ev in events_qs.filter(status=EventStatus.COMPLETED)[:8]:
        reg_c = ev.registrations.filter(attended=True).count()
        resp_c = ev.responses.count()
        ev_rate = (resp_c / reg_c * 100) if reg_c > 0 else 0
        if reg_c > 0 and ev_rate < 30:
            attention_events.append({
                'event': ev,
                'registrations': reg_c,
                'responses': resp_c,
                'rate': round(ev_rate, 1)
            })

    # Common suggestions from recent text responses
    suggestion_answers = FeedbackAnswer.objects.filter(
        response__event_id__in=event_ids,
        question__question_type__in=['LONG_TEXT', 'SHORT_TEXT']
    ).exclude(text_value='').order_by('-id')[:5]

    context = {
        'total_events': total_events,
        'upcoming_events_count': upcoming_events_count,
        'completed_events_count': completed_events_count,
        'eligible_students_count': eligible_students_count,
        'submitted_feedback_count': submitted_feedback_count,
        'response_rate': response_rate,
        'average_satisfaction': average_satisfaction,
        'pending_invitations_count': pending_invitations_count,
        'failed_email_deliveries_count': failed_email_deliveries_count,

        'rating_counts_json': json.dumps(rating_counts),
        'dept_labels_json': json.dumps(dept_labels),
        'dept_values_json': json.dumps(dept_values),
        'trend_labels_json': json.dumps(trend_labels),
        'trend_counts_json': json.dumps(trend_counts),

        'upcoming_events_list': upcoming_events_list,
        'completed_events_list': completed_events_list,
        'attention_events': attention_events,
        'suggestion_answers': suggestion_answers,

        'departments': Department.objects.all(),
        'selected_dept': selected_dept,
        'selected_category': selected_category,
        'selected_status': selected_status,
    }
    return render(request, 'admin/dashboard.html', context)


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.save()
            form.save()
            messages.success(request, "Your profile details have been updated successfully.")
            return redirect('accounts:profile')
    else:
        form = UserProfileUpdateForm(instance=profile, user=request.user)

    return render(request, 'accounts/profile.html', {'form': form, 'profile': profile})


@login_required
def users_list_view(request):
    profile = getattr(request.user, 'profile', None)
    if not (request.user.is_superuser or (profile and profile.is_univ_admin)):
        messages.error(request, "You are not authorized to view user management.")
        return redirect('accounts:dashboard')

    users = User.objects.all().select_related('profile', 'profile__department').order_by('username')
    return render(request, 'accounts/users_list.html', {'users': users})


@login_required
def user_create_view(request):
    profile = getattr(request.user, 'profile', None)
    if not (request.user.is_superuser or (profile and profile.is_univ_admin)):
        messages.error(request, "Access denied.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UserCreationWithRoleForm(request.POST)
        if form.is_valid():
            new_user = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE_USER',
                details=f"Created administrative user {new_user.username} with role {form.cleaned_data['role']}"
            )
            messages.success(request, f"User '{new_user.username}' created successfully.")
            return redirect('accounts:users_list')
    else:
        form = UserCreationWithRoleForm()

    return render(request, 'accounts/user_form.html', {'form': form})


@login_required
def audit_logs_view(request):
    logs = AuditLog.objects.all().select_related('user')[:100]
    return render(request, 'admin/audit_logs.html', {'logs': logs})


@login_required
def notifications_list_view(request):
    notifications = Notification.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    ).order_by('-created_at')[:50]

    # Mark as read
    if request.GET.get('mark_read') == 'all':
        Notification.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            is_read=False
        ).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('accounts:notifications_list')

    return render(request, 'admin/notifications.html', {'notifications': notifications})
