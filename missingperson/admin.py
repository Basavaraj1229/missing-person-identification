from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import MissingPerson, Location
from django.utils import timezone


UserAdmin.fieldsets = [
    (None, {'fields': ('username', 'email', 'is_staff', 'is_active')}),
    ('Permissions', {'fields': ('groups', 'user_permissions')}),
    ('Important dates', {'fields': ('last_login', 'date_joined')}),
]

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
# Define an inline admin interface for Location
class LocationInline(admin.TabularInline):
    model = Location
    extra = 1  # This will allow the admin to add multiple locations for each MissingPerson
    fields = ('latitude', 'longitude', 'detected_at')  # Fields for the inline form

# Define the admin interface for MissingPerson
class MissingPersonAdmin(admin.ModelAdmin):
    # Define which fields to display in the list view
    list_display = ('first_name', 'last_name', 'status', 'approval', 'aadhar_number', 'missing_from')
    list_filter = ('status', 'approval')  # Allows filtering by status and approval
    search_fields = ('first_name', 'last_name', 'aadhar_number')  # Adds search functionality

    # Define the fields shown in the form view
    fields = ('first_name', 'last_name', 'father_name', 'date_of_birth', 'address', 'email',
              'phone_number', 'aadhar_number', 'image', 'missing_from', 'gender', 'status', 'approval')

    # Make 'status' and 'approval' fields read-only for non-admin users
    readonly_fields = []

    # Ensure 'status' and 'approval' can only be updated by the admin user
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:  # Only admins can change these fields
            obj.status = obj.status  # Keep the existing status
            obj.approval = obj.approval  # Keep the existing approval status

        # Check if the status is being updated to 'found' and send an email
        if obj.status == 'Found':
            # Prepare the email content for the 'found' status update
            current_time = timezone.now().strftime('%d-%m-%Y %H:%M')
            context = {
                "first_name": obj.first_name,
                "last_name": obj.last_name,
                "fathers_name": obj.father_name,
                "aadhar_number": obj.aadhar_number,
                "missing_from": obj.missing_from,
                "date_time": current_time,
            }

            # Render the email content using the 'foundmail.html' template
            html_message = render_to_string('foundmail.html', context)

            # Send the email to the person's email address
            send_mail(
                subject='Case Closed: Missing Person Found',
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[obj.email],  # Send the email to the person who reported the case
                html_message=html_message
            )

        # Call the original save_model method to handle the rest of the saving process
        super().save_model(request, obj, form, change)

    # Include related 'Location' details within the 'MissingPerson' detail view
    inlines = [LocationInline]  # Add LocationInline here, with proper class reference

# Register the 'MissingPerson' model with its custom admin view
admin.site.register(MissingPerson, MissingPersonAdmin)

# Register the 'Location' model
admin.site.register(Location)  # Registering Location without custom admin (unless needed)
