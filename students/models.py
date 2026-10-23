from django.db import models
from accounts.models import Department


class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'
    GRADUATED = 'GRADUATED', 'Graduated'


class Student(models.Model):
    student_number = models.CharField(max_length=50, unique=True, help_text="University Student ID / Roll Number")
    full_name = models.CharField(max_length=150)
    university_email = models.EmailField(unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    academic_year = models.CharField(max_length=50, default='1st Year', help_text="e.g. 1st Year, 2nd Year, 3rd Year, 4th Year, Post-Grad")
    section = models.CharField(max_length=20, blank=True, default='A')
    enrollment_status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_number']

    def __str__(self):
        return f"{self.full_name} ({self.student_number})"
