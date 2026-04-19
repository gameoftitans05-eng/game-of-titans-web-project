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
    EmailLog
)


# =========================================================
# GOT EMPLOYEE
# =========================================================
@admin.register(GOTEmployee)
class GOTEmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "event_leg", "is_active", "created_at")
    search_fields = ("name", "code", "email", "phone")
    list_filter = ("city", "event_leg", "is_active")

    readonly_fields = ("code", "created_at")


# =========================================================
# GYM ADMIN (CRITICAL)
# =========================================================
@admin.register(Gym)
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
@admin.register(Athlete)
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
@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = (
        "tracking_id",
        "athlete",
        "gym",
        "event_leg",
        "payment_status",
        "is_confirmed",
        "created_at"
    )

    search_fields = ("tracking_id", "athlete__name", "athlete__email")
    list_filter = ("event_leg", "payment_status", "is_confirmed")

    readonly_fields = (
        "tracking_id",
        "athlete",
        "gym",
        "event_leg",
        "created_at"
    )

    actions = ["confirm_participation"]

    def confirm_participation(self, request, queryset):
        queryset.update(is_confirmed=True)
        self.message_user(request, "Selected participations confirmed.")

    confirm_participation.short_description = "Confirm selected participations"


# =========================================================
# PAYMENT ORDER ADMIN
# =========================================================
@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "athlete",
        "amount",
        "status",
        "created_at"
    )

    search_fields = ("order_id", "athlete__name", "athlete__email")
    list_filter = ("status",)

    readonly_fields = (
        "order_id",
        "athlete",
        "amount",
        "gateway_response",
        "created_at"
    )


# =========================================================
# REFER USER
# =========================================================
@admin.register(ReferUser)
class ReferUserAdmin(admin.ModelAdmin):
    list_display = ("name", "refer_code", "gym", "created_at")
    search_fields = ("name", "refer_code")
    readonly_fields = ("refer_code", "created_at")


# =========================================================
# SPONSOR
# =========================================================
@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("company", "name", "email", "phone", "created_at")
    search_fields = ("company", "name", "email")
    readonly_fields = ("created_at",)


# =========================================================
# EMAIL LOG (IMPORTANT)
# =========================================================
@admin.register(EmailLog)
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
