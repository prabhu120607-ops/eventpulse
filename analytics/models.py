from django.db import models
from events.models import Event


class AIAnalysisResult(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='ai_analysis')
    total_reviews_analyzed = models.PositiveIntegerField(default=0)
    positive_percentage = models.FloatField(default=0.0)
    neutral_percentage = models.FloatField(default=0.0)
    negative_percentage = models.FloatField(default=0.0)

    # Structured keywords and themes
    positive_themes = models.JSONField(default=list, blank=True)
    negative_themes = models.JSONField(default=list, blank=True)
    common_complaints = models.JSONField(default=list, blank=True)
    key_suggestions = models.JSONField(default=list, blank=True)

    executive_summary = models.TextField(blank=True)
    sentiment_label = models.CharField(max_length=50, default='Neutral')
    is_ai_generated = models.BooleanField(default=False)
    calculated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI Analysis: {self.event.title} ({self.sentiment_label})"
