# MOVE THIS HERE

from django.core.mail import send_mail
from django.conf import settings
from api.models import EmailLog

REGISTRATIONS_EMAIL = getattr(settings, 'REGISTRATIONS_EMAIL', 'registrations@gameoftitans.in')
OFFICE_EMAIL = getattr(settings, 'OFFICE_EMAIL', 'office@gameoftitans.in')

INTERNAL_CC = [REGISTRATIONS_EMAIL, OFFICE_EMAIL]


def send_internal_alert(subject, message, gym=None, athlete=None):
    log = EmailLog.objects.create(
        to_email=",".join(INTERNAL_CC),
        subject=subject,
        status="pending",
        related_gym=gym,
        related_athlete=athlete
    )

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            INTERNAL_CC,
            fail_silently=True
        )

        log.status = "sent"
        log.save()

    except Exception:
        log.status = "failed"
        log.save()