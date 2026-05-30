from django.contrib import admin
from .models import EventLog

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'event_type', 'details')
    list_filter = ('event_type',)
    search_fields = ('event_type', 'details')
