from communication.models import Notification
from .models import SystemPreference

def notification_count(request):
    """
    Context processor that makes the unread notification count and theme preference
    available to all templates.
    """
    if not request.user.is_authenticated:
        return {}
        
    # Count unread notifications for the current user
    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    # Get or create system preferences for the user
    system_prefs, created = SystemPreference.objects.get_or_create(
        landlord=request.user
    )
    
    return {
        'unread_notification_count': unread_count,
        'user_theme': system_prefs.dashboard_theme.lower() if system_prefs.dashboard_theme else 'light'
    }
