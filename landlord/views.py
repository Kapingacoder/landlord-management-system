

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from properties.models import Property, Unit
from tenancy.models import MaintenanceRequest, Payment, Tenancy, Document
from django.utils import timezone
from communication.models import Message
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
import csv
from reportlab.pdfgen import canvas
from datetime import datetime, date
import json
from reportlab.lib.pagesizes import letter
from .forms import ProfileForm, PaymentMethodForm, NotificationPreferenceForm, SystemPreferenceForm
from users.models import User
from .models import PaymentMethod, NotificationPreference, SystemPreference
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

# Create your views here.

@login_required(login_url='home:index')
def dashboard(request):
    """Render the landlord dashboard with real properties for this landlord"""
    properties = Property.objects.filter(landlord=request.user)
    units = Unit.objects.filter(property__in=properties)
    tenancies = Tenancy.objects.filter(unit__in=units).select_related('tenant', 'unit', 'unit__property')
    payments = Payment.objects.filter(tenancy__in=tenancies)
    
    # Annotate tenancies with payment information
    from django.db.models import Sum, Q
    
    # Create a list to store tenancy data with payment info
    tenancies_with_payments = []
    
    for tenancy in tenancies:
        # Get payment stats for this tenancy
        payment_stats = Payment.objects.filter(tenancy=tenancy).aggregate(
            total_paid=Sum('amount', filter=Q(status='Paid')),
            total_pending=Sum('amount', filter=Q(status='Pending')),
            total_late=Sum('amount', filter=Q(status__in=['Late', 'Overdue'])),
        )
        
        total_paid = payment_stats['total_paid'] or 0
        total_pending = payment_stats['total_pending'] or 0
        total_late = payment_stats['total_late'] or 0
        
        # Calculate the balance (total rent due - total paid)
        # Rent is calculated as (months_paid * rent_amount)
        total_rent_due = tenancy.months_paid * tenancy.unit.rent_amount if tenancy and tenancy.months_paid else 0
        balance = total_rent_due - total_paid
        
        # Calculate payment status based on months paid
        payment_status = 'Paid'
        if tenancy and tenancy.months_paid == 0:
            payment_status = 'Unpaid'
        elif balance > 0:
            payment_status = 'Partial'
        
        # Add payment info to tenancy object
        tenancy.total_paid = total_paid
        tenancy.total_pending = total_pending
        tenancy.total_late = total_late
        tenancy.balance = balance
        tenancy.absolute_balance = abs(balance)
        tenancy.payment_status = payment_status
        
        tenancies_with_payments.append(tenancy)

    # Get all maintenance requests for the landlord's properties
    tenant_users = User.objects.filter(tenancies__in=tenancies).distinct()
    maintenance_requests = MaintenanceRequest.objects.filter(
        tenant__in=tenant_users
    ).order_by('-submitted_at')

    # Calculate maintenance stats
    total_maintenance_requests = maintenance_requests.count()
    in_progress_requests = maintenance_requests.filter(status='In Progress').count()
    completed_requests = maintenance_requests.filter(status='Completed').count()

    # Get messages for this landlord (from tenants)
    landlord_messages = Message.objects.filter(
        recipient=request.user
    ).order_by('-sent_at')[:5]  # Latest 5 messages for dashboard
    
    # Count unread messages
    unread_messages_count = Message.objects.filter(
        recipient=request.user, 
        read_at__isnull=True
    ).count()

    # For payment stats
    monthly_income = payments.filter(date__month=timezone.now().month, status='Paid').aggregate(total=Sum('amount'))['total'] or 0
    pending_payments = payments.filter(status='Pending').count()
    late_payments = payments.filter(status__in=['Late', 'Overdue']).count()
    
    # For recent payments table
    recent_payments = payments.order_by('-date')[:5]

    # For property names in filter
    property_names = properties.values_list('name', flat=True)

    context = {
        'properties': properties,
        'tenancies': tenancies_with_payments,  # Use the annotated tenancies list
        'monthly_income': monthly_income,
        'pending_payments': pending_payments,
        'late_payments': late_payments,
        'recent_payments': recent_payments,
        'property_names': property_names,
        # Add maintenance requests to the context
        'maintenance_requests': maintenance_requests,
        'total_maintenance_requests': total_maintenance_requests,
        'in_progress_requests': in_progress_requests,
        'completed_requests': completed_requests,
        # Add messages to the context
        'messages': landlord_messages,
        'unread_messages_count': unread_messages_count,
        # Summary counts for cards
        'properties_count': properties.count(),
        'tenants_count': tenancies.count(),
        'payments_count': payments.filter(status='Paid').count(),
        'messages_count': unread_messages_count,
        'maintenance_count': total_maintenance_requests,
    }
    return render(request, 'landlord/dashboard.html', context)

@login_required(login_url='home:index')
def home_summary(request):
    """Display a comprehensive summary of all landlord management data"""
    properties = Property.objects.filter(landlord=request.user)
    units = Unit.objects.filter(property__in=properties)
    tenancies = Tenancy.objects.filter(unit__in=units).select_related('tenant', 'unit', 'unit__property')
    payments = Payment.objects.filter(tenancy__in=tenancies)
    tenant_ids = tenancies.values_list('tenant', flat=True)
    maintenance_requests = MaintenanceRequest.objects.filter(tenant__in=tenant_ids)
    
    # Calculate summary statistics
    total_properties = properties.count()
    total_units = units.count()
    total_tenants = tenancies.count()
    active_tenancies = tenancies.filter(is_active=True).count()
    
    # Payment statistics
    total_payments_received = payments.filter(status='Paid').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    pending_payments = payments.filter(status='Pending').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    overdue_payments = payments.filter(status__in=['Late', 'Overdue']).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Maintenance statistics
    total_maintenance = maintenance_requests.count()
    pending_maintenance = maintenance_requests.filter(status='Pending').count()
    completed_maintenance = maintenance_requests.filter(status='Completed').count()
    
    # Recent activities (last 30 days)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_payments = payments.filter(date__gte=thirty_days_ago.date(), status='Paid').count()
    recent_maintenance = maintenance_requests.filter(submitted_at__gte=thirty_days_ago).count()
    
    context = {
        'total_properties': total_properties,
        'total_units': total_units,
        'total_tenants': total_tenants,
        'active_tenancies': active_tenancies,
        'total_payments_received': total_payments_received,
        'pending_payments': pending_payments,
        'overdue_payments': overdue_payments,
        'total_maintenance': total_maintenance,
        'pending_maintenance': pending_maintenance,
        'completed_maintenance': completed_maintenance,
        'recent_payments': recent_payments,
        'recent_maintenance': recent_maintenance,
    }
    return render(request, 'landlord/home_summary.html', context)

# Reports & Analytics view

def reports(request):
    # Get all properties for this landlord
    properties = Property.objects.filter(landlord=request.user)
    total_properties = properties.count()
    units = Unit.objects.filter(property__in=properties)
    total_units = units.count()
    occupied_units = units.filter(is_occupied=True).count()

    # Monthly income (sum of rent for occupied units)
    monthly_income = units.filter(is_occupied=True).aggregate(total=Sum('rent_amount'))['total'] or 0

    # Payments (real data)
    tenancies = Tenancy.objects.filter(unit__property__in=properties)
    payments = Payment.objects.filter(tenancy__in=tenancies)
    pending_payments = payments.filter(status='Pending').count()
    late_payments = payments.filter(status='Late').count()

    # Recent payments
    recent_payments = payments.order_by('-date')[:10]

    # Maintenance statistics
    maintenance_requests = MaintenanceRequest.objects.filter(tenant__tenancies__unit__property__in=properties)
    pending_maintenance = maintenance_requests.filter(status='Pending').count()
    maintenance_in_progress = maintenance_requests.filter(status='In Progress').count()
    maintenance_completed = maintenance_requests.filter(status='Completed').count()

    # Payment method breakdown
    payment_methods = payments.values('method').annotate(count=Count('method')).order_by('-count')
    payment_method_labels = [item['method'] for item in payment_methods]
    payment_method_data = [item['count'] for item in payment_methods]

    # Monthly income trends (last 6 months)
    from django.utils import timezone
    import calendar
    today = timezone.now().date()
    months = []
    income_data = []
    for i in range(5, -1, -1):
        month = (today.month - i - 1) % 12 + 1
        year = today.year if today.month - i > 0 else today.year - 1
        month_name = calendar.month_abbr[month]
        months.append(month_name)
        month_payments = payments.filter(date__year=year, date__month=month, status='Paid').aggregate(total=Sum('amount'))['total'] or 0
        income_data.append(float(month_payments))

    # Occupancy rate chart
    vacant_units = total_units - occupied_units

    # Property performance (stub: use occupancy or income per property)
    property_names = [p.name for p in properties]
    property_performance = [units.filter(property=p, is_occupied=True).count() for p in properties]

    context = {
        'total_properties': total_properties,
        'occupied_units': occupied_units,
        'total_units': total_units,
        'vacant_units': vacant_units,
        'monthly_income': monthly_income,
        'pending_payments': pending_payments,
        'late_payments': late_payments,
        'pending_maintenance': pending_maintenance,
        'maintenance_in_progress': maintenance_in_progress,
        'maintenance_completed': maintenance_completed,
        'payment_method_labels': json.dumps(payment_method_labels),
        'payment_method_data': json.dumps(payment_method_data),
        'income_months': json.dumps(months),
        'income_data': json.dumps(income_data),
        'property_names': json.dumps(property_names),
        'property_performance': json.dumps(property_performance),
        'recent_payments': recent_payments,
    }
    return render(request, 'landlord/reports.html', context)

def export_payments_csv(request):
    # Get filters from request
    start_date = request.GET.get('start_date')
    property_name = request.GET.get('property')
    status = request.GET.get('status')

    # Get all payments for the landlord's properties
    properties = Property.objects.filter(landlord=request.user)
    units = Unit.objects.filter(property__in=properties)
    tenancies = Tenancy.objects.filter(unit__in=units)
    payments = Payment.objects.filter(tenancy__in=tenancies)
    if start_date:
        payments = payments.filter(date__gte=start_date)
    if property_name:
        payments = payments.filter(tenancy__unit__property__name=property_name)
    if status:
        payments = payments.filter(status=status)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename_date = f"{start_date}_to_now" if start_date else "all_payments"
    response['Content-Disposition'] = f'attachment; filename="payments_{filename_date}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Tenant', 'Property', 'Amount', 'Date', 'Status', 'Method'])
    for payment in payments:
        writer.writerow([
            payment.tenancy.tenant.get_full_name() or payment.tenancy.tenant.username,
            payment.tenancy.unit.property.name,
            payment.amount,
            payment.date,
            payment.status,
            payment.method,
        ])
    return response

def export_payments_pdf(request):
    # Get filters from request
    start_date = request.GET.get('start_date')
    property_name = request.GET.get('property')
    status = request.GET.get('status')

    # Get all payments for the landlord's properties
    properties = Property.objects.filter(landlord=request.user)
    units = Unit.objects.filter(property__in=properties)
    tenancies = Tenancy.objects.filter(unit__in=units)
    payments = Payment.objects.filter(tenancy__in=tenancies)
    if start_date:
        payments = payments.filter(date__gte=start_date)
    if property_name:
        payments = payments.filter(tenancy__unit__property__name=property_name)
    if status:
        payments = payments.filter(status=status)

    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="payments.pdf"'
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    y = height - 40
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, "Payments Report")
    y -= 30
    p.setFont("Helvetica", 10)
    date_range = f"from {start_date} to now" if start_date else "all dates"
    p.drawString(40, y, f"Filters: {date_range}, Property: {property_name or 'All'}, Status: {status or 'All'}")
    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(40, y, "Tenant")
    p.drawString(140, y, "Property")
    p.drawString(240, y, "Amount")
    p.drawString(300, y, "Date")
    p.drawString(370, y, "Status")
    p.drawString(440, y, "Method")
    y -= 20
    p.setFont("Helvetica", 10)
    for payment in payments:
        if y < 50:
            p.showPage()
            y = height - 40
        p.drawString(40, y, str(payment.tenancy.tenant.get_full_name() or payment.tenancy.tenant.username))
        p.drawString(140, y, str(payment.tenancy.unit.property.name))
        p.drawString(240, y, f"${payment.amount}")
        p.drawString(300, y, payment.date.strftime('%Y-%m-%d'))
        p.drawString(370, y, payment.status)
        p.drawString(440, y, payment.method)
        y -= 18
    p.save()
    return response

@login_required(login_url='home:index')
def settings(request):
    user = request.user
    # Only allow landlords
    if not hasattr(user, 'user_type') or user.user_type != 'landlord':
        return redirect('dashboard')

    # Profile settings: update name, email, phone, profile picture
    profile_form = ProfileForm(instance=user)
    if request.method == 'POST' and 'save_profile' in request.POST:
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
        else:
            messages.error(request, 'Please correct the errors in your profile form.')

    # Payment Methods: add, edit, delete
    payment_methods = PaymentMethod.objects.filter(landlord=user)
    payment_form = PaymentMethodForm()
    edit_id = request.GET.get('edit_payment')
    delete_id = request.GET.get('delete_payment')
    edit_form = None
    # Handle add
    if request.method == 'POST' and 'add_payment' in request.POST:
        payment_form = PaymentMethodForm(request.POST)
        if payment_form.is_valid():
            pm = payment_form.save(commit=False)
            pm.landlord = user
            pm.save()
            messages.success(request, 'Payment method added!')
        else:
            messages.error(request, 'Please correct the errors in your payment method form.')
    # Handle edit
    if edit_id:
        edit_pm = get_object_or_404(PaymentMethod, id=edit_id, landlord=user)
        edit_form = PaymentMethodForm(instance=edit_pm)
        if request.method == 'POST' and 'edit_payment' in request.POST:
            edit_form = PaymentMethodForm(request.POST, instance=edit_pm)
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, 'Payment method updated!')
            else:
                messages.error(request, 'Please correct the errors in your payment method form.')
    # Handle delete
    if delete_id:
        del_pm = get_object_or_404(PaymentMethod, id=delete_id, landlord=user)
        del_pm.delete()
        messages.success(request, 'Payment method deleted!')
        return redirect('landlord_settings')

    # Notification Preferences
    notif_pref, _ = NotificationPreference.objects.get_or_create(landlord=user)
    notif_form = NotificationPreferenceForm(instance=notif_pref)
    if request.method == 'POST' and 'save_notifications' in request.POST:
        notif_form = NotificationPreferenceForm(request.POST, instance=notif_pref)
        if notif_form.is_valid():
            notif_form.save()
            messages.success(request, 'Notification preferences updated!')
        else:
            messages.error(request, 'Please correct the errors in your notification preferences.')

    # System Preferences
    sys_pref, _ = SystemPreference.objects.get_or_create(landlord=user)
    sys_form = SystemPreferenceForm(instance=sys_pref)
    if request.method == 'POST' and 'save_system' in request.POST:
        sys_form = SystemPreferenceForm(request.POST, instance=sys_pref)
        if sys_form.is_valid():
            sys_form.save()
            messages.success(request, 'System preferences updated!')
        else:
            messages.error(request, 'Please correct the errors in your system preferences.')

    # Security Settings: password update (basic)
    password_message = None
    if request.method == 'POST' and 'save_password' in request.POST:
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if not user.check_password(old_password):
            password_message = 'Old password is incorrect.'
        elif new_password != confirm_password:
            password_message = 'New passwords do not match.'
        elif len(new_password) < 8:
            password_message = 'New password must be at least 8 characters.'
        else:
            user.set_password(new_password)
            user.save()
            password_message = 'Password updated successfully!'
            messages.success(request, password_message)
        if password_message and 'successfully' not in password_message:
            messages.error(request, password_message)

    context = {
        'profile_form': profile_form,
        'payment_form': payment_form,
        'edit_form': edit_form,
        'payment_methods': payment_methods,
        'notif_form': notif_form,
        'sys_form': sys_form,
        'profile_picture_url': user.profile_picture.url if user.profile_picture else None,
    }
    return render(request, 'landlord/settings.html', context)

# Standalone manage pages for each settings section
@login_required(login_url='home:index')
def profile_manage(request):
    """
    Profile Settings – Manage Page
    Allows landlord to edit name, email, phone, and profile picture.
    Shows success/error messages. Responsive, modern UI.
    """
    # TODO: Implement full form logic and template rendering
    return render(request, 'landlord/profile_manage.html', {})

@login_required(login_url='home:index')
def payment_methods_manage(request):
    """
    Payment Methods – Manage Page
    Add, edit, delete payment methods. Validate inputs, show messages.
    Responsive, modern UI.
    """
    # TODO: Implement full form logic and template rendering
    return render(request, 'landlord/payment_methods_manage.html', {})

@login_required(login_url='home:index')
def notification_preferences_manage(request):
    """
    Notification Preferences – Manage Page
    Toggle email/SMS notifications. Save settings to DB. Modern UI.
    """
    # TODO: Implement full form logic and template rendering
    return render(request, 'landlord/notification_preferences_manage.html', {})

@login_required(login_url='home:index')
def security_settings_manage(request):
    """
    Security Settings – Manage Page
    Change password, basic 2FA setup. All actions fully functional.
    Responsive, modern UI.
    """
    # TODO: Implement full form logic and template rendering
    return render(request, 'landlord/security_settings_manage.html', {})

@login_required(login_url='home:index')
def maintenance_detail(request, pk):
    """
    Show details for a single maintenance request for landlord.
    Allow landlord to update status and send messages to tenant.
    """
    # Get the maintenance request and verify landlord owns the property
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    tenant = maintenance_request.tenant

    # Verify landlord owns the property this tenant is renting
    tenancy = Tenancy.objects.filter(tenant=tenant, is_active=True).first()
    if not tenancy or tenancy.unit.property.landlord != request.user:
        messages.error(request, 'You do not have permission to view this maintenance request.')
        return redirect('landlord:dashboard')

    if request.method == 'POST':
        if 'update_status' in request.POST:
            new_status = request.POST.get('status')
            if new_status in dict(MaintenanceRequest.STATUS_CHOICES):
                maintenance_request.status = new_status
                maintenance_request.save()
                messages.success(request, f'Maintenance request status updated to {new_status}.')
            else:
                messages.error(request, 'Invalid status selected.')
        elif 'send_message' in request.POST:
            subject = request.POST.get('subject')
            body = request.POST.get('body')
            if subject and body:
                Message.objects.create(
                    sender=request.user,
                    recipient=tenant,
                    subject=subject,
                    body=body
                )
                messages.success(request, 'Message sent to tenant successfully.')
            else:
                messages.error(request, 'Please fill in both subject and message.')


    context = {
        'request': maintenance_request,
        'tenancy': tenancy,
        'status_choices': MaintenanceRequest.STATUS_CHOICES,
    }
    return render(request, 'landlord/maintenance_detail.html', context)

# Message Management Views
@login_required(login_url='home:index')
def message_detail(request, pk):
    """Display a single message and allow landlord to reply"""
    try:
        message = get_object_or_404(Message, pk=pk, recipient=request.user)
        
        # Mark as read
        if not message.read_at:
            message.read_at = timezone.now()
            message.save()
        
        if request.method == 'POST':
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            
            if not all([subject, body]):
                messages.error(request, 'Please fill in all fields')
                return redirect('landlord:message_detail', pk=pk)
            
            try:
                # Send reply message to the tenant
                reply_message = Message.objects.create(
                    sender=request.user,
                    recipient=message.sender,  # Reply to the original sender (tenant)
                    subject=subject,
                    body=body
                )
                
                messages.success(request, 'Reply sent successfully!')
                return redirect('landlord:message_detail', pk=pk)
                
            except Exception as e:
                messages.error(request, f'Error sending reply: {str(e)}')
                # Return the form with the submitted data
                context = {
                    'page_title': f'Message: {message.subject}',
                    'message': message,
                    'form': {  # Pass the form data back to the template
                        'body': {'value': body},
                        'errors': {'body': ['Failed to send message. Please try again.']}
                    }
                }
                return render(request, 'landlord/message_detail.html', context)
        
        # For GET requests or if there was an error
        context = {
            'page_title': f'Message: {message.subject}',
            'message': message,
            'form': {
                'body': {'value': ''},
                'errors': {}
            }
        }
        
        return render(request, 'landlord/message_detail.html', context)
    
    except Exception as e:
        messages.error(request, f'Error loading message: {str(e)}')
def send_message(request):
    """Allow landlord to send new message to one or more tenants or all tenants"""
    try:
        # Get all active tenancies for this landlord to select tenant
        tenancies = Tenancy.objects.filter(
            unit__property__landlord=request.user,
            is_active=True
        ).select_related('tenant', 'unit', 'unit__property')
        
        if not tenancies.exists():
            messages.error(request, 'No active tenancies found')
            return redirect('landlord:dashboard')
        
        if request.method == 'POST':
            tenant_ids = request.POST.getlist('tenants')
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            send_to_all = 'send_to_all' in request.POST
            
            # Validate inputs
            if not all([subject, body]):
                messages.error(request, 'Please fill in all required fields')
                return redirect('landlord:send_message')
                
            if not send_to_all and not tenant_ids:
                messages.error(request, 'Please select at least one tenant or choose "All Tenants"')
                return redirect('landlord:send_message')
            
            # Get recipients based on selection
            if send_to_all:
                # Get all active tenants for this landlord
                recipients = User.objects.filter(
                    id__in=tenancies.values_list('tenant', flat=True).distinct(),
                    user_type='tenant'
                )
                success_message = f'Message sent to all {recipients.count()} tenants'
            else:
                # Get selected tenants that belong to this landlord
                recipients = User.objects.filter(
                    id__in=tenant_ids,
                    user_type='tenant',
                    tenancies__unit__property__landlord=request.user,
                    tenancies__is_active=True
                ).distinct()
                
                if not recipients.exists():
                    messages.error(request, 'No valid tenants selected')
                    return redirect('landlord:send_message')
                
                success_message = f'Message sent to {recipients.count()} tenant(s)'
            
            # Send message to each recipient
            messages_sent = 0
            for recipient in recipients:
                try:
                    Message.objects.create(
                        sender=request.user,
                        recipient=recipient,
                        subject=subject,
                        body=body
                    )
                    messages_sent += 1
                except Exception as e:
                    logger.error(f"Error sending message to {recipient.id}: {str(e)}")
            
            if messages_sent > 0:
                messages.success(request, success_message)
            else:
                messages.error(request, 'Failed to send messages to any recipients')
            
            return redirect('landlord:messages')
        
        context = {
            'page_title': 'Send New Message',
            'tenancies': tenancies,
            'total_tenants': tenancies.values('tenant').distinct().count()
        }
        
        return render(request, 'landlord/send_message.html', context)
    
    except Exception as e:
        messages.error(request, f'Error sending message: {str(e)}')
        return redirect('landlord:send_message')

@login_required(login_url='home:index')
def payment_history_landlord(request):
    """
    API view to fetch payment history data for landlord dashboard.
    Returns grouped payment data by tenant and tenancy with totals.
    """
    try:
        # Initialize default response data
        response_data = {
            'payment_data': [],
            'stats': {
                'total_paid': 0,
                'total_pending': 0,
                'total_late': 0,
                'total_amount': 0,
                'total_payments': 0,
                'unique_tenants': 0
            },
            'filters': {
                'property_names': [],
                'tenants': [],
                'status_choices': [],
                'method_choices': []
            }
        }
        
        # Get all properties for this landlord
        properties = Property.objects.filter(landlord=request.user)
        if not properties.exists():
            return JsonResponse(response_data)
        
        # Get all tenancies for these properties
        tenancies = Tenancy.objects.filter(unit__property__in=properties)
        if not tenancies.exists():
            return JsonResponse(response_data)
        
        # Get all payments for these tenancies with related data
        payments = Payment.objects.filter(tenancy__in=tenancies).select_related(
            'tenancy__tenant', 
            'tenancy__unit',
            'tenancy__unit__property',
            'created_by'
        ).order_by('-date', '-created_at')
        
        # Apply filters
        start_date = request.GET.get('start_date')
        property_filter = request.GET.get('property')
        status_filter = request.GET.get('status')
        tenant_filter = request.GET.get('tenant')
        payment_method = request.GET.get('method')
        
        if start_date:
            payments = payments.filter(date__gte=start_date)
        if property_filter:
            payments = payments.filter(tenancy__unit__property__name=property_filter)
        if status_filter:
            payments = payments.filter(status=status_filter)
        if tenant_filter:
            payments = payments.filter(tenancy__tenant__id=tenant_filter)
        if payment_method:
            payments = payments.filter(method=payment_method)
        
        # Initialize payment data structure
        from collections import defaultdict
        payment_data = defaultdict(lambda: {
            'tenant_name': 'Unknown Tenant',
            'tenant_id': None,
            'property_name': 'Unknown Property',
            'unit_identifier': 'N/A',
            'tenancy_id': None,
            'payments': [],
            'total_paid': 0,
            'total_pending': 0,
            'total_late': 0,
            'total_amount': 0,
            'payment_count': 0,
            'last_payment_date': None
        })
        
        overall_total = 0
        total_paid = 0
        total_pending = 0
        total_late = 0
        
        for payment in payments:
            try:
                tenancy = payment.tenancy
                tenant = getattr(tenancy, 'tenant', None)
                unit = getattr(tenancy, 'unit', None)
                property_obj = getattr(unit, 'property', None) if unit else None
                
                # Skip if required relationships are missing
                if not all([tenancy, tenant, unit, property_obj]):
                    print(f"Skipping payment {payment.id} due to missing relationships")
                    continue
                    
                # Create unique key for tenant-tenancy combination
                key = f"{getattr(tenant, 'id', 'unknown')}_{getattr(tenancy, 'id', 'unknown')}"
            
                # Initialize tenant-tenancy group if not exists
                if not payment_data[key].get('tenant_name', '').strip():
                    payment_data[key]['tenant_name'] = getattr(tenant, 'get_full_name', lambda: '')() or getattr(tenant, 'username', 'Unknown Tenant')
                    payment_data[key]['tenant_id'] = getattr(tenant, 'id', None)
                    payment_data[key]['property_name'] = getattr(property_obj, 'name', 'Unknown Property')
                    payment_data[key]['unit_identifier'] = getattr(unit, 'unit_identifier', None) or f"Unit {getattr(unit, 'id', '?')}"
                    payment_data[key]['tenancy_id'] = getattr(tenancy, 'id', None)
            
                # Format payment date
                payment_date = getattr(payment, 'date', timezone.now().date())
                formatted_date = payment_date.strftime('%b %d, %Y') if hasattr(payment_date, 'strftime') else 'N/A'
                
                # Get created by info safely
                created_by = getattr(payment, 'created_by', None)
                created_by_name = ''
                if created_by:
                    created_by_name = getattr(created_by, 'get_full_name', lambda: getattr(created_by, 'username', 'System'))()
                
                # Add payment to group with more details
                payment_info = {
                    'id': getattr(payment, 'id', 0),
                    'amount': float(getattr(payment, 'amount', 0)),
                    'date': payment_date.strftime('%Y-%m-%d') if hasattr(payment_date, 'strftime') else 'N/A',
                    'formatted_date': formatted_date,
                    'status': getattr(payment, 'status', 'Unknown'),
                    'method': getattr(payment, 'method', 'N/A'),
                    'reference_number': getattr(payment, 'reference_number', 'N/A') or 'N/A',
                    'transaction_id': getattr(payment, 'transaction_id', 'N/A') or 'N/A',
                    'description': getattr(payment, 'description', 'Rent Payment') or 'Rent Payment',
                    'created_by': created_by_name or 'System',
                    'created_at': getattr(payment, 'created_at', timezone.now()).strftime('%b %d, %Y %I:%M %p') if hasattr(getattr(payment, 'created_at', None), 'strftime') else 'N/A',
                    'has_proof': bool(getattr(payment, 'payment_proof', None))
                }
            
                payment_data[key]['payments'].append(payment_info)
                
                # Update totals based on payment status
                amount = float(getattr(payment, 'amount', 0))
                status = getattr(payment, 'status', '').lower()
                
                # Update payment status totals
                if status == 'paid':
                    payment_data[key]['total_paid'] += amount
                    total_paid += amount
                elif status == 'pending':
                    payment_data[key]['total_pending'] += amount
                    total_pending += amount
                elif status == 'late':
                    payment_data[key]['total_late'] += amount
                    total_late += amount
                
                # Update overall totals
                payment_data[key]['total_amount'] += amount
                payment_data[key]['payment_count'] += 1
                overall_total += amount
                
                # Update last payment date
                if hasattr(payment_date, 'strftime'):
                    last_date_str = payment_data[key]['last_payment_date']
                    if not last_date_str or (isinstance(payment_date, str) and payment_date > last_date_str) or \
                       (not isinstance(payment_date, str) and payment_date > datetime.strptime(last_date_str, '%Y-%m-%d').date() if last_date_str else True):
                        payment_data[key]['last_payment_date'] = payment_date.strftime('%Y-%m-%d')
                        
            except Exception as e:
                import traceback
                print(f"Error processing payment {getattr(payment, 'id', 'unknown')}: {str(e)}")
                traceback.print_exc()
                continue
        
        # Convert to list and sort by tenant name
        payment_list = list(payment_data.values())
        try:
            payment_list.sort(key=lambda x: str(x.get('tenant_name', '')).lower())
        except Exception as e:
            print(f"Error sorting payment list: {str(e)}")
            # Sort by tenant ID as fallback
            payment_list.sort(key=lambda x: x.get('tenant_id', 0))
        
        # Get filter options for frontend
        property_names = list(properties.exclude(name__isnull=True).exclude(name='').values_list('name', flat=True).distinct())
        tenant_list = User.objects.filter(
            tenancies__in=tenancies,
            user_type='tenant'
        ).distinct()
        
        # Initialize statistics with default values
        stats = {
            'total_paid': 0.0,
            'total_pending': 0.0,
            'total_late': 0.0,
            'total_amount': 0.0,
            'total_payments': 0,
            'unique_tenants': 0
        }
        
        try:
            # Recalculate totals from the payment list to ensure accuracy
            total_paid = 0.0
            total_pending = 0.0
            total_late = 0.0
            total_amount = 0.0
            total_payments = 0
            
            for group in payment_list:
                if not isinstance(group, dict) or 'payments' not in group:
                    continue
                    
                for payment in group.get('payments', []):
                    if not isinstance(payment, dict):
                        continue
                        
                    amount = float(payment.get('amount', 0))
                    status = str(payment.get('status', '')).lower()
                    
                    if status == 'paid':
                        total_paid += amount
                    elif status == 'pending':
                        total_pending += amount
                    elif status == 'late':
                        total_late += amount
                    
                    total_amount += amount
                    total_payments += 1
            
            # Update stats with calculated values
            stats.update({
                'total_paid': round(total_paid, 2),
                'total_pending': round(total_pending, 2),
                'total_late': round(total_late, 2),
                'total_amount': round(total_amount, 2),
                'total_payments': total_payments,
                'unique_tenants': len(payment_list) if isinstance(payment_list, list) else 0
            })
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating payment statistics: {str(e)}", exc_info=True)
            # Use the accumulated values even if there was an error
            
        payment_stats = stats
        
        # Prepare response data with safe defaults
        response_data = {
            'payment_data': payment_list,
            'stats': {
                'total_paid': total_paid,
                'total_pending': total_pending,
                'total_late': total_late,
                'total_amount': overall_total,
                'total_payments': sum(len(group['payments']) for group in payment_list),
                'unique_tenants': len(payment_list)
            },
            'filters': {
                'property_names': property_names,
                'tenants': [
                    {
                        'id': getattr(t, 'id', 0),
                        'name': getattr(t, 'get_full_name', lambda: getattr(t, 'username', 'Unknown'))()
                    } for t in tenant_list if t is not None
                ],
                'status_choices': [choice[0] for choice in getattr(Payment, 'STATUS_CHOICES', [])],
                'method_choices': [choice[0] for choice in getattr(Payment, 'PAYMENT_METHODS', [])]
            }
        }
        
        # Ensure all values are JSON serializable
        def make_json_serializable(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {str(k): make_json_serializable(v) for k, v in obj.items()}
            elif hasattr(obj, '__dict__'):
                return make_json_serializable(obj.__dict__)
            else:
                return str(obj)
        
        # Convert response data to JSON-serializable format
        safe_response = make_json_serializable(response_data)
        
        try:
            return JsonResponse(
                safe_response, 
                json_dumps_params={'indent': 2} if request.GET.get('pretty') else None,
                safe=False
            )
        except Exception as e:
            print(f"Error serializing response: {str(e)}")
            # Return minimal valid response if serialization fails
            return JsonResponse({
                'error': 'Error processing payment data',
                'payment_data': [],
                'stats': {
                    'total_paid': 0,
                    'total_pending': 0,
                    'total_late': 0,
                    'total_amount': 0,
                    'total_payments': 0,
                    'unique_tenants': 0
                },
                'filters': {
                    'property_names': [],
                    'tenants': [],
                    'status_choices': [],
                    'method_choices': []
                }
            }, status=200)
        
    except Exception as e:
        import traceback
        error_msg = f"Error in payment_history_landlord: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        
        # Return empty but valid response structure
        return JsonResponse({
            'error': 'An error occurred while loading payment data.',
            'payment_data': [],
            'stats': {
                'total_paid': 0,
                'total_pending': 0,
                'total_late': 0,
                'total_amount': 0,
                'total_payments': 0,
                'unique_tenants': 0
            },
            'filters': {
                'property_names': [],
                'tenants': [],
                'status_choices': [],
                'method_choices': []
            }
        }, status=200)  # Return 200 with error message instead of 500

# New views for separate pages

@login_required(login_url='home:index')
def properties_view(request):
    """Properties management page"""
    properties = Property.objects.filter(landlord=request.user)
    context = {
        'properties': properties,
    }
    return render(request, 'landlord/properties.html', context)

@login_required(login_url='home:index')
def tenants_view(request):
    """Tenants management page"""
    tenancies = Tenancy.objects.filter(unit__property__landlord=request.user).select_related('tenant', 'unit', 'unit__property')
    context = {
        'tenancies': tenancies,
    }
    return render(request, 'landlord/tenants.html', context)

@login_required(login_url='home:index')
def payments_view(request):
    """Payments page"""
    payments = Payment.objects.filter(tenancy__unit__property__landlord=request.user).select_related('tenancy__tenant', 'tenancy__unit__property')
    
    # Calculate total amount from all payments
    total_amount = payments.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'payments': payments,
        'total_amount': total_amount,
    }
    return render(request, 'landlord/payments.html', context)

@login_required(login_url='home:index')
def messages_view(request):
    """Messages page with inbox and compose functionality"""
    try:
        # Get all properties owned by the landlord
        properties = Property.objects.filter(landlord=request.user)
        
        # Get all active tenancies for this landlord
        tenancies = Tenancy.objects.filter(
            unit__property__in=properties,
            is_active=True
        ).select_related('tenant', 'unit', 'unit__property')
        
        # Get messages for this landlord (from tenants)
        messages_list = Message.objects.filter(recipient=request.user).order_by('-sent_at')
        
        # Calculate statistics
        unread_messages = messages_list.filter(read_at__isnull=True).count()
        total_messages = messages_list.count()
        
        # Get unique senders for active conversations
        active_conversations = messages_list.values('sender').distinct().count()
        
        # Count pending replies (messages from tenants that haven't been replied to yet)
        tenant_messages = Message.objects.filter(
            recipient=request.user,
            sender__user_type='tenant'
        ).values_list('sender_id', flat=True).distinct()
        
        landlord_replies = Message.objects.filter(
            sender=request.user,
            recipient_id__in=tenant_messages
        ).values_list('recipient_id', flat=True).distinct()
        
        pending_replies = len(set(tenant_messages) - set(landlord_replies))
        
        context = {
            'messages_list': messages_list,
            'tenancies': tenancies,
            'unread_messages': unread_messages,
            'total_messages': total_messages,
            'active_conversations': active_conversations,
            'pending_replies': pending_replies,
        }
        return render(request, 'landlord/messages.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading messages: {str(e)}')
        return redirect('landlord:dashboard')

@login_required(login_url='home:index')
def maintenance_view(request):
    """Maintenance requests page"""
    maintenance_requests = MaintenanceRequest.objects.filter(
        tenant__tenancies__unit__property__landlord=request.user
    ).select_related('tenant').distinct().order_by('-submitted_at')
    
    # Add property to each request for display
    for req in maintenance_requests:
        # Find the property for this landlord
        tenancies = req.tenant.tenancies.filter(unit__property__landlord=request.user)
        if tenancies.exists():
            req.property_name = tenancies.first().unit.property.name
        else:
            req.property_name = "N/A"
    
    context = {
        'maintenance_requests': maintenance_requests,
    }
    return render(request, 'landlord/maintenance.html', context)

@login_required(login_url='home:index')
def record_payment(request):
    """
    View for landlords to record a new payment from a tenant.
    """
    # Get active tenancies for the current landlord
    properties = Property.objects.filter(landlord=request.user)
    units = Unit.objects.filter(property__in=properties)
    
    # Get tenant_id from query parameters if available
    tenant_id = request.GET.get('tenant_id')
    
    # Get the tenant if tenant_id is provided
    tenant = None
    if tenant_id:
        try:
            tenant = User.objects.get(id=tenant_id)
            # Check if tenant has any tenancies in landlord's properties
            tenant_tenancies = Tenancy.objects.filter(
                tenant=tenant,
                unit__in=units
            )
            
            if not tenant_tenancies.exists():
                messages.warning(
                    request,
                    f"Note: {tenant.get_full_name() or tenant.username} doesn't have an active tenancy. "
                    "You can still record payments, but please ensure the tenant is properly assigned to a property."
                )
                # We'll allow proceeding without a tenancy, but create a record with a warning
                context['show_tenancy_warning'] = True
                
        except User.DoesNotExist:
            messages.error(request, 'Invalid tenant selected.')
            return redirect('landlord:payments')
    
    # Prepare context for the template
    context = {
        'tenant': tenant,
        'current_date': timezone.now().date(),
    }
    
    if request.method == 'POST':
        try:
            # Get form data
            tenant_id = request.POST.get('tenant')
            amount = request.POST.get('amount')
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            transaction_id = request.POST.get('transaction_id', '').strip()
            payment_period = request.POST.get('payment_period')
            months = request.POST.get('months', '1')
            notes = request.POST.get('notes', '').strip()
            
            # Basic validation
            if not all([tenant_id, amount, payment_date, payment_method, payment_period, months]):
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'landlord/record_payment.html', context)
                
            # Validate months is a positive integer
            try:
                months = int(months)
                if months < 1:
                    raise ValueError("Number of months must be at least 1")
            except (ValueError, TypeError):
                messages.error(request, 'Please enter a valid number of months.')
                return render(request, 'landlord/record_payment.html', context)
            
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError("Amount must be greater than zero")
            except (ValueError, TypeError):
                messages.error(request, 'Please enter a valid amount.')
                return render(request, 'landlord/record_payment.html', context)
            
            # Get the tenant and their active tenancy
            try:
                tenant = User.objects.get(id=tenant_id)
                # Try to get the most recent tenancy for this tenant
                tenancy = None
                all_tenancies = Tenancy.objects.filter(tenant=tenant, unit__in=units)
                
                if all_tenancies.exists():
                    # Get the most recent tenancy (based on last payment date)
                    tenancy = all_tenancies.latest('last_payment_date')
                    
                    # Check if the tenancy is active
                    if not tenancy.is_active:
                        messages.warning(
                            request,
                            'Note: This tenancy is currently inactive. ' \
                            'You can still record payments for this tenant.'
                        )
                else:
                    # If no tenancy exists, create a payment without a tenancy
                    messages.warning(
                        request,
                        'Note: This payment is not linked to any tenancy. ' \
                        'Please ensure the tenant is properly assigned to a property.'
                    )
                
                # Create and save the payment with correct field names
                # Create description with payment period and months
                period_description = f"{payment_period}"
                if months and int(months) > 1:
                    period_description += f" ({months} months)"
                if notes:
                    period_description += f": {notes}"
                
                payment_data = {
                    'amount': amount,
                    'date': payment_date,
                    'method': payment_method,
                    'transaction_id': transaction_id if transaction_id else None,
                    'description': period_description,
                    'status': 'Paid',
                    'created_by': request.user
                }
                
                # Only add tenancy if it exists
                if tenancy:
                    payment_data['tenancy'] = tenancy
                
                # Create the payment
                payment = Payment.objects.create(**payment_data)
                
                # Update tenancy payment information if tenancy exists
                if tenancy:
                    tenancy.last_payment_date = payment_date
                    tenancy.months_paid += int(months)
                    tenancy.save()
                
                # Create a notification for the tenant
                from communication.models import Notification
                from django.contrib.contenttypes.models import ContentType
                
                notification_message = f'Payment of TZS {amount:,.2f} has been recorded'
                if payment_period:
                    notification_message += f' for {payment_period}.'
                else:
                    notification_message += '.'
                
                # Get the content type for the Payment model
                payment_content_type = ContentType.objects.get_for_model(payment)
                
                # Create the notification with proper generic relation fields
                Notification.objects.create(
                    recipient=tenant,
                    title='Payment Recorded',
                    message=notification_message,
                    notification_type='payment_received',
                    content_type=payment_content_type,
                    object_id=payment.id
                )
                
                messages.success(
                    request, 
                    f'Successfully recorded payment of TZS {amount:,.2f} from {tenant.get_full_name() or tenant.username}'
                )
                return redirect('landlord:payments')
                
            except User.DoesNotExist:
                messages.error(request, 'Invalid tenant selected.')
            except Exception as e:
                messages.error(request, f'Error processing payment: {str(e)}')
                
        except Exception as e:
            messages.error(request, f'An unexpected error occurred: {str(e)}')
    
    # For GET requests or if there was an error, show the form
    return render(request, 'landlord/record_payment.html', context)
    
    return render(request, 'landlord/record_payment.html', context)


@login_required(login_url='home:index')
def debug_tenant_tenancies(request, tenant_id):
    """Debug view to check tenant's tenancies"""
    try:
        tenant = User.objects.get(id=tenant_id)
        properties = Property.objects.filter(landlord=request.user)
        units = Unit.objects.filter(property__in=properties)
        
        # Get all tenancies for this tenant across landlord's properties
        tenancies = Tenancy.objects.filter(
            tenant=tenant,
            unit__in=units
        ).select_related('unit', 'unit__property').order_by('-last_payment_date')
        
        current_date = timezone.now().date()
        
        context = {
            'tenant': tenant,
            'tenancies': tenancies,
            'current_date': current_date,
            'has_active_tenancy': any(
                t.is_active and t.last_payment_date is not None
                for t in tenancies
            )
        }
        return render(request, 'landlord/debug_tenancies.html', context)
        
    except User.DoesNotExist:
        messages.error(request, 'Tenant not found')
        return redirect('landlord:payments')


def notifications_view(request):
    """Notifications page - shows all system activities for the landlord"""
    # Get all properties owned by this landlord
    properties = Property.objects.filter(landlord=request.user)

    # Get all tenancies for this landlord's properties
    tenancies = Tenancy.objects.filter(unit__property__in=properties)

    # Collect all notifications/activities
    notifications = []

    # 1. New maintenance requests (unread/submitted recently)
    maintenance_requests = MaintenanceRequest.objects.filter(
        tenant__tenancies__unit__property__in=properties
    ).select_related('tenant').order_by('-submitted_at')[:10]

    for req in maintenance_requests:
        notifications.append({
            'type': 'maintenance',
            'title': f'New Maintenance Request from {req.tenant.get_full_name or req.tenant.username}',
            'message': f'{req.title} - {req.status}',
            'date': req.submitted_at,
            'icon': 'fas fa-tools',
            'color': 'warning',
            'url': f'/landlord/maintenance/{req.pk}/'
        })

    # 2. New messages from tenants
    messages = Message.objects.filter(
        recipient=request.user
    ).order_by('-sent_at')[:10]

    for msg in messages:
        notifications.append({
            'type': 'message',
            'title': f'New Message from {msg.sender.get_full_name or msg.sender.username}',
            'message': msg.subject,
            'date': msg.sent_at,
            'icon': 'fas fa-envelope',
            'color': 'info',
            'url': f'/landlord/messages/{msg.pk}/'
        })

    # 3. Recent payments
    payments = Payment.objects.filter(
        tenancy__unit__property__in=properties
    ).select_related('tenancy__tenant').order_by('-created_at')[:10]

    for payment in payments:
        notifications.append({
            'type': 'payment',
            'title': f'Payment Received from {payment.tenancy.tenant.get_full_name or payment.tenancy.tenant.username}',
            'message': f'TZS {payment.amount} - {payment.status}',
            'date': payment.created_at,
            'icon': 'fas fa-money-bill-wave',
            'color': 'success',
            'url': f'/landlord/payments/'
        })

    # 4. Tenancy status changes
    recent_tenancies = Tenancy.objects.filter(
        unit__property__in=properties
    ).select_related('tenant', 'unit__property').order_by('-start_date')[:5]

    for tenancy in recent_tenancies:
        status_text = "Active" if tenancy.is_active else "Inactive"
        notifications.append({
            'type': 'tenancy',
            'title': f'Tenancy for {tenancy.tenant.get_full_name or tenancy.tenant.username}',
            'message': f'Unit {tenancy.unit.unit_number} at {tenancy.unit.property.name} - {status_text}',
            'date': tenancy.start_date,
            'icon': 'fas fa-home',
            'color': 'primary',
            'url': f'/landlord/tenants/'
        })

    # Sort all notifications by date (most recent first)
    # Convert all dates to datetime for consistent sorting
    for notification in notifications:
        if isinstance(notification['date'], date) and not isinstance(notification['date'], datetime):
            # This is a date object, convert to datetime
            notification['date'] = datetime.combine(notification['date'], datetime.min.time())
            notification['date'] = timezone.make_aware(notification['date'])
    
    notifications.sort(key=lambda x: x['date'], reverse=True)

    # Get summary counts
    unread_messages = Message.objects.filter(recipient=request.user, read_at__isnull=True).count()
    pending_maintenance = MaintenanceRequest.objects.filter(
        tenant__tenancies__unit__property__in=properties,
        status='Pending'
    ).count()
    recent_payments = Payment.objects.filter(
        tenancy__unit__property__in=properties,
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).count()

    context = {
        'notifications': notifications[:20],  # Show latest 20 notifications
        'unread_messages': unread_messages,
        'pending_maintenance': pending_maintenance,
        'recent_payments': recent_payments,
        'total_notifications': len(notifications)
    }
    return render(request, 'landlord/notifications.html', context)


@login_required(login_url='home:index')
def manage_documents(request):
    """
    Allow landlords to upload and manage documents for their properties.
    """
    try:
        # Get all properties for this landlord
        properties = Property.objects.filter(landlord=request.user)
        
        if request.method == 'POST':
            property_id = request.POST.get('property')
            document_type = request.POST.get('document_type')
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            file = request.FILES.get('file')
            
            # Validate required fields
            if not all([property_id, document_type, title, file]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('landlord:manage_documents')
            
            try:
                # Verify property belongs to landlord
                property_obj = get_object_or_404(Property, id=property_id, landlord=request.user)
                
                # Validate file type
                if not file.name.endswith('.pdf'):
                    messages.error(request, 'Only PDF files are allowed.')
                    return redirect('landlord:manage_documents')
                
                # Validate file size (10MB max)
                if file.size > 10 * 1024 * 1024:
                    messages.error(request, 'File size must not exceed 10MB.')
                    return redirect('landlord:manage_documents')
                
                # Create document
                document = Document.objects.create(
                    property=property_obj,
                    document_type=document_type,
                    title=title,
                    description=description,
                    file=file,
                    uploaded_by=request.user
                )
                
                messages.success(request, f'Document "{title}" uploaded successfully! All tenants will be able to download it.')
                return redirect('landlord:manage_documents')
                
            except Property.DoesNotExist:
                messages.error(request, 'Invalid property selected.')
                return redirect('landlord:manage_documents')
            except Exception as e:
                messages.error(request, f'Error uploading document: {str(e)}')
                return redirect('landlord:manage_documents')
        
        # GET request - display documents
        documents = Document.objects.filter(
            property__landlord=request.user,
            is_active=True
        ).order_by('-uploaded_at')
        
        # Count statistics
        total_documents = documents.count()
        total_properties = properties.count()
        recent_count = documents.filter(
            uploaded_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        context = {
            'page_title': 'Manage Documents',
            'properties': properties,
            'documents': documents,
            'total_documents': total_documents,
            'total_properties': total_properties,
            'recent_count': recent_count,
        }
        
        return render(request, 'landlord/manage_documents.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading documents: {str(e)}')
        return redirect('landlord:dashboard')


@login_required(login_url='home:index')
def delete_document(request, document_id):
    """
    Delete a document (soft delete by marking is_active=False).
    """
    try:
        document = get_object_or_404(Document, id=document_id, property__landlord=request.user)
        
        # Soft delete
        document.is_active = False
        document.save()
        
        messages.success(request, f'Document "{document.title}" has been deleted.')
        return redirect('landlord:manage_documents')
        
    except Exception as e:
        messages.error(request, f'Error deleting document: {str(e)}')
        return redirect('landlord:manage_documents')
