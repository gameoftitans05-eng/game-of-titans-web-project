from datetime import timedelta
from django.utils import timezone

from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings

from api.models import Participation
from api.services.notifications import send_internal_alert

REGISTRATIONS_EMAIL = getattr(settings, 'REGISTRATIONS_EMAIL', 'registrations@gameoftitans.in')
OFFICE_EMAIL = getattr(settings, 'OFFICE_EMAIL', 'office@gameoftitans.in')
ADMIN_EMAIL = getattr(settings, 'ADMIN_EMAIL', 'admin@gameoftitans.in')

INTERNAL_CC = [REGISTRATIONS_EMAIL, OFFICE_EMAIL]

def send_got_email(subject, html_content, to_email, gym=None, athlete=None, extra_cc=None):
    from api.models import EmailLog

    text = strip_tags(html_content)

    cc_list = INTERNAL_CC.copy()
    if extra_cc:
        cc_list += extra_cc

    #  CREATE LOG ENTRY (PENDING)
    log = EmailLog.objects.create(
        to_email=to_email,
        subject=subject,
        status="pending",
        related_gym=gym,
        related_athlete=athlete
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            cc=cc_list
        )

        msg.attach_alternative(html_content, "text/html")

        msg.send(fail_silently=False)

        #  MARK SUCCESS
        log.status = "sent"
        log.save()

        print(f" Email sent → {to_email}")

        return True

    except Exception as e:
        #  MARK FAILED
        log.status = "failed"
        log.save()

        print(" EMAIL ERROR:", str(e))

        # Optional: alert system
        send_internal_alert(
            subject="Email Failure Alert",
            message=f"""
            Failed to send email
    
            To: {to_email}
            Subject: {subject}
    
            Error:
            {str(e)}
            """
        )

        return False

def send_email(subject, html, to, gym=None, athlete=None, extra_cc=None):
    return send_got_email(
        subject=subject,
        html_content=html,
        to_email=to,
        gym=gym,
        athlete=athlete,
        extra_cc=extra_cc
    )


def email_gym_confirmation(gym):
    html = f"""
    <h2>Welcome to Game of Titans</h2>

    <p><b>{gym.name}</b></p>

    <h1>{gym.titan_id}</h1>

    <p>Share this ID with your athletes.</p>

    <p>Event: {gym.event_leg}</p>
    <p>GOT Contact: {gym.got_employee.name if gym.got_employee else 'Team GOT'}</p>

    <p>Benefits:</p>
    <ul>
        <li>Official GOT Partner Gym Certificate</li>
        <li>Social Media Feature</li>
        <li>Digital Badge</li>
        <li>Priority Access Season 2</li>
    </ul>

    <p>Contact: info@gameoftitans.in</p>
    """

    send_email(
        "Welcome to Game of Titans — Your Titan Gym ID is Ready",
        html,
        gym.email,
        gym=gym
    )


def email_mpcg_pending(gym):
    html = f"""
    <p>Dear {gym.name},</p>

    <p>Your registration is being processed.</p>

    <p>Regional Partner will contact within 48 hours.</p>

    <p>Benefits:</p>
    <ul>
        <li>Partner Certificate</li>
        <li>Social Media Feature</li>
        <li>Digital Badge</li>
        <li>Priority Access</li>
    </ul>

    <p>mpcg@gameoftitans.in</p>
    """

    send_email(
        "Game of Titans — Your Registration is Being Processed",
        html,
        gym.email,
        gym=gym
    )


def email_mpcg_lead(gym):
    send_email(
        subject="New Gym Lead — MP/CG — Action Required Within 48 Hours",
        html=f"""
        Gym: {gym.name}<br>
        Contact: {gym.contact_person}<br>
        Phone: {gym.phone}<br>
        City: {gym.city}<br>
        Athletes: {gym.expected_athletes}
        """,
        to="mpcg@gameoftitans.in",
        gym=gym
    )


def email_employee_gym(gym):
    if not gym.got_employee:
        return

    send_email(
        subject=f"New Gym Registered Under You — {gym.name}",
        html=f"""
        Gym: {gym.name}<br>
        Phone: {gym.phone}<br>
        City: {gym.city}<br>
        Titan ID: {gym.titan_id}
        """,
        to=gym.got_employee.email,
        gym=gym
    )


def email_gym_confirmed(gym):
    send_email(
        subject="Your GOT Contact Has Been Confirmed",
        html=f"""
        <p>{gym.got_employee.name} is your official GOT contact.</p>
        <p>Email: {gym.got_employee.email}</p>
        """,
        to=gym.email,
        gym=gym
    )


def email_mpcg_approved(gym):
    send_email(
        subject="You're Official — Your Titan Gym ID is Ready",
        html=f"""
        <h1>{gym.titan_id}</h1>
        <p>You are now an official GOT Partner Gym.</p>
        """,
        to=gym.email,
        gym=gym,
        extra_cc=["mpcg@gameoftitans.in"]
    )


def email_athlete_confirmation(participation):
    athlete = participation.athlete
    gym = participation.gym

    html = f"""
    <h2>You are a Titan</h2>

    <h1>{participation.tracking_id}</h1>

    <p>Name: {athlete.name}</p>
    <p>Event: {participation.event_leg}</p>
    <p>Gym: {gym.name if gym else 'Independent'}</p>

    <p>Contact: {athlete.got_employee.name if athlete.got_employee else 'Team GOT'}</p>
    """

    send_email(
        "You're a Titan. Welcome to Game of Titans.",
        html,
        athlete.email,
        athlete=athlete
    )


def email_employee_athlete(participation):
    emp = participation.athlete.got_employee
    if not emp:
        return

    send_email(
        subject=f"New Athlete Registered — {participation.athlete.name}",
        html=f"""
        Athlete: {participation.athlete.name}<br>
        Phone: {participation.athlete.phone}<br>
        Tracking ID: {participation.tracking_id}
        """,
        to=emp.email
    )


def email_athlete_confirmed(participation):
    emp = participation.athlete.got_employee

    send_email(
        subject="Your GOT Contact Has Been Confirmed",
        html=f"{emp.name} is your official GOT contact.",
        to=participation.athlete.email
    )



def send_48h_reminders():
    from django.utils import timezone
    from datetime import timedelta

    threshold = timezone.now() - timedelta(hours=48)

    pending = Participation.objects.filter(
        is_confirmed=False,
        created_at__lte=threshold
    )

    for p in pending:
        send_internal_alert(
            subject=f"Reminder — Confirmation Pending — {p.athlete.name}",
            message=f"{p.tracking_id} pending since 48h"
        )


def send_72h_escalation():
    threshold = timezone.now() - timedelta(hours=72)

    pending = Participation.objects.filter(
        is_confirmed=False,
        created_at__lte=threshold
    )

    for p in pending:
        send_internal_alert(
            subject="Unconfirmed Registration — 72 Hours",
            message=f"{p.tracking_id} needs manual action"
        )


def send_weekly_report(summary):
    send_internal_alert(
        subject=f"GOT Weekly Payout Report — {summary['start']} to {summary['end']}",
        message=f"""
        Total Registrations: {summary['total']}
        Gross: ₹{summary['gross']}
        Net: ₹{summary['net']}
        Iqbal Cut: ₹{summary['iqbal']}
        """
    )