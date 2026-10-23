from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short department code, e.g. CSE, EEE, MBA")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Administrator'
    UNIV_ADMIN = 'UNIV_ADMIN', 'University Administrator'
    DEPT_ADMIN = 'DEPT_ADMIN', 'Department Administrator'
    ORGANIZER = 'ORGANIZER', 'Event Organizer'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ORGANIZER)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    title = models.CharField(max_length=120, blank=True, help_text="e.g. Professor, Club Lead, Coordinator")
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self):
        return self.user.is_superuser or self.role == UserRole.SUPER_ADMIN

    @property
    def is_univ_admin(self):
        return self.is_super_admin or self.role == UserRole.UNIV_ADMIN

    @property
    def is_dept_admin(self):
        return self.is_univ_admin or self.role == UserRole.DEPT_ADMIN

    @property
    def is_organizer(self):
        return True  # all higher roles have organizer capabilities


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=120)
    details = models.TextField(blank=True)
    ip_address = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} - {self.action}"


class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Critical Alert'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications', help_text="Leave empty for broadcast to all admins")
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.level})"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        role = UserRole.SUPER_ADMIN if instance.is_superuser else UserRole.ORGANIZER
        UserProfile.objects.create(user=instance, role=role)
    else:
        if hasattr(instance, 'profile'):
            if instance.is_superuser and instance.profile.role != UserRole.SUPER_ADMIN:
                instance.profile.role = UserRole.SUPER_ADMIN
                instance.profile.save()
        else:
            UserProfile.objects.create(user=instance, role=UserRole.SUPER_ADMIN if instance.is_superuser else UserRole.ORGANIZER)
