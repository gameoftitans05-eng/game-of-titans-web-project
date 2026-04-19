# from rest_framework import serializers
# from .models import (GymModel, MemberModel, EventModel, ParticipatedMemberModel, PaymentOrderModel, TransactionModel,
#                      SponsorModel)
#
#
# class GymSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = GymModel
#         fields = [
#             'id',  # usually good to include
#             'name',
#             'gym_id',
#             'contact_number',
#             'email',
#             'website',
#             'location',  # JSONField
#             'created_at',
#             'updated_at',
#         ]
#
#         read_only_fields = ['id', 'gym_id', 'created_at', 'updated_at']
#
#
# class MemberSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = MemberModel
#         fields = ['id', 'name', 'email', 'contact_number', 'gym', 'created_at']
#         read_only_fields = ['id', 'created_at']
#
#     def validate(self, attrs):
#         gym = attrs.get('gym')
#         email = attrs.get('email')
#         phone = attrs.get('contact_number')
#
#         if gym:
#             qs = MemberModel.objects.filter(gym=gym)
#             if email and qs.filter(email=email).exists():
#                 raise serializers.ValidationError({"email": "This email is already registered in this gym."})
#             if phone and qs.filter(contact_number=phone).exists():
#                 raise serializers.ValidationError(
#                     {"contact_number": "This phone number is already registered in this gym."})
#         return attrs
#
#
# class EventBasicSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = EventModel
#         fields = ['id', 'name', 'schedule_on', 'from_date', 'participation_amount', 'to_date', 'active', 'address']
#
#
# class PaymentOrderSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = PaymentOrderModel
#         fields = ['id', 'order_id', 'payment_type', 'status', 'created_at']
#         read_only_fields = ['id', 'order_id', 'status', 'created_at']
#
#
# class ParticipateInitiateSerializer(serializers.Serializer):
#     member_id = serializers.PrimaryKeyRelatedField(queryset=MemberModel.objects.all())
#     payment_type = serializers.ChoiceField(choices=[('UPI', 'UPI'), ('CARD', 'CARD')], default='UPI')
#
#
# class PaymentConfirmSerializer(serializers.Serializer):
#     order_id = serializers.CharField(max_length=30)
#     transaction_id = serializers.CharField(max_length=50, required=False)
#     pg_response = serializers.JSONField(required=False)  # full payment response
#
#
# class SponsorSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = SponsorModel
#         fields = [
#             'id',  # usually good to include
#             'name',
#             'company',
#             'email',
#             'contact_number',
#             'rejected',
#             'created_at',
#             'updated_at',
#         ]
#
#         read_only_fields = ['id', 'rejected', 'created_at', 'updated_at']
