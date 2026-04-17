# admin.py
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from import_export import resources, fields
from import_export.formats.base_formats import XLSX
from import_export.admin import ExportMixin


class CustomAdminSite(AdminSite):
    site_header = "Game of Titans - Admin Panel"  # ← big blue header
    site_title = "GoT Admin"  # ← browser tab title
    index_title = "Welcome to Game of Titans Dashboard"


# Create instance
custom_admin_site = CustomAdminSite(name='custom_admin')

from .models import (
    GymModel,
    MemberModel,
    EventModel,
    ParticipatedMemberModel,
    PaymentOrderModel,
    TransactionModel, SponsorModel, ReferUserModel,
)


class GymResource(resources.ModelResource):
    sl_no = fields.Field(column_name='Sl No', readonly=True)
    gym_name = fields.Field(attribute='name', column_name='Gym Name')
    contact_person = fields.Field(attribute='name', column_name='Contact person')  # if you have separate field, change it
    email_id = fields.Field(attribute='email', column_name='Email ID')
    gym_registered_id = fields.Field(attribute='gym_id', column_name='Gym Registered Id')
    phone_no = fields.Field(attribute='contact_number', column_name='Phone No')

    class Meta:
        model = GymModel
        fields = ('sl_no', 'gym_name', 'contact_person', 'email_id', 'gym_registered_id', 'phone_no')
        export_order = ('sl_no', 'gym_name', 'contact_person', 'email_id', 'gym_registered_id', 'phone_no')

    def dehydrate_sl_no(self, gym):
        # Assign serial number automatically
        # Note: for all exported rows, serial will start from 1
        if not hasattr(self, '_counter'):
            self._counter = 1
        value = self._counter
        self._counter += 1
        return value

@admin.register(GymModel)
class GymModelAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        'name',
        'gym_id',
        'contact_number',
        'email',
        'created_at',
        'gym_members_count',
    )
    resource_class = GymResource
    formats = [XLSX]
    list_filter = ('created_at',)
    search_fields = ('name', 'gym_id', 'email', 'contact_number')
    readonly_fields = ('created_at', 'updated_at', 'gym_id')
    ordering = ('-created_at',)
    list_per_page = 20

    fieldsets = (
        (None, {
            'fields': ('name', 'gym_id', 'email', 'contact_number')
        }),
        ('Additional Info', {
            'fields': ('website', 'location'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def gym_members_count(self, obj):
        return obj.gym_member.count()

    gym_members_count.short_description = "Members"


class MemberResource(resources.ModelResource):
    sl_no = fields.Field(column_name='Sl No', readonly=True)
    member_name = fields.Field(attribute='name', column_name='Member Name')
    email = fields.Field(attribute='email', column_name='Email')
    contact_number = fields.Field(attribute='contact_number', column_name='Contact Number')
    gender = fields.Field(attribute='gender', column_name='Gender')
    registration_type = fields.Field(attribute='registration_type', column_name='Registration Type')

    gym_name = fields.Field(column_name='Gym Name')
    gym_id = fields.Field(column_name='Gym ID')
    gym_contact = fields.Field(column_name='Gym Contact')

    participated = fields.Field(column_name='Participated')
    events = fields.Field(column_name='Events Participated')

    class Meta:
        model = MemberModel
        fields = (
            'sl_no',
            'member_name',
            'email',
            'contact_number',
            'gender',
            'registration_type',
            'gym_name',
            'gym_id',
            'gym_contact',
            'participated',
            'events',
        )
        export_order = fields

    # Serial number
    def dehydrate_sl_no(self, obj):
        if not hasattr(self, '_counter'):
            self._counter = 1
        val = self._counter
        self._counter += 1
        return val

    # Gym Details
    def dehydrate_gym_name(self, obj):
        return obj.gym.name if obj.gym else "N/A"

    def dehydrate_gym_id(self, obj):
        return obj.gym.gym_id if obj.gym else "N/A"

    def dehydrate_gym_contact(self, obj):
        return obj.gym.contact_number if obj.gym else "N/A"

    # Participation
    def dehydrate_participated(self, obj):
        return "Yes" if obj.member_participated.exists() else "No"

    # Events list
    def dehydrate_events(self, obj):
        events = obj.member_participated.select_related('event')
        return ", ".join([p.event.name for p in events if p.event]) or "N/A"


@admin.register(MemberModel)
class MemberModelAdmin(ExportMixin, admin.ModelAdmin):
    list_display = (
        'name',
        'gym',
        'email',
        'gender',
        'registration_type',
        'contact_number',
        'created_at',
    )

    resource_class = MemberResource  # ✅ ADD THIS
    formats = [XLSX]

    list_filter = ('gym', 'gender', 'created_at')
    search_fields = ('name', 'email', 'contact_number', 'gym__name', 'gym__gym_id')
    raw_id_fields = ('gym',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(EventModel)
class EventModelAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'schedule_on',
        'active',
        'created_at',
        'participants_count',
    )
    list_filter = ('active', 'schedule_on', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'schedule_on'
    ordering = ('-schedule_on',)

    def participants_count(self, obj):
        return obj.event_participated.count()

    participants_count.short_description = "Participants"


@admin.register(ParticipatedMemberModel)
class ParticipatedMemberModelAdmin(admin.ModelAdmin):
    list_display = (
        'member_name',
        'event_name',
        'gym_name',
        'referred_by',
        'mail_sent',
        'registration_id',
        'registration_type',
        'created_at',
    )
    list_filter = ('mail_sent', 'event__active', 'member__gym__name', 'referred_by__refer_code', 'created_at')
    search_fields = (
        'member__name',
        'event__name',
        'member__gym__name',
        'registration_id',
        'referred_by__refer_code',
    )
    raw_id_fields = ('event', 'member')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    def member_name(self, obj):
        return obj.member.name if obj.member else "-"

    member_name.short_description = "Member"

    def event_name(self, obj):
        return obj.event.name if obj.event else "-"

    event_name.short_description = "Event"

    def gym_name(self, obj):
        return obj.member.gym.name if obj.member and obj.member.gym else "-"

    gym_name.short_description = "Gym"


@admin.register(PaymentOrderModel)
class PaymentOrderModelAdmin(admin.ModelAdmin):
    list_display = (
        'order_id',
        'participate_member',
        'payment_type',
        'status',
        'cancelled',
        'created_at',
    )
    list_filter = ('status', 'payment_type', 'cancelled', 'created_at')
    search_fields = ('order_id', 'participate_member__registration_id')
    readonly_fields = ('created_at', 'updated_at', 'pg_response')
    ordering = ('-created_at',)
    list_per_page = 25


@admin.register(TransactionModel)
class TransactionModelAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id',
        'order',
        'status',
        'cancelled',
        'created_at',
    )
    list_filter = ('status', 'cancelled', 'created_at')
    search_fields = ('transaction_id', 'order__order_id')
    readonly_fields = ('created_at', 'updated_at', 'pg_response')
    ordering = ('-created_at',)
    list_per_page = 25


@admin.register(SponsorModel)
class SponsorModelAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company',
        'email',
        'contact_number',
        'rejected',
        'created_at',
    )
    list_filter = ('rejected', 'created_at')
    search_fields = ('name', 'company', 'email', 'contact_number')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('name', 'company', 'email', 'contact_number', 'rejected')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReferUserModel)
class ReferUserModelAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'refer_code',
        'gym',
        'contact_number',
        'total_referrals_count',
        'created_at',
    )

    search_fields = ('name', 'refer_code', 'contact_number')
    list_filter = ('gym', 'created_at')
    readonly_fields = ('refer_code', 'created_at', 'updated_at')

    def total_referrals_count(self, obj):
        return obj.referred_participants.count()

    total_referrals_count.short_description = "Total Referrals"


custom_admin_site.register(GymModel, GymModelAdmin)
custom_admin_site.register(MemberModel, MemberModelAdmin)
custom_admin_site.register(EventModel, EventModelAdmin)
custom_admin_site.register(ParticipatedMemberModel, ParticipatedMemberModelAdmin)
custom_admin_site.register(PaymentOrderModel, PaymentOrderModelAdmin)
custom_admin_site.register(TransactionModel, TransactionModelAdmin)
custom_admin_site.register(SponsorModel, SponsorModelAdmin)
custom_admin_site.register(ReferUserModel, ReferUserModelAdmin)
