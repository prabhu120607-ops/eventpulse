from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import Department
from students.models import Student


class EventCategory(models.TextChoices):
    SEMINAR = 'SEMINAR', 'Seminar'
    WORKSHOP = 'WORKSHOP', 'Workshop'
    HACKATHON = 'HACKATHON', 'Hackathon'
    TECH_FEST = 'TECH_FEST', 'Technical Festival'
    CULTURAL = 'CULTURAL', 'Cultural Event'
    GUEST_LECTURE = 'GUEST_LECTURE', 'Guest Lecture'
    SPORTS = 'SPORTS', 'Sports Event'
    OTHER = 'OTHER', 'Other'


class EventStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    UPCOMING = 'UPCOMING', 'Upcoming'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    ARCHIVED = 'ARCHIVED', 'Archived'


class FeedbackMode(models.TextChoices):
    ANONYMOUS = 'ANONYMOUS', 'Anonymous Feedback (Guaranteed Privacy)'
    IDENTIFIED = 'IDENTIFIED', 'Identified Feedback (Name/Student ID visible to admins)'


class InvitationSchedule(models.TextChoices):
    IMMEDIATE = 'IMMEDIATE', 'Immediately after event concludes'
    AFTER_1_HOUR = 'AFTER_1_HOUR', '1 Hour after event concludes'
    AFTER_6_HOURS = 'AFTER_6_HOURS', '6 Hours after event concludes'
    AFTER_24_HOURS = 'AFTER_24_HOURS', '24 Hours after event concludes'
    MANUAL = 'MANUAL', 'Manual trigger only by Organizer'


class Event(models.Model):
    title = models.CharField(max_length=220)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=EventCategory.choices, default=EventCategory.SEMINAR)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='events', help_text="Department hosting this event (or empty for University-wide)")
    venue = models.CharField(max_length=180, help_text="e.g. Auditorium Hall A, Virtual / Zoom, Lab 3")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='organized_events')
    co_organizers = models.ManyToManyField(User, blank=True, related_name='co_organized_events')
    target_audience = models.CharField(max_length=150, blank=True, default="All Students", help_text="e.g. 3rd Year CSE, Open to All")

    status = models.CharField(max_length=20, choices=EventStatus.choices, default=EventStatus.UPCOMING)

    # Feedback settings
    feedback_mode = models.CharField(max_length=20, choices=FeedbackMode.choices, default=FeedbackMode.ANONYMOUS)
    invitation_schedule = models.CharField(max_length=20, choices=InvitationSchedule.choices, default=InvitationSchedule.IMMEDIATE)
    feedback_deadline = models.DateTimeField(null=True, blank=True, help_text="Date & time after which feedback forms close")
    invitations_paused = models.BooleanField(default=False, help_text="Allow organizer to pause automated emails")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.title} ({self.start_time:%b %d, %Y})"

    @property
    def is_finished(self):
        return timezone.now() >= self.end_time or self.status == EventStatus.COMPLETED

    @property
    def is_feedback_open(self):
        if self.feedback_deadline and timezone.now() > self.feedback_deadline:
            return False
        return self.status in [EventStatus.COMPLETED, EventStatus.IN_PROGRESS, EventStatus.PUBLISHED]

    def update_dynamic_status(self):
        """Auto-computes dynamic status according to current time if status is UPCOMING or IN_PROGRESS."""
        now = timezone.now()
        if self.status in [EventStatus.UPCOMING, EventStatus.IN_PROGRESS, EventStatus.PUBLISHED]:
            if now < self.start_time:
                self.status = EventStatus.UPCOMING
            elif self.start_time <= now <= self.end_time:
                self.status = EventStatus.IN_PROGRESS
            elif now > self.end_time:
                self.status = EventStatus.COMPLETED
            self.save(update_fields=['status'])


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='event_registrations')
    registered_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=True, help_text="Mark if student actually attended (eligible for feedback)")

    class Meta:
        unique_together = ('event', 'student')
        ordering = ['student__full_name']

    def __str__(self):
        return f"{self.student.full_name} -> {self.event.title}"


class ManagementAction(models.Model):
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='actions')
    title = models.CharField(max_length=200)
    description = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_actions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
