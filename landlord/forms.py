from django import forms
from django.contrib.auth import get_user_model
from .models import PaymentMethod, NotificationPreference, SystemPreference

User = get_user_model()

# Profile settings form for landlord, includes profile picture and phone
class ProfileForm(forms.ModelForm):
    profile_picture = forms.ImageField(required=False)
    phone = forms.CharField(required=False, max_length=20, label='Phone')
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'profile_picture']
        # This form allows updating landlord profile info

# Payment method form for add/edit
class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ['bank_name', 'account_number', 'preferred_method']
        # Used for adding/editing landlord payment methods

# Notification preferences form
class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ['email_alerts', 'sms_alerts']
        # Used for toggling notification settings

# System preferences form
class SystemPreferenceForm(forms.ModelForm):
    THEME_CHOICES = [
        ('Light', 'Light Theme'),
        ('Dark', 'Dark Theme'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('sw', 'Swahili'),
    ]
    
    dashboard_theme = forms.ChoiceField(
        choices=THEME_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
            'onchange': 'updateTheme(this.value)'
        }),
        label='Dashboard Theme',
        required=True
    )
    
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Language',
        required=True
    )
    
    class Meta:
        model = SystemPreference
        fields = ['dashboard_theme', 'language']
        # Used for dashboard theme and language selection
