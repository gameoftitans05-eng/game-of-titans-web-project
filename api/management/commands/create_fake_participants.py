from django.core.management.base import BaseCommand
from faker import Faker
import random

from api.models import (
    GymModel,
    MemberModel,
    EventModel,
    ParticipatedMemberModel
)

fake = Faker()


class Command(BaseCommand):
    help = "Create fake gym-registered participated members for existing event"

    def handle(self, *args, **kwargs):
        # Get existing active event
        event = EventModel.objects.filter(active=True).first()
        if not event:
            self.stdout.write(self.style.ERROR("No active event found"))
            return

        # Get test gym
        gym = GymModel.objects.filter(name__icontains="test").first()
        if not gym:
            self.stdout.write(self.style.ERROR("No test gym found"))
            return

        created_count = 0

        for i in range(50):
            # Force registration type as gym_member
            registration_type = "gym_member"

            # Create member linked to gym
            member = MemberModel.objects.create(
                gym=gym,
                name=fake.name(),
                email=fake.unique.email(),
                contact_number=fake.msisdn()[:15],  # cleaner numeric phone
                gender=random.choice(["male", "female", "other"]),
                registration_type=registration_type
            )

            ParticipatedMemberModel.objects.create(
                event=event,
                member=member,
                gym=gym,
                registration_type=registration_type,
                registration_id=f"REG{random.randint(10000, 99999)}",
                mail_sent=random.choice([True, False])
            )

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count} gym-registered participants for event '{event.name}'."
            )
        )