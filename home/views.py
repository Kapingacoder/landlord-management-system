from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import send_mail, BadHeaderError, get_connection
from django.http import HttpResponse, JsonResponse
from django.db.models.query_utils import Q
from django.contrib.auth.forms import SetPasswordForm
from django.conf import settings
import os
import logging
from django.contrib.admin.views.decorators import staff_member_required

logger = logging.getLogger(__name__)

def index(request):
    """Render the homepage"""
    return render(request, 'home/index.html')

@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Handle user login.
    - GET: Display the login form.
    - POST: Authenticate user and redirect based on user type.
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Redirect based on user type
                if hasattr(user, 'user_type'):
                    if user.user_type == 'landlord':
                        # Corrected redirect to use the namespaced URL name
                        return redirect('landlord:dashboard')
                    elif user.user_type == 'tenant':
                        # Assuming you have a tenant dashboard
                        return redirect('tenancy:tenant_dashboard')
                
                # Default redirect if user_type is not set
                return redirect('home:index')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
        
    return render(request, 'home/login.html', {'form': form})

def logout_view(request):
    """Handle user logout and redirect to login page"""
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('home:login')

def forgot_password(request):
    """Handle password reset request"""
    if request.method == "POST":
        email = request.POST.get('email')
        User = get_user_model()
        
        # Check if user exists with this email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with that email address.')
            return redirect('home:forgot_password')
        
        # Generate password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Create reset link
        domain = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        reset_link = f"{protocol}://{domain}/reset-password/{uid}/{token}/"
        
        # Email subject and message
        subject = "Password Reset Request"
        message = render_to_string('home/password_reset_email.html', {
            'user': user,
            'reset_link': reset_link,
            'domain': domain,
            'protocol': protocol,
        })
        
        # Send email
        try:
            send_mail(
                subject,
                '',  # Empty message as we're using html_message
                None,  # Use DEFAULT_FROM_EMAIL from settings
                [user.email],
                html_message=message,
                fail_silently=False,
            )
            messages.success(request, 'Password reset link has been sent to your email.')
            return redirect('home:forgot_password')
        except Exception as e:
            # Log full exception details so we can investigate (stack trace included)
            logger.exception("Failed to send password reset email to %s", user.email)
            messages.error(request, 'An error occurred while sending the reset email. Our team has been notified.')
            return redirect('home:forgot_password')
    
    return render(request, 'home/forgot_password.html')

def password_reset_confirm(request, uidb64, token):
    """Handle password reset confirmation"""
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your password has been set. You may go ahead and log in now.')
                return redirect('home:login')
        else:
            form = SetPasswordForm(user)
        
        return render(request, 'home/password_reset_confirm.html', {'form': form})
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('home:forgot_password')


@staff_member_required
def email_health_check(request):
    """Health check endpoint for email subsystem. Attempts to open an email connection.
    Restricted to staff users.

    If EMAIL_HEALTH_CHECK_RECIPIENT is configured and environment variable
    EMAIL_HEALTH_CHECK_SEND='True' is set, the view will attempt to send a small test message
    to verify end-to-end delivery (useful in staging/production).
    """
    try:
        conn = get_connection()
        # Opening the connection will attempt to contact the SMTP server if using SMTP backend
        conn.open()
        conn.close()

        # Optional: attempt a small send if requested via environment
        send_test = os.getenv('EMAIL_HEALTH_CHECK_SEND', 'False') == 'True'
        recipient = getattr(settings, 'EMAIL_HEALTH_CHECK_RECIPIENT', '')
        if send_test and recipient:
            try:
                send_mail('WAPANGAJI email health check', 'This is a health check.', settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
            except Exception as e:
                logger.exception('Email health check send failed: %s', str(e))
                return JsonResponse({'status': 'error', 'detail': f'connection_ok_but_send_failed: {str(e)}'}, status=500)

        return JsonResponse({'status': 'ok', 'detail': 'SMTP connection succeeded'})
    except Exception as e:
        logger.exception('Email health check failed: %s', str(e))
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=500)