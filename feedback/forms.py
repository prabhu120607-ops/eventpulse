from django import forms
from .models import FeedbackQuestion, QuestionType, FeedbackForm


class FeedbackQuestionForm(forms.ModelForm):
    class Meta:
        model = FeedbackQuestion
        fields = ['question_text', 'question_type', 'choices_raw', 'is_required', 'category_tag', 'order']
        widgets = {
            'question_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter question prompt...'}),
            'question_type': forms.Select(attrs={'class': 'form-select'}),
            'choices_raw': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'One option per line (for choice questions)'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'category_tag': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class DynamicStudentFeedbackForm(forms.Form):
    """
    Dynamically generates form fields based on the FeedbackQuestions attached to a FeedbackForm.
    Performs server-side validation on every submission.
    """
    def __init__(self, *args, **kwargs):
        feedback_form = kwargs.pop('feedback_form')
        super().__init__(*args, **kwargs)

        for q in feedback_form.questions.all():
            field_name = f"question_{q.id}"
            label = q.question_text
            required = q.is_required

            if q.question_type == QuestionType.STAR_RATING:
                self.fields[field_name] = forms.ChoiceField(
                    label=label,
                    choices=[(str(i), f"{i} Stars") for i in range(5, 0, -1)],
                    widget=forms.RadioSelect(attrs={'class': 'star-rating-radio'}),
                    required=required,
                    initial='5'
                )
            elif q.question_type == QuestionType.YES_NO:
                self.fields[field_name] = forms.ChoiceField(
                    label=label,
                    choices=[('Yes', 'Yes'), ('No', 'No')],
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                    required=required
                )
            elif q.question_type == QuestionType.SINGLE_CHOICE:
                choices_list = [(c, c) for c in q.get_choices_list()]
                self.fields[field_name] = forms.ChoiceField(
                    label=label,
                    choices=choices_list,
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                    required=required
                )
            elif q.question_type == QuestionType.MULTIPLE_CHOICE:
                choices_list = [(c, c) for c in q.get_choices_list()]
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=label,
                    choices=choices_list,
                    widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                    required=required
                )
            elif q.question_type == QuestionType.SHORT_TEXT:
                self.fields[field_name] = forms.CharField(
                    label=label,
                    widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your response...'}),
                    required=required
                )
            elif q.question_type == QuestionType.LONG_TEXT:
                self.fields[field_name] = forms.CharField(
                    label=label,
                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your constructive thoughts...'}),
                    required=required
                )
