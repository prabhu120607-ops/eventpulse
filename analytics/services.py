"""
EventPulse NLP Analytics & Feedback Sentiment Engine.
Performs sentiment classification, keyword theme extraction, complaint aggregation,
and executive summary generation without requiring any external paid API keys.
"""

import re
from collections import Counter
from django.utils import timezone
from django.db.models import Avg
from .models import AIAnalysisResult
from feedback.models import FeedbackResponse, FeedbackAnswer, FeedbackQuestion


POSITIVE_KEYWORDS = {
    'excellent', 'great', 'good', 'amazing', 'inspiring', 'engaging', 'clear',
    'helpful', 'informative', 'knowledgeable', 'practical', 'hands-on', 'interactive',
    'fantastic', 'organized', 'well', 'structured', 'relevant', 'enjoyed', 'loved',
    'valuable', 'insightful', 'brilliant', 'smooth', 'appreciate', 'thank'
}

NEGATIVE_KEYWORDS = {
    'poor', 'bad', 'disappointing', 'boring', 'unclear', 'confusing', 'rushed',
    'noisy', 'echo', 'audio', 'slow', 'waste', 'disorganized', 'short', 'crowded',
    'delayed', 'late', 'lag', 'technical', 'issue', 'problem', 'difficult',
    'seating', 'uncomfortable', 'monotone', 'irrelevant'
}

THEME_CATEGORIES = {
    'Speaker & Delivery': ['speaker', 'presenter', 'instructor', 'teaching', 'knowledge', 'clear', 'delivery', 'voice'],
    'Hands-on Practical Content': ['hands-on', 'practical', 'code', 'demo', 'exercise', 'lab', 'project', 'implementation'],
    'Venue & Environment': ['venue', 'hall', 'room', 'auditorium', 'seating', 'chair', 'air', 'ac', 'temperature', 'wifi'],
    'Audio, Video & Technology': ['audio', 'microphone', 'sound', 'speaker', 'projector', 'screen', 'slides', 'display', 'echo'],
    'Time Management & Pacing': ['time', 'duration', 'rushed', 'pacing', 'break', 'schedule', 'started', 'fast', 'slow'],
    'Organization & Hospitality': ['organization', 'coordination', 'registration', 'volunteers', 'food', 'refreshment', 'certificate'],
}


def analyze_sentiment(text):
    """
    Computes sentiment score (-1.0 to 1.0) and categorical label ('POSITIVE', 'NEUTRAL', 'NEGATIVE').
    """
    if not text:
        return 0.0, 'NEUTRAL'

    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    pos_count = sum(1 for w in words if w in POSITIVE_KEYWORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_KEYWORDS)

    total = pos_count + neg_count
    if total == 0:
        return 0.0, 'NEUTRAL'

    score = round((pos_count - neg_count) / total, 2)
    if score >= 0.2:
        return score, 'POSITIVE'
    elif score <= -0.2:
        return score, 'NEGATIVE'
    else:
        return score, 'NEUTRAL'


def run_ai_analysis_for_event(event):
    """
    Processes all feedback responses and answers for an event to build a comprehensive
    AIAnalysisResult record with positive themes, negative themes, complaints, suggestions,
    and an executive summary.
    """
    responses = event.responses.prefetch_related('answers', 'answers__question').all()
    total_reviews = responses.count()

    if total_reviews == 0:
        return None

    # Count sentiments
    pos_reviews = 0
    neu_reviews = 0
    neg_reviews = 0

    all_texts = []
    suggestion_texts = []
    praise_texts = []
    complaint_texts = []

    for resp in responses:
        # Check rating & text
        if resp.overall_rating >= 4:
            pos_reviews += 1
        elif resp.overall_rating <= 2:
            neg_reviews += 1
        else:
            neu_reviews += 1

        for ans in resp.answers.all():
            val = ans.text_value.strip()
            if val:
                all_texts.append(val)
                score, label = analyze_sentiment(val)
                if 'suggestion' in ans.question.question_text.lower() or ans.question.category_tag == 'SUGGESTIONS':
                    suggestion_texts.append(val)
                elif label == 'POSITIVE':
                    praise_texts.append(val)
                elif label == 'NEGATIVE':
                    complaint_texts.append(val)

    pos_pct = round((pos_reviews / total_reviews) * 100, 1)
    neu_pct = round((neu_reviews / total_reviews) * 100, 1)
    neg_pct = round((neg_reviews / total_reviews) * 100, 1)

    # Theme extraction
    positive_themes = []
    negative_themes = []
    full_corpus = " ".join(all_texts).lower()

    for theme_name, keywords in THEME_CATEGORIES.items():
        theme_matches = sum(full_corpus.count(kw) for kw in keywords)
        if theme_matches > 0:
            # Check polarity in praise vs complaint
            praise_hits = sum(" ".join(praise_texts).lower().count(kw) for kw in keywords)
            complaint_hits = sum(" ".join(complaint_texts).lower().count(kw) for kw in keywords)

            if praise_hits >= complaint_hits:
                positive_themes.append(f"{theme_name} ({theme_matches} mentions)")
            else:
                negative_themes.append(f"{theme_name} ({theme_matches} mentions)")

    # Key suggestions
    key_suggestions = [s[:120] for s in suggestion_texts[:6]]

    # Common complaints
    common_complaints = [c[:120] for c in complaint_texts[:5]]

    # Overall label
    if pos_pct >= 60:
        overall_label = 'Highly Positive'
    elif pos_pct >= 40 and neg_pct < 30:
        overall_label = 'Generally Favorable'
    elif neg_pct >= 40:
        overall_label = 'Requires Attention'
    else:
        overall_label = 'Mixed / Neutral'

    # Generate executive summary paragraph
    avg_stars = event.responses.aggregate(avg=Avg('overall_rating'))['avg'] or 5.0
    summary_parts = [
        f"Based on {total_reviews} verified student evaluation(s), {event.title} achieved an overall satisfaction rating of {avg_stars:.1f}/5.0 ({pos_pct}% positive ratings)."
    ]

    if positive_themes:
        summary_parts.append(f"Key student praises centered around {', '.join(positive_themes[:3])}.")

    if negative_themes or common_complaints:
        complaint_mention = f"Areas flagged for operational improvement include {', '.join(negative_themes[:2])}." if negative_themes else ""
        summary_parts.append(complaint_mention)

    if key_suggestions:
        summary_parts.append(f"Primary student recommendation: \"{key_suggestions[0]}\".")

    executive_summary = " ".join([p for p in summary_parts if p])

    analysis, _ = AIAnalysisResult.objects.update_or_create(
        event=event,
        defaults={
            'total_reviews_analyzed': total_reviews,
            'positive_percentage': pos_pct,
            'neutral_percentage': neu_pct,
            'negative_percentage': neg_pct,
            'positive_themes': positive_themes[:5],
            'negative_themes': negative_themes[:5],
            'common_complaints': common_complaints[:5],
            'key_suggestions': key_suggestions[:5],
            'executive_summary': executive_summary,
            'sentiment_label': overall_label,
            'is_ai_generated': True,
        }
    )
    return analysis
