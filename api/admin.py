from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Gym,
    Athlete,
    Participation,
    PaymentOrder,
    GOTEmployee,
    ReferUser,
    Sponsor,
    EmailLog,
    IncentiveConfig
)

from django.contrib import admin


class MyAdminSite(admin.AdminSite):
    site_header = "GOT Admin"
    site_title = "GOT Admin Portal"
    index_title = "GOT Admin"  # keep empty to remove "Site administration"


admin_site = MyAdminSite(name="myadmin")


# =========================================================
# GOT EMPLOYEE
# =========================================================
class GOTEmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "event_leg", "is_active", "created_at")
    search_fields = ("name", "code", "email", "phone")
    list_filter = ("city", "event_leg", "is_active")

    readonly_fields = ("code", "created_at")


# =========================================================
# GYM ADMIN (CRITICAL)
# =========================================================
class GymAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "state",
        "status",
        "is_mpcg",
        "titan_id",
        "got_employee",
        "created_at"
    )

    list_filter = ("status", "is_mpcg", "state", "event_leg")
    search_fields = ("name", "email", "phone", "titan_id")

    readonly_fields = (
        "titan_id",
        "is_mpcg",
        "created_at"
    )

    actions = ["approve_gym", "reject_gym"]

    def approve_gym(self, request, queryset):
        for gym in queryset:
            if gym.status != "approved" and not gym.is_mpcg:
                if not gym.titan_id:
                    gym.titan_id = gym.generate_titan_id()
                gym.status = "approved"
                gym.save()
        self.message_user(request, "Selected gyms approved.")

    def reject_gym(self, request, queryset):
        queryset.update(status="rejected")
        self.message_user(request, "Selected gyms rejected.")

    approve_gym.short_description = "Approve selected gyms"
    reject_gym.short_description = "Reject selected gyms"


# =========================================================
# ATHLETE ADMIN
# =========================================================
class AthleteAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "phone",
        "state",
        "city",
        "created_at"
    )

    search_fields = ("name", "email", "phone")
    list_filter = ("state", "city")

    readonly_fields = ("created_at",)


# =========================================================
# PARTICIPATION ADMIN (VERY IMPORTANT)
# =========================================================
class PaymentInline(admin.TabularInline):
    model = PaymentOrder
    extra = 0
    readonly_fields = ("order_id", "status", "created_at")


class ParticipationAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_id",
        "athlete",
        "gym",
        "event_leg",
        "payment_status",
        "retry_count",  # 🔥 NEW
        "is_confirmed",
        "created_at"
    )
    inlines = [PaymentInline]

    search_fields = ("tracking_id", "athlete__name", "athlete__email")
    list_filter = ("event_leg", "payment_status", "is_confirmed")

    readonly_fields = (
        "tracking_id",
        "athlete",
        "gym",
        "event_leg",
        "payment_status",
        "retry_count",  # 🔥 NEW
        "created_at"
    )

    def colored_status(self, obj):
        color = {
            "success": "green",
            "failed": "red",
            "pending": "orange",
            "expired": "gray"
        }.get(obj.payment_status, "black")

        return format_html(
            '<b style="color:{}">{}</b>',
            color,
            obj.payment_status
        )

    colored_status.short_description = "Status"

    actions = ["confirm_participation", "mark_failed"]

    def confirm_participation(self, request, queryset):
        queryset.update(is_confirmed=True, payment_status="success")
        self.message_user(request, "Marked as confirmed.")

    def mark_failed(self, request, queryset):
        queryset.update(payment_status="failed")
        self.message_user(request, "Marked as failed.")

    confirm_participation.short_description = "Mark as SUCCESS"
    mark_failed.short_description = "Mark as FAILED"


# =========================================================
# PAYMENT ORDER ADMIN
# =========================================================
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "athlete",
        "participation",
        "amount",
        "status",
        "retry_of",  # 🔥 NEW
        "created_at"
    )

    search_fields = ("order_id", "athlete__name", "athlete__email")
    list_filter = ("status",)

    readonly_fields = (
        "order_id",
        "athlete",
        "participation",
        "amount",
        "status",
        "retry_of",
        "gateway_response",
        "created_at"
    )

    actions = ["mark_success", "mark_failed", "mark_expired"]

    def mark_success(self, request, queryset):
        queryset.update(status="success")
        self.message_user(request, "Orders marked as SUCCESS")

    def mark_failed(self, request, queryset):
        queryset.update(status="failed")
        self.message_user(request, "Orders marked as FAILED")

    def mark_expired(self, request, queryset):
        queryset.update(status="expired")
        self.message_user(request, "Orders marked as EXPIRED")


# =========================================================
# REFER USER
# =========================================================
class ReferUserAdmin(admin.ModelAdmin):
    list_display = ("name", "refer_code", "gym", "created_at")
    search_fields = ("name", "refer_code")
    readonly_fields = ("refer_code", "created_at")


# =========================================================
# SPONSOR
# =========================================================
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "email", "phone", "created_at")
    search_fields = ("company", "name", "email")
    readonly_fields = ("created_at",)


# =========================================================
# EMAIL LOG (IMPORTANT)
# =========================================================
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "to_email",
        "subject",
        "status",
        "related_gym",
        "related_athlete",
        "created_at"
    )

    list_filter = ("status",)
    search_fields = ("to_email", "subject")

    readonly_fields = (
        "to_email",
        "subject",
        "status",
        "related_gym",
        "related_athlete",
        "created_at"
    )



class IncentiveConfigAdmin(admin.ModelAdmin):
    list_display = ("gym_rate", "employee_rate", "mpcg_rate", "is_active", "updated_at")

    def has_add_permission(self, request):
        # Only one config allowed
        return not IncentiveConfig.objects.exists()


admin_site.register(GOTEmployee, GOTEmployeeAdmin)
admin_site.register(Gym, GymAdmin)
admin_site.register(Athlete, AthleteAdmin)
admin_site.register(Participation, ParticipationAdmin)
admin_site.register(PaymentOrder, PaymentOrderAdmin)
admin_site.register(ReferUser, ReferUserAdmin)
admin_site.register(Sponsor, SponsorAdmin)
admin_site.register(EmailLog, EmailLogAdmin)
admin_site.register(IncentiveConfig, IncentiveConfigAdmin)
