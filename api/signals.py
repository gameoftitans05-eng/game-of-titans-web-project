# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.core.mail import send_mail
# from django.conf import settings
#
# from .models import GymModel
#
#
# @receiver(post_save, sender=GymModel)
# def send_gym_id_email(sender, instance, created, **kwargs):
#     # We want to send only when gym_id was just set (usually on the second save)
#     if created:
#         return  # first save → gym_id still None → skip
#
#     # Check if gym_id was part of the updated fields
#     if kwargs.get('update_fields') and 'gym_id' in kwargs['update_fields']:
#         if instance.email and instance.gym_id:
#             subject = f"Welcome! Your Gym ID is {instance.gym_id}"
#
#             message = (
#                 f"Dear {instance.name},\n\n"
#                 f"Your gym has been successfully registered!\n\n"
#                 f"Gym ID: {instance.gym_id}\n"
#                 f"This ID is important for member registration and management.\n\n"
#                 f"Keep it safe!\n\n"
#                 f"Best regards,\nYour Platform Team"
#             )
#
#             send_mail(
#                 subject=subject,
#                 message=message,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 recipient_list=[instance.email],
#                 fail_silently=False,
#             )
