from .models import Notification

def user_role_context(request):
    """
    Context processor to inject current user profile, role flags,
    and unread notification counts into every template context.
    """
    context = {
        'current_profile': None,
        'is_super_admin': False,
        'is_univ_admin': False,
        'is_dept_admin': False,
        'is_organizer': False,
        'unread_notifications_count': 0,
        'recent_notifications': [],
    }

    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        context['current_profile'] = profile
        if profile:
            context['is_super_admin'] = profile.is_super_admin
            context['is_univ_admin'] = profile.is_univ_admin
            context['is_dept_admin'] = profile.is_dept_admin
            context['is_organizer'] = profile.is_organizer
        elif request.user.is_superuser:
            context['is_super_admin'] = True
            context['is_univ_admin'] = True
            context['is_dept_admin'] = True
            context['is_organizer'] = True

        # Unread notifications for this user or broadcast
        notifications = Notification.objects.filter(
            models_q_filter(request.user)
        )[:5]
        context['recent_notifications'] = notifications
        context['unread_notifications_count'] = Notification.objects.filter(
            models_q_filter(request.user), is_read=False
        ).count()

    return context


def models_q_filter(user):
    from django.db.models import Q
    return Q(user=user) | Q(user__isnull=True)
