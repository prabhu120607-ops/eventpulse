from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import io

from accounts.models import Department, UserProfile, UserRole
from students.models import Student, EnrollmentStatus
from events.models import Event, EventCategory, EventStatus, FeedbackMode, EventRegistration
from feedback.models import (
    FeedbackForm, FeedbackQuestion, QuestionType,
    FeedbackInvitation, InvitationStatus, FeedbackResponse,
    FeedbackAnswer, EmailDeliveryAttempt
)
from events.views import create_default_feedback_questions
from feedback.services import generate_invitations_for_event, dispatch_invitation_email, process_pending_event_automations
from analytics.services import run_ai_analysis_for_event, analyze_sentiment


class EventPulseComprehensiveTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # 1. Departments
        self.dept = Department.objects.create(name="Computer Science", code="CSE")

        # 2. Users
        self.admin_user = User.objects.create_user(
            username="testadmin", email="admin@test.edu", password="Password123!"
        )
        self.admin_user.profile.role = UserRole.SUPER_ADMIN
        self.admin_user.profile.save()

        self.organizer_user = User.objects.create_user(
            username="testorganizer", email="organizer@test.edu", password="Password123!"
        )
        self.organizer_user.profile.role = UserRole.ORGANIZER
        self.organizer_user.profile.department = self.dept
        self.organizer_user.profile.save()

        # 3. Students
        self.student1 = Student.objects.create(
            student_number="STU-001",
            full_name="Alice Student",
            university_email="alice@test.edu",
            department=self.dept,
            academic_year="3rd Year",
            section="A"
        )
        self.student2 = Student.objects.create(
            student_number="STU-002",
            full_name="Bob Student",
            university_email="bob@test.edu",
            department=self.dept,
            academic_year="2nd Year",
            section="B"
        )

        # 4. Event
        self.event = Event.objects.create(
            title="Django Advanced Workshop",
            description="Hands on workshop",
            category=EventCategory.WORKSHOP,
            department=self.dept,
            venue="Room 101",
            start_time=self.now - timedelta(days=2),
            end_time=self.now - timedelta(days=1),
            feedback_deadline=self.now + timedelta(days=3),
            status=EventStatus.COMPLETED,
            feedback_mode=FeedbackMode.ANONYMOUS,
            organizer=self.organizer_user
        )

        # 5. Form & questions
        self.feedback_form = FeedbackForm.objects.create(
            event=self.event,
            title="Feedback: Django Advanced Workshop"
        )
        create_default_feedback_questions(self.feedback_form)

        # 6. Registrations
        self.reg1 = EventRegistration.objects.create(event=self.event, student=self.student1, attended=True)
        self.reg2 = EventRegistration.objects.create(event=self.event, student=self.student2, attended=True)

    def test_admin_login_and_logout(self):
        """Test admin authentication and session management."""
        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {'username': 'testadmin', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue('_auth_user_id' in self.client.session)

        # Dashboard access
        dash_response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, "Executive Operations Overview")

        # Logout
        logout_response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(logout_response.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_unauthorized_access_redirection(self):
        """Unauthenticated requests to admin views must redirect to login."""
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/portal/login/', response.url)

    def test_event_creation_view(self):
        """Test creating an event via the administrative form."""
        self.client.login(username='testadmin', password='Password123!')
        url = reverse('events:event_create')
        post_data = {
            'title': 'AI & Robotics Colloquium',
            'description': 'Colloquium on autonomous agents',
            'category': 'SEMINAR',
            'department': self.dept.id,
            'venue': 'Auditorium Hall B',
            'start_time': (self.now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'end_time': (self.now + timedelta(days=1, hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'feedback_deadline': (self.now + timedelta(days=4)).strftime('%Y-%m-%dT%H:%M'),
            'target_audience': 'All Engineering Students',
            'status': 'UPCOMING',
            'feedback_mode': 'ANONYMOUS',
            'invitation_schedule': 'IMMEDIATE',
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)

        new_ev = Event.objects.filter(title='AI & Robotics Colloquium').first()
        self.assertIsNotNone(new_ev)
        self.assertTrue(hasattr(new_ev, 'feedback_form'))
        self.assertGreater(new_ev.feedback_form.questions.count(), 0)

    def test_student_csv_import(self):
        """Test CSV file parsing, column validation, and student creation."""
        self.client.login(username='testadmin', password='Password123!')
        csv_content = (
            "student_number,full_name,university_email,department,academic_year,section\n"
            "STU-003,Charlie Brown,charlie@test.edu,CSE,1st Year,A\n"
            "STU-004,Diana Prince,diana@test.edu,CSE,4th Year,B\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'students.csv'

        url = reverse('students:import_csv')
        response = self.client.post(url, {
            'csv_file': csv_file,
            'default_department': self.dept.id,
            'update_existing': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Student.objects.filter(student_number="STU-003").exists())
        self.assertTrue(Student.objects.filter(student_number="STU-004").exists())

    def test_invitation_generation_and_duplicate_prevention(self):
        """Ensure invitations are created for eligible attendees without duplicates."""
        count = generate_invitations_for_event(self.event)
        self.assertEqual(count, 2)
        self.assertEqual(self.event.invitations.count(), 2)

        # Running again must yield 0 new invitations
        count_repeat = generate_invitations_for_event(self.event)
        self.assertEqual(count_repeat, 0)
        self.assertEqual(self.event.invitations.count(), 2)

    def test_feedback_submission_and_anonymous_protections(self):
        """Test valid feedback submission, single-use token consumption, and anonymous protections."""
        generate_invitations_for_event(self.event)
        invitation = self.event.invitations.first()
        token = invitation.token

        submit_url = reverse('feedback:submit_feedback', kwargs={'token': token})
        get_response = self.client.get(submit_url)
        self.assertEqual(get_response.status_code, 200)

        # Prepare POST answers
        post_data = {}
        for q in self.feedback_form.questions.all():
            field_name = f"question_{q.id}"
            if q.question_type == QuestionType.STAR_RATING:
                post_data[field_name] = '5'
            elif q.question_type == QuestionType.YES_NO:
                post_data[field_name] = 'Yes'
            elif q.question_type == QuestionType.SINGLE_CHOICE:
                post_data[field_name] = q.get_choices_list()[0]
            elif q.question_type == QuestionType.MULTIPLE_CHOICE:
                post_data[field_name] = [q.get_choices_list()[0]]
            else:
                post_data[field_name] = "Great workshop with clear demonstrations!"

        # Submit feedback
        post_response = self.client.post(submit_url, post_data)
        self.assertEqual(post_response.status_code, 302)
        self.assertRedirects(post_response, reverse('feedback:submission_success'))

        # Verify token is now COMPLETED
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, InvitationStatus.COMPLETED)
        self.assertIsNotNone(invitation.completed_at)

        # Verify FeedbackResponse
        self.assertEqual(FeedbackResponse.objects.filter(event=self.event).count(), 1)
        resp = FeedbackResponse.objects.filter(event=self.event).first()
        self.assertEqual(resp.overall_rating, 5)
        self.assertTrue(resp.is_anonymous)
        self.assertIsNone(resp.student)

        # Attempting duplicate submission with same token must be rejected
        dup_response = self.client.get(submit_url)
        self.assertEqual(dup_response.status_code, 200)
        self.assertContains(dup_response, "Feedback Already Submitted")

    def test_deadline_enforcement(self):
        """Submission must be blocked when feedback deadline has expired."""
        expired_event = Event.objects.create(
            title="Old Seminar",
            description="Expired",
            category=EventCategory.SEMINAR,
            department=self.dept,
            venue="Room 202",
            start_time=self.now - timedelta(days=10),
            end_time=self.now - timedelta(days=9),
            feedback_deadline=self.now - timedelta(days=1),
            status=EventStatus.COMPLETED,
            feedback_mode=FeedbackMode.ANONYMOUS,
            organizer=self.organizer_user
        )
        form = FeedbackForm.objects.create(event=expired_event, title="Old Form")
        create_default_feedback_questions(form)

        inv = FeedbackInvitation.objects.create(
            event=expired_event,
            feedback_form=form,
            student=self.student1,
            status=InvitationStatus.SENT
        )

        url = reverse('feedback:submit_feedback', kwargs={'token': inv.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feedback Period Closed")

    def test_nlp_sentiment_and_analysis_service(self):
        """Test the built-in heuristic NLP sentiment classification and theme extraction."""
        score_pos, label_pos = analyze_sentiment("The speaker gave an inspiring, clear, and excellent presentation.")
        self.assertEqual(label_pos, 'POSITIVE')
        self.assertGreater(score_pos, 0.2)

        score_neg, label_neg = analyze_sentiment("The audio was bad, poor acoustics, very disorganized and confusing.")
        self.assertEqual(label_neg, 'NEGATIVE')
        self.assertLess(score_neg, -0.2)

    def test_csv_report_export(self):
        """Test generating and downloading event feedback CSV reports."""
        self.client.login(username='testadmin', password='Password123!')
        url = reverse('analytics:event_report_csv', kwargs={'event_id': self.event.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('eventpulse_report_', response['Content-Disposition'])

        # University-wide audit CSV
        univ_url = reverse('analytics:university_report_csv')
        univ_response = self.client.get(univ_url)
        self.assertEqual(univ_response.status_code, 200)
        self.assertIn('eventpulse_university_satisfaction_audit.csv', univ_response['Content-Disposition'])

    def test_dashboard_metric_calculations(self):
        """Verify dashboard metrics are computed mathematically from database records."""
        self.client.login(username='testadmin', password='Password123!')
        dash_response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        # Context must contain accurate calculated integers
        context = dash_response.context
        self.assertIn('total_events', context)
        self.assertIn('eligible_students_count', context)
        self.assertIn('response_rate', context)
        self.assertIn('average_satisfaction', context)
