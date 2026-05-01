from django.db import models
import uuid
import random

from django.db.models import Q

# =========================================
# CONSTANTS
# =========================================
MPCG_STATES = ["Madhya Pradesh", "Chhattisgarh"]


# =========================================
# GOT EMPLOYEE / USHER
# =========================================
class GOTEmployee(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=20, unique=True)  # GOT-EMP-XXXX
    city = models.CharField(max_length=100)
    event_leg = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        return f"GOT-EMP-{random.randint(1000, 9999)}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


# =========================================
# GYM
# =========================================
class Gym(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('manager', 'Manager'),
        ('coach', 'Head Coach'),
        ('other', 'Other'),
    ]

    EVENT_CHOICES = [
        ('mumbai', 'Mumbai May 23'),
        ('delhi', 'Delhi Sep 19'),
        ('bengaluru', 'Bengaluru Feb 6'),
    ]

    # BASIC
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    email = models.EmailField()
    phone = models.CharField(max_length=15)

    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()

    active_members = models.CharField(max_length=50)
    instagram = models.CharField(max_length=255, blank=True, null=True)

    expected_athletes = models.CharField(max_length=50)
    event_leg = models.CharField(max_length=50, choices=EVENT_CHOICES)

    got_employee = models.ForeignKey(
        GOTEmployee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # CORE SYSTEM
    titan_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    is_mpcg = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )

    is_confirmed_by_employee = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def generate_titan_id(self):
        return f"TITAN-{random.randint(1000, 9999)}"

    def save(self, *args, **kwargs):

        # MPCG LOGIC
        if self.state in MPCG_STATES:
            self.is_mpcg = True
            self.status = 'pending'
        else:
            self.is_mpcg = False
            self.status = 'approved'

        # TITAN ID ONLY FOR NON-MPCG
        if not self.is_mpcg and not self.titan_id:
            self.titan_id = self.generate_titan_id()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.titan_id or 'Pending'})"


# =========================================
# ATHLETE
# =========================================
class Athlete(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    REG_TYPE = [
        ('gym', 'Gym Participant'),
        ('individual', 'Individual'),
    ]

    EVENT_CHOICES = Gym.EVENT_CHOICES

    # BASIC
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    registration_type = models.CharField(max_length=20, choices=REG_TYPE)

    gym = models.ForeignKey(
        Gym,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    titan_id_input = models.CharField(max_length=20, blank=True, null=True)

    event_leg = models.CharField(max_length=50, choices=EVENT_CHOICES)

    got_employee = models.ForeignKey(
        GOTEmployee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    referral_code = models.CharField(max_length=50, blank=True, null=True)

    is_confirmed_by_employee = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        # MPCG LOGIC
        if self.state in MPCG_STATES:
            self.gym = None
            self.titan_id_input = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.email})"


# =========================================
# PARTICIPATION
# =========================================
class Participation(models.Model):

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("expired", "Expired"),  # 🔥 NEW (important)
    ]

    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE)
    gym = models.ForeignKey(Gym, on_delete=models.SET_NULL, null=True, blank=True)

    event_leg = models.CharField(max_length=50)
    season = models.CharField(max_length=20, default="S1")

    tracking_id = models.CharField(max_length=20, unique=True)

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )

    is_confirmed = models.BooleanField(default=False)

    retry_count = models.IntegerField(default=0)  # 🔥 NEW (important)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["athlete", "event_leg"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["athlete", "event_leg"],
                condition=Q(payment_status="success"),
                name="unique_success_participation"
            )
        ]

# =========================================
# PAYMENT ORDER
# =========================================
class PaymentOrder(models.Model):

    STATUS_CHOICES = [
        ("created", "Created"),
        ("pending", "Pending"),   # 🔥 NEW
        ("success", "Success"),
        ("failed", "Failed"),
        ("expired", "Expired"),  # 🔥 NEW
    ]

    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE)
    participation = models.ForeignKey(Participation, null=True, on_delete=models.CASCADE)

    order_id = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=888)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created"
    )

    retry_of = models.ForeignKey(   # 🔥 NEW (track retries)
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    gateway_response = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["athlete", "status"]),
        ]

# =========================================
# TRANSACTION
# =========================================
class Transaction(models.Model):
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE)

    transaction_id = models.CharField(max_length=50)
    status = models.CharField(max_length=50)

    gateway_response = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.transaction_id


# =========================================
# REFERRAL USER
# =========================================
class ReferUser(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    gym = models.ForeignKey(
        Gym,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    refer_code = models.CharField(max_length=12, unique=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def generate_code(self):
        return f"GOT{uuid.uuid4().hex[:6].upper()}"

    def save(self, *args, **kwargs):
        if not self.refer_code:
            self.refer_code = self.generate_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.refer_code})"


# =========================================
# SPONSOR (UNCHANGED)
# =========================================
class Sponsor(models.Model):
    name = models.CharField(max_length=255)
    company = models.CharField(max_length=255)

    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    message = models.TextField(blank=True, null=True)

    rejected = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company


# =========================================
# EMAIL LOG (IMPORTANT FOR PDF FLOW)
# =========================================
class EmailLog(models.Model):
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed')
        ],
        default='pending'
    )

    related_gym = models.ForeignKey(Gym, on_delete=models.SET_NULL, null=True, blank=True)
    related_athlete = models.ForeignKey(Athlete, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class IncentiveConfig(models.Model):
    gym_rate = models.IntegerField(null=True, blank=True)
    employee_rate = models.IntegerField(null=True, blank=True)
    mpcg_rate = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Active Incentive Config"
