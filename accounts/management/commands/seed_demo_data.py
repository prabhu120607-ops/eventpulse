from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

from accounts.models import Department, UserProfile, UserRole
from students.models import Student, EnrollmentStatus
from events.models import Event, EventCategory, EventStatus, FeedbackMode, InvitationSchedule, EventRegistration
from feedback.models import (
    FeedbackForm, FeedbackQuestion, QuestionType, FeedbackInvitation,
    InvitationStatus, FeedbackResponse, FeedbackAnswer
)
from events.views import create_default_feedback_questions
from feedback.services import generate_invitations_for_event
from analytics.services import run_ai_analysis_for_event


class Command(BaseCommand):
    help = "Seeds comprehensive, realistic demonstration records for EventPulse (Departments, Users, Events, Students, Responses, NLP Analytics)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding EventPulse database...")

        # 1. Departments
        depts_data = [
            ('Computer Science & Engineering', 'CSE', 'Software engineering, artificial intelligence, and computing.'),
            ('Electrical & Electronics Engineering', 'EEE', 'Circuits, robotics, power systems, and embedded computing.'),
            ('School of Business Management', 'MBA', 'Leadership, operations management, and entrepreneurship.'),
            ('Mechanical Engineering', 'MECH', 'Thermal systems, robotics, and advanced manufacturing.'),
        ]

        departments = []
        for name, code, desc in depts_data:
            dept, _ = Department.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': desc}
            )
            departments.append(dept)

        # 2. Staff Accounts
        staff_data = [
            ('admin', 'admin@eventpulse.univ.edu', 'AdminUser@2026', UserRole.SUPER_ADMIN, None, 'Institutional Admin'),
            ('univ_dean', 'dean.academics@univ.edu', 'DeanPass@2026', UserRole.UNIV_ADMIN, None, 'Dean of Academic Affairs'),
            ('prof_alan', 'alan.turing@univ.edu', 'ProfPass@2026', UserRole.DEPT_ADMIN, departments[0], 'Head of Computer Science'),
            ('organizer_jane', 'jane.coord@univ.edu', 'CoordPass@2026', UserRole.ORGANIZER, departments[0], 'Technical Club Coordinator'),
        ]

        created_users = {}
        for username, email, pwd, role, dept, title in staff_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'is_staff': True, 'first_name': username.capitalize()}
            )
            user.set_password(pwd)
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.department = dept
            profile.title = title
            profile.save()
            created_users[username] = user

        # 3. Students
        students_data = [
            ('STU-2024-101', 'Aarav Sharma', 'aarav.sharma@univ.edu', departments[0], '3rd Year', 'A'),
            ('STU-2024-102', 'Priya Patel', 'priya.patel@univ.edu', departments[0], '3rd Year', 'A'),
            ('STU-2024-103', 'Liam O\'Connor', 'liam.oc@univ.edu', departments[1], '2nd Year', 'B'),
            ('STU-2024-104', 'Mei Ling Zhou', 'mei.ling@univ.edu', departments[0], '4th Year', 'A'),
            ('STU-2024-105', 'Carlos Mendez', 'carlos.m@univ.edu', departments[2], 'Postgraduate', '1'),
            ('STU-2024-106', 'Fatima Al-Sayed', 'fatima.as@univ.edu', departments[1], '3rd Year', 'C'),
            ('STU-2024-107', 'Kavita Nair', 'kavita.n@univ.edu', departments[0], '2nd Year', 'B'),
            ('STU-2024-108', 'David Kim', 'david.kim@univ.edu', departments[3], '4th Year', 'A'),
            ('STU-2024-109', 'Ananya Gupta', 'ananya.g@univ.edu', departments[2], '1st Year', 'A'),
            ('STU-2024-110', 'Zachary Taylor', 'zachary.t@univ.edu', departments[3], '2nd Year', 'B'),
        ]

        students = []
        for s_num, name, email, dept, year, sec in students_data:
            stu, _ = Student.objects.get_or_create(
                student_number=s_num,
                defaults={
                    'full_name': name,
                    'university_email': email,
                    'department': dept,
                    'academic_year': year,
                    'section': sec,
                    'enrollment_status': EnrollmentStatus.ACTIVE
                }
            )
            students.append(stu)

        # 4. Events
        now = timezone.now()

        # Event 1: Completed Workshop with high response rate
        ev1, _ = Event.objects.get_or_create(
            title="Cloud Architecture & Microservices Bootcamp",
            defaults={
                'description': "Comprehensive hands-on workshop covering Docker containers, Kubernetes deployment, and scalable cloud APIs.",
                'category': EventCategory.WORKSHOP,
                'department': departments[0],
                'venue': "Advanced Software Engineering Lab 3",
                'start_time': now - timedelta(days=3, hours=5),
                'end_time': now - timedelta(days=3, hours=1),
                'feedback_deadline': now + timedelta(days=4),
                'status': EventStatus.COMPLETED,
                'feedback_mode': FeedbackMode.ANONYMOUS,
                'invitation_schedule': InvitationSchedule.IMMEDIATE,
                'organizer': created_users['organizer_jane'],
            }
        )

        # Event 2: Completed Guest Lecture
        ev2, _ = Event.objects.get_or_create(
            title="Executive Leadership in Deep Tech & AI Ventures",
            defaults={
                'description': "Distinguished lecture with industry venture capitalists exploring startup formation, patenting, and ethical AI governance.",
                'category': EventCategory.GUEST_LECTURE,
                'department': departments[2],
                'venue': "University Main Auditorium",
                'start_time': now - timedelta(days=5, hours=3),
                'end_time': now - timedelta(days=5, hours=1),
                'feedback_deadline': now - timedelta(days=1),
                'status': EventStatus.COMPLETED,
                'feedback_mode': FeedbackMode.IDENTIFIED,
                'invitation_schedule': InvitationSchedule.IMMEDIATE,
                'organizer': created_users['univ_dean'],
            }
        )

        # Event 3: Upcoming Hackathon
        ev3, _ = Event.objects.get_or_create(
            title="Campus Innovation 36-Hour Hackathon 2026",
            defaults={
                'description': "Annual inter-collegiate flagship hackathon focused on sustainable energy, health-tech, and intelligent robotics.",
                'category': EventCategory.HACKATHON,
                'department': departments[0],
                'venue': "Innovation Complex & Student Hub",
                'start_time': now + timedelta(days=4, hours=9),
                'end_time': now + timedelta(days=5, hours=21),
                'feedback_deadline': now + timedelta(days=10),
                'status': EventStatus.UPCOMING,
                'feedback_mode': FeedbackMode.ANONYMOUS,
                'invitation_schedule': InvitationSchedule.IMMEDIATE,
                'organizer': created_users['prof_alan'],
            }
        )

        # Event 4: Upcoming Seminar
        ev4, _ = Event.objects.get_or_create(
            title="Renewable Energy Integration in Smart Grids",
            defaults={
                'description': "Technical seminar discussing solar forecasting algorithms and high-voltage grid stability.",
                'category': EventCategory.SEMINAR,
                'department': departments[1],
                'venue': "Faraday Hall 102",
                'start_time': now + timedelta(days=7, hours=14),
                'end_time': now + timedelta(days=7, hours=16),
                'feedback_deadline': now + timedelta(days=12),
                'status': EventStatus.UPCOMING,
                'feedback_mode': FeedbackMode.ANONYMOUS,
                'invitation_schedule': InvitationSchedule.IMMEDIATE,
                'organizer': created_users['organizer_jane'],
            }
        )

        # 5. Build Feedback Forms for each event
        for ev in [ev1, ev2, ev3, ev4]:
            form, created = FeedbackForm.objects.get_or_create(
                event=ev,
                defaults={
                    'title': f"Feedback: {ev.title}",
                    'description': f"Please provide your candid evaluation for {ev.title}."
                }
            )
            if created or form.questions.count() == 0:
                create_default_feedback_questions(form)

        # 6. Enroll Students & Generate Invitations
        for ev, stu_subset in [(ev1, students[:8]), (ev2, students[2:9]), (ev3, students)]:
            for stu in stu_subset:
                EventRegistration.objects.get_or_create(
                    event=ev,
                    student=stu,
                    defaults={'attended': True}
                )
            generate_invitations_for_event(ev)

        # 7. Seed completed responses for Event 1 (Workshop)
        sample_responses_ev1 = [
            {
                'overall': 5,
                'content': 5,
                'speaker': 5,
                'org': 5,
                'venue': 4,
                'time': 'Just Right - Well balanced',
                'praise': 'The hands-on Docker and Kubernetes deployment labs were clear, practical and exceptionally well guided!',
                'suggestion': 'Please offer an advanced follow-up lab session with production CI/CD pipelines.',
                'rec': 'Yes'
            },
            {
                'overall': 5,
                'content': 4,
                'speaker': 5,
                'org': 4,
                'venue': 5,
                'time': 'Just Right - Well balanced',
                'praise': 'Instructor had profound domain knowledge and answered real-world debugging questions smoothly.',
                'suggestion': 'Provide the sample GitHub repository code snippets 24 hours prior to the session.',
                'rec': 'Yes'
            },
            {
                'overall': 4,
                'content': 4,
                'speaker': 4,
                'org': 4,
                'venue': 3,
                'time': 'Too Short - Needed more time',
                'praise': 'Great practical demonstrations and active live troubleshooting.',
                'suggestion': 'WiFi in Lab 3 had intermittent drops during container pulls; ensure dedicated bandwidth next time.',
                'rec': 'Yes'
            },
            {
                'overall': 5,
                'content': 5,
                'speaker': 5,
                'org': 5,
                'venue': 4,
                'time': 'Just Right - Well balanced',
                'praise': 'One of the best technical workshops on campus this semester. Extremely relevant for job interviews.',
                'suggestion': 'Extend the session by 30 minutes for a dedicated architectural Q&A.',
                'rec': 'Yes'
            },
            {
                'overall': 4,
                'content': 4,
                'speaker': 5,
                'org': 4,
                'venue': 4,
                'time': 'Just Right - Well balanced',
                'praise': 'Clear explanations of microservice architecture and container orchestration.',
                'suggestion': 'More time for hands-on exercises.',
                'rec': 'Yes'
            },
            {
                'overall': 3,
                'content': 3,
                'speaker': 4,
                'org': 3,
                'venue': 3,
                'time': 'Too Short - Needed more time',
                'praise': 'Good presentation slides.',
                'suggestion': 'Pacing felt slightly rushed towards the end of the Kubernetes section.',
                'rec': 'Yes'
            }
        ]

        invitations_ev1 = list(ev1.invitations.all())
        form_ev1 = ev1.feedback_form
        questions_ev1 = list(form_ev1.questions.all().order_by('order'))

        for idx, resp_data in enumerate(sample_responses_ev1):
            if idx < len(invitations_ev1):
                inv = invitations_ev1[idx]
                inv.status = InvitationStatus.COMPLETED
                inv.completed_at = now - timedelta(days=2, hours=random.randint(1, 12))
                inv.sent_at = now - timedelta(days=3)
                inv.save()

                resp_obj = FeedbackResponse.objects.create(
                    event=ev1,
                    feedback_form=form_ev1,
                    student=None,  # Anonymous!
                    is_anonymous=True,
                    overall_rating=resp_data['overall'],
                    sentiment='POSITIVE' if resp_data['overall'] >= 4 else 'NEUTRAL',
                    submitted_at=inv.completed_at
                )

                # Answers map
                ans_values = [
                    resp_data['overall'],
                    resp_data['content'],
                    resp_data['speaker'],
                    resp_data['org'],
                    resp_data['venue'],
                    resp_data['time'],
                    resp_data['praise'],
                    resp_data['suggestion'],
                    resp_data['rec']
                ]

                for q_idx, q in enumerate(questions_ev1):
                    if q_idx < len(ans_values):
                        val = ans_values[q_idx]
                        if isinstance(val, int):
                            FeedbackAnswer.objects.create(response=resp_obj, question=q, rating_value=val)
                        else:
                            FeedbackAnswer.objects.create(response=resp_obj, question=q, text_value=str(val))

        # Seed completed responses for Event 2 (Identified)
        invitations_ev2 = list(ev2.invitations.all())
        form_ev2 = ev2.feedback_form
        questions_ev2 = list(form_ev2.questions.all().order_by('order'))

        sample_responses_ev2 = [
            {'overall': 5, 'praise': 'Remarkable insights into deep tech startups and fundraising.', 'sug': 'Invite more entrepreneurs for a panel.'},
            {'overall': 4, 'praise': 'Inspiring talk with realistic venture data.', 'sug': 'Microphone audio had a slight echo in the back rows.'},
            {'overall': 5, 'praise': 'Clear roadmap for student founders.', 'sug': 'Host an informal networking dinner after the talk.'},
        ]

        for idx, resp_data in enumerate(sample_responses_ev2):
            if idx < len(invitations_ev2):
                inv = invitations_ev2[idx]
                inv.status = InvitationStatus.COMPLETED
                inv.completed_at = now - timedelta(days=4)
                inv.sent_at = now - timedelta(days=5)
                inv.save()

                resp_obj = FeedbackResponse.objects.create(
                    event=ev2,
                    feedback_form=form_ev2,
                    student=inv.student,  # Identified!
                    is_anonymous=False,
                    overall_rating=resp_data['overall'],
                    sentiment='POSITIVE',
                    submitted_at=inv.completed_at
                )

                for q in questions_ev2:
                    if q.question_type == QuestionType.STAR_RATING:
                        FeedbackAnswer.objects.create(response=resp_obj, question=q, rating_value=resp_data['overall'])
                    elif q.category_tag == 'SUGGESTIONS':
                        FeedbackAnswer.objects.create(response=resp_obj, question=q, text_value=resp_data['sug'])
                    else:
                        FeedbackAnswer.objects.create(response=resp_obj, question=q, text_value=resp_data['praise'])

        # 8. Run NLP Synthesis on completed events
        run_ai_analysis_for_event(ev1)
        run_ai_analysis_for_event(ev2)

        self.stdout.write(self.style.SUCCESS("EventPulse demo database seeded successfully!"))
        self.stdout.write(self.style.SUCCESS("Sample Accounts:"))
        self.stdout.write("  • Super Admin: admin / AdminUser@2026")
        self.stdout.write("  • University Dean: univ_dean / DeanPass@2026")
        self.stdout.write("  • Dept Admin: prof_alan / ProfPass@2026")
        self.stdout.write("  • Event Organizer: organizer_jane / CoordPass@2026")
