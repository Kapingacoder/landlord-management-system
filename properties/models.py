from django.db import models
from django.conf import settings

class Property(models.Model):
    """Model for managing rental properties"""
    
    # Status choices for property
    STATUS_CHOICES = [
        ('vacant', 'Vacant'),
        ('occupied', 'Occupied'),
        ('pending', 'Pending Inspection'),
        ('maintenance', 'Under Maintenance'),
    ]
    
    # Landlord who owns this property
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'landlord'}
    )
    
    # Basic Property Information
    name = models.CharField(max_length=255, help_text="e.g., House 1, Apartment 5B")
    address = models.TextField(help_text="Full address of the property")
    location = models.CharField(max_length=255, blank=True, help_text="Location/Area name")
    description = models.TextField(blank=True, help_text="Detailed description of the property")
    
    # Property Details
    rooms = models.IntegerField(default=1, help_text="Number of rooms")
    rent = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monthly rent amount")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='vacant')
    
    # Utilities
    utilities = models.CharField(max_length=255, blank=True, help_text="e.g., Water, Electricity, Wi-Fi")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Properties'

    def __str__(self):
        return self.name

class Unit(models.Model):
    """Model for individual units within a property"""
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=50, help_text="e.g., A1, B2, Room 5")
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_occupied = models.BooleanField(default=False)
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_type': 'tenant'}
    )

    def __str__(self):
        return f"{self.property.name} - {self.unit_number}"