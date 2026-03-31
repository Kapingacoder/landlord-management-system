from django.urls import path
from . import views as landlord_views
from properties import views as properties_views

app_name = 'landlord'

urlpatterns = [
    # URL ya Dashboard
    path('dashboard/', landlord_views.dashboard, name='dashboard'),

    # URL ya Home Summary
    path('home/', landlord_views.home_summary, name='home'),

    # New feature pages
    path('properties/', landlord_views.properties_view, name='properties'),
    path('tenants/', landlord_views.tenants_view, name='tenants'),
    path('payments/', landlord_views.payments_view, name='payments'),
    path('messages/', landlord_views.messages_view, name='messages'),
    path('maintenance/', landlord_views.maintenance_view, name='maintenance'),
    path('notifications/', landlord_views.notifications_view, name='notifications'),

    # URL ya Reports
    path('reports/', landlord_views.reports, name='reports'),

    # URL kuu ya Settings
    path('settings/', landlord_views.settings, name='settings'),

    # URLs za Properties zikitoka kwenye 'properties' app
    # Hizi ndizo zinazotatua kosa la NoReverseMatch
    path('property/<int:pk>/', properties_views.property_detail, name='landlord_property_detail'),
    path('property/<int:pk>/edit/', properties_views.edit_property, name='landlord_edit_property'),
    path('property/<int:pk>/delete/', properties_views.delete_property, name='landlord_delete_property'),

    # URL za ku-export data (hizi zinabaki kwenye landlord app)
    path('export/payments/csv/', landlord_views.export_payments_csv, name='export_payments_csv'),
    path('export/payments/pdf/', landlord_views.export_payments_pdf, name='export_payments_pdf'),

    # URLs za Settings (hizi zinabaki kwenye landlord app)
    path('settings/profile/', landlord_views.profile_manage, name='landlord_profile_manage'),
    path('settings/payment-methods/', landlord_views.payment_methods_manage, name='landlord_payment_methods_manage'),
    path('settings/notification-preferences/', landlord_views.notification_preferences_manage, name='landlord_notification_preferences_manage'),
    path('settings/security/', landlord_views.security_settings_manage, name='landlord_security_settings_manage'),
    
    # URL zingine za properties ambazo template inahitaji
    path('property/add/', properties_views.add_property, name='add_property'),


    # Maintenance URLs
    path('maintenance/<int:pk>/', landlord_views.maintenance_detail, name='maintenance_detail'),
    
    # Record Payment URL
    path('payments/record/', landlord_views.record_payment, name='record_payment'),
    
    # Documents Management
    path('documents/', landlord_views.manage_documents, name='manage_documents'),
    path('documents/<int:document_id>/delete/', landlord_views.delete_document, name='delete_document'),


    # Message Management URLs
    path('messages/<int:pk>/', landlord_views.message_detail, name='message_detail'),
    path('messages/send/', landlord_views.send_message, name='send_message'),
    
    # Payment History API
    path('payment-history/', landlord_views.payment_history_landlord, name='payment_history_landlord'),
    
    # Debug URL for tenant tenancies
    path('debug/tenant/<int:tenant_id>/tenancies/', landlord_views.debug_tenant_tenancies, name='debug_tenant_tenancies'),
]
