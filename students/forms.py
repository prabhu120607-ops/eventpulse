from django import forms
from .models import Student
from accounts.models import Department


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Select CSV Roster File",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
        help_text="File must be formatted as CSV (.csv). Max size 5MB."
    )
    default_department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label="Default Department (if not specified in CSV)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=True,
        label="Update details if student ID already exists",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['student_number', 'full_name', 'university_email', 'department', 'academic_year', 'section', 'enrollment_status']
        widgets = {
            'student_number': forms.TextInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'university_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control'}),
            'enrollment_status': forms.Select(attrs={'class': 'form-select'}),
        }
