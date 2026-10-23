import secrets
import hashlib
from django.db import models
from django.utils import timezone
from events.models import Event, FeedbackMode
from students.models import Student


class QuestionType(models.TextChoices):
    STAR_RATING = 'STAR_RATING', 'Star Rating (1 - 5 Stars)'
    MULTIPLE_CHOICE = 'MULTIPLE_CHOICE', 'Multiple Choice (Checkboxes)'
    SINGLE_CHOICE = 'SINGLE_CHOICE', 'Single Choice (Radio Buttons)'
    SHORT_TEXT = 'SHORT_TEXT', 'Short Text (Single Line)'
    LONG_TEXT = 'LONG_TEXT', 'Long Text (Detailed Feedback / Suggestions)'
    YES_NO = 'YES_NO', 'Yes / No'


class FeedbackForm(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='feedback_form')
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback Form: {self.title}"

    @property
    def is_anonymous(self):
        return self.event.feedback_mode == FeedbackMode.ANONYMOUS


class FeedbackQuestion(models.Model):
    CATEGORY_TAG_CHOICES = [
        ('OVERALL', 'Overall Impression'),
        ('CONTENT', 'Content Quality'),
        ('SPEAKER', 'Speaker / Instructor Effectiveness'),
        ('ORGANIZATION', 'Organization & Management'),
        ('VENUE', 'Venue & Facilities'),
        ('TIME', 'Duration & Time Management'),
        ('SUGGESTIONS', 'Suggestions & Future Topics'),
    ]

    form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name='questions')
    question_text = models.CharField(max_length=350)
    question_type = models.CharField(max_length=30, choices=QuestionType.choices, default=QuestionType.STAR_RATING)
    choices_raw = models.TextField(
        blank=True,
        help_text="For Multiple Choice or Single Choice: enter each option on a new line"
    )
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=1)
    category_tag = models.CharField(max_length=30, choices=CATEGORY_TAG_CHOICES, default='OVERALL')

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"

    def get_choices_list(self):
        """Returns non-empty split choices for choice questions."""
        if not self.choices_raw:
            return []
        return [choice.strip() for choice in self.choices_raw.splitlines() if choice.strip()]


class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Dispatch'
    SENT = 'SENT', 'Sent'
    FAILED = 'FAILED', 'Delivery Failed'
    COMPLETED = 'COMPLETED', 'Feedback Submitted'
    EXPIRED = 'EXPIRED', 'Expired'


def generate_secure_invitation_token():
    return secrets.token_urlsafe(32)


class FeedbackInvitation(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='invitations')
    feedback_form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name='invitations')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='feedback_invitations')
    token = models.CharField(max_length=64, unique=True, default=generate_secure_invitation_token, db_index=True)
    token_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    delivery_error = models.TextField(blank=True)

    class Meta:
        unique_together = ('event', 'student')
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite for {self.student.full_name} ({self.event.title})"

    def save(self, *args, **kwargs):
        if self.token and not self.token_hash:
            self.token_hash = hashlib.sha256(self.token.encode('utf-8')).hexdigest()
        if not self.expires_at:
            if self.event.feedback_deadline:
                self.expires_at = self.event.feedback_deadline
            else:
                self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at or (self.event.feedback_deadline and timezone.now() > self.event.feedback_deadline)

    @property
    def is_usable(self):
        return self.status in [InvitationStatus.SENT, InvitationStatus.PENDING] and not self.is_expired


class FeedbackResponse(models.Model):
    """
    Stores individual submitted feedback responses.
    Notice: If event.feedback_mode == ANONYMOUS, student is strictly NULL,
    ensuring anonymous reviews cannot be traced back in the database!
    """
    SENTIMENT_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEUTRAL', 'Neutral'),
        ('NEGATIVE', 'Negative'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='responses')
    feedback_form = models.ForeignKey(FeedbackForm, on_delete=models.CASCADE, related_name='responses')

    # Nullable student field: Populated ONLY when feedback mode is IDENTIFIED
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='identified_responses')
    is_anonymous = models.BooleanField(default=True)

    overall_rating = models.PositiveSmallIntegerField(default=5, help_text="Cached overall rating (1 to 5 stars)")
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='NEUTRAL')
    sentiment_score = models.FloatField(default=0.0)

    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        mode = "Anonymous" if self.is_anonymous else (self.student.full_name if self.student else "Identified")
        return f"Response ({mode}) for {self.event.title} - {self.overall_rating} Stars"


class FeedbackAnswer(models.Model):
    response = models.ForeignKey(FeedbackResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(FeedbackQuestion, on_delete=models.CASCADE, related_name='answers')
    rating_value = models.PositiveSmallIntegerField(null=True, blank=True)
    text_value = models.TextField(blank=True)
    selected_choices = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Answer to {self.question.question_text[:30]}: {self.display_value()}"

    def display_value(self):
        if self.rating_value is not None:
            return f"{self.rating_value} Stars"
        if self.selected_choices:
            return ", ".join(self.selected_choices)
        if self.text_value:
            return self.text_value
        return "N/A"


class EmailDeliveryAttempt(models.Model):
    ATTEMPT_CHOICES = [
        ('INVITATION', 'Initial Feedback Invitation'),
        ('REMINDER', 'Feedback Reminder'),
        ('TEST', 'Manual Test Email'),
    ]
    STATUS_CHOICES = [
        ('SUCCESS', 'Delivered Successfully'),
        ('FAILED', 'Delivery Failed'),
    ]

    invitation = models.ForeignKey(FeedbackInvitation, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_attempts')
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=250)
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_CHOICES, default='INVITATION')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.attempt_type} to {self.recipient_email} at {self.created_at:%Y-%m-%d %H:%M}"
