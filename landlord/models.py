from django.db import models
from django.conf import settings

# Create your models here.

class PaymentMethod(models.Model):
    landlord = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    preferred_method = models.CharField(max_length=50, choices=[('Bank Transfer', 'Bank Transfer'), ('Mobile Money', 'Mobile Money'), ('Cheque', 'Cheque')])
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bank_name} ({self.account_number})"

class NotificationPreference(models.Model):
    landlord = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    email_alerts = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

class SystemPreference(models.Model):
    landlord = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    dashboard_theme = models.CharField(max_length=10, choices=[('Light', 'Light'), ('Dark', 'Dark')], default='Light')
    language = models.CharField(max_length=20, default='English')
    updated_at = models.DateTimeField(auto_now=True)
