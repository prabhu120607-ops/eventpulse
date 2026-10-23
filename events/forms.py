from django import forms
from .models import Event, EventRegistration, ManagementAction, EventCategory, EventStatus, FeedbackMode, InvitationSchedule
from accounts.models import Department
from students.models import Student, EnrollmentStatus


class EventForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Event Start Date & Time"
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Event End Date & Time"
    )
    feedback_deadline = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Feedback Submission Deadline",
        help_text="Forms close automatically after this timestamp"
    )

    class Meta:
        model = Event
        fields = [
            'title', 'description', 'category', 'department', 'venue',
            'start_time', 'end_time', 'target_audience', 'status',
            'feedback_mode', 'invitation_schedule', 'feedback_deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Modern Full-Stack Web Development Workshop'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe event objectives, speakers, and target learning outcomes...'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Main Auditorium Hall A / Online via Zoom'}),
            'target_audience': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. All Undergraduates, 3rd Year CSE'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'feedback_mode': forms.Select(attrs={'class': 'form-select'}),
            'invitation_schedule': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        deadline = cleaned_data.get('feedback_deadline')

        if start and end and end <= start:
            self.add_error('end_time', "Event end time must be chronologically after the start time.")

        if end and deadline and deadline <= end:
            self.add_error('feedback_deadline', "Feedback deadline must be scheduled after the event concludes.")

        return cleaned_data


class ManagementActionForm(forms.ModelForm):
    class Meta:
        model = ManagementAction
        fields = ['title', 'description', 'assigned_to', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Action title...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Describe action plan...'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class StudentPublicRegistrationForm(forms.Form):
    student_number = forms.CharField(
        max_length=50,
        label="Student ID / Roll Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. STU-2024-042'})
    )
    full_name = forms.CharField(
        max_length=150,
        label="Full Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Alex Rivera'})
    )
    university_email = forms.EmailField(
        label="University Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. name@university.edu'}),
        help_text="Your unique feedback link will be sent to this email after the event concludes."
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label="Your Department",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    academic_year = forms.ChoiceField(
        choices=[
            ('1st Year', '1st Year'),
            ('2nd Year', '2nd Year'),
            ('3rd Year', '3rd Year'),
            ('4th Year', '4th Year'),
            ('Postgraduate', 'Postgraduate / Masters'),
            ('Faculty/Staff', 'Faculty / Staff'),
        ],
        initial='3rd Year',
        label="Academic Year",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
