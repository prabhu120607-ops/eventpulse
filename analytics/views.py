import csv
import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q

from events.models import Event, EventStatus, EventRegistration
from feedback.models import (
    FeedbackResponse, FeedbackInvitation, InvitationStatus,
    EmailDeliveryAttempt, FeedbackQuestion, FeedbackAnswer
)
from accounts.models import Department, UserRole
from .models import AIAnalysisResult
from .services import run_ai_analysis_for_event


@login_required
def analytics_dashboard_view(request):
    """
    Main Analytics Dashboard with Chart.js charts and institutional benchmarks.
    """
    event_id = request.GET.get('event')
    dept_id = request.GET.get('dept')
    category = request.GET.get('category')

    events_qs = Event.objects.all()

    # Role scoping
    profile = getattr(request.user, 'profile', None)
    if profile:
        if profile.role == UserRole.DEPT_ADMIN and profile.department:
            events_qs = events_qs.filter(department=profile.department)
        elif profile.role == UserRole.ORGANIZER and not (profile.is_univ_admin or profile.is_super_admin):
            events_qs = events_qs.filter(Q(organizer=request.user) | Q(co_organizers=request.user))

    if event_id:
        events_qs = events_qs.filter(id=event_id)
    if dept_id:
        events_qs = events_qs.filter(department_id=dept_id)
    if category:
        events_qs = events_qs.filter(category=category)

    event_ids = events_qs.values_list('id', flat=True)

    # Core numbers
    total_eligible = EventRegistration.objects.filter(event_id__in=event_ids, attended=True).count()
    total_invitations = FeedbackInvitation.objects.filter(event_id__in=event_ids).count()
    delivered_invitations = FeedbackInvitation.objects.filter(
        event_id__in=event_ids, status__in=[InvitationStatus.SENT, InvitationStatus.COMPLETED]
    ).count()

    responses_qs = FeedbackResponse.objects.filter(event_id__in=event_ids)
    submitted_responses = responses_qs.count()

    # Formulas
    response_rate = round((submitted_responses / total_eligible * 100), 1) if total_eligible > 0 else 0.0
    delivery_rate = round((delivered_invitations / total_invitations * 100), 1) if total_invitations > 0 else 0.0

    avg_rating = responses_qs.aggregate(avg=Avg('overall_rating'))['avg']
    avg_rating = round(avg_rating, 2) if avg_rating else 0.0

    # Rating distribution
    rating_data = [
        responses_qs.filter(overall_rating=1).count(),
        responses_qs.filter(overall_rating=2).count(),
        responses_qs.filter(overall_rating=3).count(),
        responses_qs.filter(overall_rating=4).count(),
        responses_qs.filter(overall_rating=5).count(),
    ]

    # Department ratings
    dept_labels = []
    dept_ratings = []
    for d in Department.objects.all():
        d_events = Event.objects.filter(department=d).values_list('id', flat=True)
        d_avg = FeedbackResponse.objects.filter(event_id__in=d_events).aggregate(avg=Avg('overall_rating'))['avg']
        if d_avg:
            dept_labels.append(d.code)
            dept_ratings.append(round(d_avg, 2))

    # Event rating comparison (Top 8 events)
    event_comp_labels = []
    event_comp_values = []
    for ev in events_qs.filter(status=EventStatus.COMPLETED)[:8]:
        ev_avg = ev.responses.aggregate(avg=Avg('overall_rating'))['avg']
        if ev_avg:
            event_comp_labels.append(ev.title[:20])
            event_comp_values.append(round(ev_avg, 2))

    # Response trend over past 14 days
    now = timezone.now()
    trend_labels = []
    trend_counts = []
    for i in range(13, -1, -1):
        day = now - timedelta(days=i)
        d_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        d_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        c = responses_qs.filter(submitted_at__gte=d_start, submitted_at__lte=d_end).count()
        trend_labels.append(day.strftime('%b %d'))
        trend_counts.append(c)

    # Aggregated AI analyses
    ai_results = AIAnalysisResult.objects.filter(event_id__in=event_ids).order_by('-calculated_at')[:5]

    context = {
        'total_eligible': total_eligible,
        'total_invitations': total_invitations,
        'delivered_invitations': delivered_invitations,
        'submitted_responses': submitted_responses,
        'response_rate': response_rate,
        'delivery_rate': delivery_rate,
        'avg_rating': avg_rating,

        'rating_data_json': json.dumps(rating_data),
        'dept_labels_json': json.dumps(dept_labels),
        'dept_ratings_json': json.dumps(dept_ratings),
        'event_comp_labels_json': json.dumps(event_comp_labels),
        'event_comp_values_json': json.dumps(event_comp_values),
        'trend_labels_json': json.dumps(trend_labels),
        'trend_counts_json': json.dumps(trend_counts),

        'ai_results': ai_results,
        'all_events': Event.objects.all().order_by('-start_time'),
        'departments': Department.objects.all(),
        'selected_event': event_id,
        'selected_dept': dept_id,
        'selected_category': category,
    }
    return render(request, 'analytics/dashboard.html', context)


@login_required
def reports_home_view(request):
    """
    Central hub for downloading CSV reports and executive exports.
    """
    events = Event.objects.all().order_by('-start_time')
    departments = Department.objects.all()
    return render(request, 'reports/reports_home.html', {'events': events, 'departments': departments})


@login_required
def export_event_report_csv(request, event_id):
    """
    Exports a clean CSV feedback report for a specific event.
    Applies privacy controls: Student personal IDs are omitted in anonymous reports!
    """
    event = get_object_or_404(Event.objects.select_related('department'), id=event_id)
    responses = event.responses.prefetch_related('answers', 'answers__question').all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="eventpulse_report_{event.id}.csv"'

    writer = csv.writer(response)

    # Metadata Header
    writer.writerow(["EVENTPULSE INSTITUTIONAL FEEDBACK REPORT"])
    writer.writerow(["Event Title", event.title])
    writer.writerow(["Category", event.get_category_display()])
    writer.writerow(["Department", event.department.name if event.department else "University-Wide"])
    writer.writerow(["Venue", event.venue])
    writer.writerow(["Date", event.start_time.strftime("%Y-%m-%d")])
    writer.writerow(["Feedback Mode", event.get_feedback_mode_display()])

    eligible = event.registrations.filter(attended=True).count()
    resp_count = responses.count()
    rate = round((resp_count / eligible * 100), 1) if eligible > 0 else 0
    avg_r = responses.aggregate(avg=Avg('overall_rating'))['avg']
    avg_r = round(avg_r, 2) if avg_r else 0

    writer.writerow(["Eligible Attendees", eligible])
    writer.writerow(["Responses Submitted", resp_count])
    writer.writerow(["Response Rate (%)", f"{rate}%"])
    writer.writerow(["Average Rating (1-5)", avg_r])
    writer.writerow([])

    # Questions & Answers
    questions = event.feedback_form.questions.all().order_by('order')
    header_row = ["Response #", "Respondent", "Overall Rating", "Sentiment", "Submitted At"]
    for q in questions:
        header_row.append(f"Q{q.order}: {q.question_text}")
    writer.writerow(header_row)

    for idx, resp in enumerate(responses, start=1):
        respondent_label = "Anonymous Attendee" if resp.is_anonymous else (resp.student.full_name if resp.student else "Student")
        row = [
            idx,
            respondent_label,
            resp.overall_rating,
            resp.sentiment,
            resp.submitted_at.strftime("%Y-%m-%d %H:%M")
        ]
        answers_map = {ans.question_id: ans.display_value() for ans in resp.answers.all()}
        for q in questions:
            row.append(answers_map.get(q.id, ""))
        writer.writerow(row)

    return response


@login_required
def export_university_report_csv(request):
    """
    Exports a university-wide aggregate satisfaction benchmark report across all events.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="eventpulse_university_satisfaction_audit.csv"'

    writer = csv.writer(response)
    writer.writerow(["Event ID", "Event Title", "Category", "Department", "Start Date", "Eligible Attendees", "Responses", "Response Rate (%)", "Avg Satisfaction (1-5)"])

    for ev in Event.objects.select_related('department').all().order_by('-start_time'):
        eligible = ev.registrations.filter(attended=True).count()
        resp_c = ev.responses.count()
        rate = round((resp_c / eligible * 100), 1) if eligible > 0 else 0
        avg_s = ev.responses.aggregate(avg=Avg('overall_rating'))['avg']
        avg_s = round(avg_s, 2) if avg_s else "N/A"

        writer.writerow([
            ev.id,
            ev.title,
            ev.get_category_display(),
            ev.department.name if ev.department else "University-Wide",
            ev.start_time.strftime("%Y-%m-%d"),
            eligible,
            resp_c,
            f"{rate}%",
            avg_s
        ])

    return response
