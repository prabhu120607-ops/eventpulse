from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, UserRole


class Command(BaseCommand):
    help = "Creates or updates an initial EventPulse Super Administrator safely without hardcoding passwords."

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help="Administrator username")
        parser.add_argument('--email', type=str, default='admin@eventpulse.univ.edu', help="Administrator email")
        parser.add_argument('--password', type=str, required=True, help="Administrator secure password")

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserRole.SUPER_ADMIN
        profile.title = "Institutional Administrator"
        profile.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Successfully created Super Administrator '{username}' ({email})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated existing user '{username}' to Super Administrator."))
