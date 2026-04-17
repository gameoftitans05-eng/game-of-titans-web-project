from django.db import models
import re
import uuid

# Create your models here.
class GymModel(models.Model):
    name = models.CharField(max_length=250, null=True, blank=False)
    gym_id = models.CharField(max_length=50, null=True, blank=True)
    contact_number = models.CharField(unique=True, max_length=15, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    website = models.TextField(null=True, blank=True)
    location = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def _clean_name_prefix(self):
        # Keep only uppercase letters + digits, remove spaces/special chars
        cleaned = re.sub(r'[^A-Z0-9]', '', self.name.upper())
        # Take first 6 characters (we'll slice to 6 later if needed)
        prefix = cleaned[:6]

        # Minimum length fallback (if name is very short/empty after cleaning)
        if len(prefix) < 3:
            prefix = (prefix + "GYMXXX")[:6]

        return prefix

    def save(self, *args, **kwargs):
        if not self.gym_id:
            # First save without gym_id to get the pk
            if not self.pk:
                super().save(*args, **kwargs)  # save once to generate id/pk

            # Now generate gym_id using the pk
            prefix = self._clean_name_prefix()[:6]  # max 6 chars
            pk_part = f"{self.pk:04d}"[-4:]  # last 4 digits of pk, zero-padded
            self.gym_id = (prefix + pk_part)[:10]  # exactly 10 chars

            # Second save → now with gym_id
            super().save(update_fields=['gym_id'])

        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.gym_id})"


class MemberModel(models.Model):
    gym = models.ForeignKey(
        'GymModel',
        on_delete=models.SET_NULL,  # Changed: better for individuals (don't delete member if gym is deleted)
        related_name='gym_member',
        null=True,
        blank=True,
        help_text="Gym this member belongs to (null for independent participants)"
    )
    name = models.CharField(max_length=250, null=True, blank=False)
    email = models.EmailField(unique=False, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    # ✅ NEW FIELD
    referred_by = models.ForeignKey(
        'ReferUserModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_members'
    )
    gender = models.CharField(
        max_length=20,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other'),
                 ('prefer_not_to_say', 'Prefer not to say')],
        null=True,
        blank=True,
        help_text="Participant's gender (optional)"
    )
    registration_type = models.CharField(
        max_length=20,
        choices=[
            ('gym_member', 'Gym Member'),
            ('individual', 'Independent / Individual'),
        ],
        default='individual',
        help_text="Whether this member is part of a gym or registering independently"
    )
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Member"
        verbose_name_plural = "Members"
        ordering = ['-created_at']

    def __str__(self):
        gym_part = f" ({self.gym.gym_id})" if self.gym else ""
        return f"{self.name or 'Unnamed'} - {self.registration_type}{gym_part}"

    def is_individual(self):
        return self.registration_type == 'individual'

    def is_gym_member(self):
        return self.registration_type == 'gym_member'


class EventModel(models.Model):
    name = models.CharField(max_length=250, null=False, blank=False)
    location = models.JSONField(null=True, blank=True)
    participation_amount = models.IntegerField(default=0)
    schedule_on = models.DateTimeField(null=True, blank=True)
    from_date = models.DateTimeField(null=True, blank=True)
    to_date = models.DateTimeField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class ParticipatedMemberModel(models.Model):
    event = models.ForeignKey('EventModel', on_delete=models.CASCADE, related_name='event_participated')
    member = models.ForeignKey('MemberModel', on_delete=models.CASCADE, related_name='member_participated')
    gym = models.ForeignKey(
        'GymModel',
        on_delete=models.SET_NULL,
        related_name='gym_participated',
        null=True,
        blank=True,
        help_text="Gym of the participant (copied from MemberModel for faster queries / historical data)"
    )

    # ✅ NEW FIELD
    referred_by = models.ForeignKey(
        'ReferUserModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_participants'
    )

    registration_type = models.CharField(
        max_length=20,
        choices=[
            ('gym_member', 'Gym Member'),
            ('individual', 'Independent / Individual'),
        ],
        default='individual',
        help_text="Registration type at the time of participation"
    )
    mail_sent = models.BooleanField(default=True)
    registration_id = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class PaymentOrderModel(models.Model):
    participate_member = models.ForeignKey('ParticipatedMemberModel', on_delete=models.CASCADE,
                                           related_name='participated_member_order', null=True, blank=True)
    event = models.ForeignKey('EventModel', on_delete=models.SET_NULL, null=True, blank=True , related_name='event_order')
    member = models.ForeignKey('MemberModel', on_delete=models.SET_NULL, null=True, blank=True, related_name='member_order')
    order_id = models.CharField(max_length=30, unique=True, null=False, blank=True)
    payment_type = models.CharField(max_length=20, default='UPI', null=False, blank=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pg_response = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='CREATED', null=False, blank=False)
    cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class TransactionModel(models.Model):
    order = models.ForeignKey('PaymentOrderModel', on_delete=models.CASCADE, related_name='order_transaction')
    transaction_id = models.CharField(max_length=20, null=False, blank=False)
    status = models.CharField(max_length=50, null=True, blank=True, default='CREATED')
    pg_response = models.TextField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class SponsorModel(models.Model):
    name = models.CharField(max_length=250, null=False, blank=False)
    company = models.CharField(max_length=250, null=False, blank=False)
    email = models.EmailField(null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    rejected = models.BooleanField(default=False)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)


class ReferUserModel(models.Model):
    name = models.CharField(max_length=250)
    email = models.EmailField(null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)

    # Optional Gym link
    gym = models.ForeignKey(
        'GymModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gym_referrers'
    )

    refer_code = models.CharField(max_length=12, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    def generate_refer_code(self):
        # Example: GOT + random 6 chars
        return f"GOT{uuid.uuid4().hex[:6].upper()}"

    def save(self, *args, **kwargs):
        if not self.refer_code:
            self.refer_code = self.generate_refer_code()
        super().save(*args, **kwargs)

    def total_referrals(self):
        return self.referred_participants.count()

    def __str__(self):
        return f"{self.name} ({self.refer_code})"

