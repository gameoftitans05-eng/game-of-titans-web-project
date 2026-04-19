# import hmac
# import hashlib
# import json
# import base64
#
# from django.conf import settings
# from django.db import transaction
# from django.db.models import Q
# from django.utils.crypto import get_random_string
# from rest_framework import status, generics, permissions
# from rest_framework.decorators import action
# from rest_framework.response import Response
#
# from titan_api_proj.response import APIResponse
# from django.http import JsonResponse
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated, AllowAny
#
# from rest_framework import viewsets
# from rest_framework.permissions import IsAuthenticatedOrReadOnly  # or whatever you need
# from .serializers import (GymSerializer, MemberSerializer, ParticipateInitiateSerializer,
#                           PaymentOrderSerializer, PaymentConfirmSerializer, EventBasicSerializer)
#
#
# def verify_cashfree_signature(raw_body: bytes, received_signature: str) -> bool:
#     """
#     Very important function - verifies Cashfree webhook signature
#     """
#     if not settings.CASHFREE_WEBHOOK_SECRET:
#         raise ValueError("CASHFREE_WEBHOOK_SECRET is not set in settings!")
#
#     # Compute HMAC SHA256 of RAW body
#     computed_hmac = hmac.new(
#         key=settings.CASHFREE_WEBHOOK_SECRET.encode('utf-8'),
#         msg=raw_body,
#         digestmod=hashlib.sha256
#     ).digest()
#
#     # Base64 encode → this is what Cashfree sends
#     computed_signature = base64.b64encode(computed_hmac).decode('utf-8')
#
#     # Timing safe comparison (very important for security)
#     return hmac.compare_digest(computed_signature, received_signature)
#
#
#
# class TestAPIView(APIView):
#     permission_classes = [AllowAny]
#
#     @staticmethod
#     def get():
#         return APIResponse(message='Test API Called.', data={})
#
# class GymViewSet(viewsets.ModelViewSet):
#     """
#     Gym create / list / retrieve / update / delete
#     """
#     queryset = GymModel.objects.all()
#     serializer_class = GymSerializer
#
#     # Optional: customize permission, filtering, ordering, search
#     permission_classes = [IsAuthenticatedOrReadOnly]  # example
#
#     # Example: only allow creation by authenticated users
#     def get_permissions(self):
#         if self.action in ['create', 'list', 'retrieve']:
#             return [permissions.AllowAny()]     # anyone can create & see gyms
#         # update, partial_update, destroy require login
#         return [permissions.IsAuthenticated()]
#
#     # Optional: filter by gym name, location etc.
#     filterset_fields = ['name', 'gym_id']
#     search_fields = ['name', 'email', 'contact_number',]
#     ordering_fields = ['name', 'created_at']
#
#
# class MemberViewSet(viewsets.ModelViewSet):
#     queryset = MemberModel.objects.all()
#     serializer_class = MemberSerializer
#
#     def get_permissions(self):
#         if self.action in ['create', 'list', 'retrieve']:
#             return [permissions.AllowAny()]  # anyone can register as member
#         return [permissions.IsAuthenticated()]
#
#
# class EventViewSet(viewsets.ModelViewSet):
#     queryset = EventModel.objects.filter(active=True)
#     serializer_class = EventBasicSerializer
#
#     def get_permissions(self):
#         # Allow anyone to see active events and initiate participation
#         if self.action in ['list', 'retrieve', 'participate']:
#             return [permissions.AllowAny()]
#
#         # Confirm payment endpoint - can be AllowAny (or token-based later)
#         if self.action == 'confirm_participation':
#             return [permissions.AllowAny()]
#
#         # update, destroy, deactivate etc. → only authenticated
#         return [permissions.IsAuthenticated()]
#
#     @action(detail=True, methods=['post'], url_path='participate')
#     @transaction.atomic
#     def participate(self, request, pk=None):
#         """
#         Step 1: Initiate participation → create payment order
#         """
#         event = self.get_object()
#
#         if not event.active:
#             return Response({"detail": "This event is not active."}, status=status.HTTP_400_BAD_REQUEST)
#
#         serializer = ParticipateInitiateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#
#         member = serializer.validated_data['member_id']
#         payment_type = serializer.validated_data['payment_type']
#
#         # Optional: validate member belongs to the same gym as event
#         # if member.gym_id != event.gym_id:  (add gym to EventModel if needed)
#         #     return Response({"detail": "Member is not from this gym"}, status=403)
#
#         # Check if already participated
#         if ParticipatedMemberModel.objects.filter(event=event, member=member).exists():
#             return Response({"detail": "Already registered for this event."}, status=400)
#
#         # Create payment order (temporary — no participation yet)
#         order = PaymentOrderModel.objects.create(
#             participate_member=None,           # will be set after success
#             order_id=f"ORD-{get_random_string(12).upper()}",
#             payment_type=payment_type,
#             status='CREATED'
#         )
#
#         # Here you would normally:
#         # - Calculate amount (add fee field to EventModel)
#         # - Create real payment order (Razorpay, PayU, Cashfree, etc.)
#         # - Return payment URL / QR / UPI payload
#
#         return Response({
#             "message": "Payment order created. Please complete payment.",
#             "order_id": order.order_id,
#             "amount": 500,  # ← replace with real amount
#             "payment_type": payment_type,
#             # "payment_url": "https://...",   # real gateway link
#             # "upi_payload": "...",          # for UPI deep link
#         }, status=status.HTTP_201_CREATED)
#
#
# @action(detail=False, methods=['post'], url_path='payment/confirm')
# @transaction.atomic
# def confirm_participation(request):
#     """
#     Step 2: After successful payment → create participation record
#     """
#     serializer = PaymentConfirmSerializer(data=request.data)
#     serializer.is_valid(raise_exception=True)
#
#     order_id = serializer.validated_data['order_id']
#
#     try:
#         order = PaymentOrderModel.objects.select_for_update().get(order_id=order_id)
#     except PaymentOrderModel.DoesNotExist:
#         return Response({"detail": "Order not found"}, status=404)
#
#     if order.status == 'PAID':
#         return Response({"detail": "Already processed"}, status=400)
#
#     # Here you should **verify the payment** with your gateway
#     # For demo we assume success
#     payment_success = True   # ← replace with real verification logic
#
#     if not payment_success:
#         order.status = 'FAILED'
#         order.save()
#         return APIResponse(success=False, data={"detail": "Payment verification failed"}, status=400)
#
#     # Payment is successful → create participation
#     # You need to know which event & member this order belongs to.
#     # For simplicity, let's assume you stored it temporarily or pass it in request.
#
#     # Better solution: store event & member in a temporary model or in order metadata
#
#     # Temporary solution (not ideal for production):
#     # You should pass event_id & member_id in the confirm request too
#
#     event_id = request.data.get('event_id')
#     member_id = request.data.get('member_id')
#
#     if not event_id or not member_id:
#         return APIResponse(success=False, data={"detail": "Missing event_id or member_id"}, status=400)
#
#     try:
#         event = EventModel.objects.get(id=event_id)
#         member = MemberModel.objects.get(id=member_id)
#     except (EventModel.DoesNotExist, MemberModel.DoesNotExist):
#         return APIResponse(success=False, data={"detail": "Invalid event or member"}, status=400)
#
#     # Create participation
#     participation = ParticipatedMemberModel.objects.create(
#         event=event,
#         member=member,
#         gym=member.gym,           # copy gym from member
#         mail_sent=False,
#         registration_id=f"REG-{get_random_string(10).upper()}"
#     )
#
#     # Update order
#     order.participate_member = participation
#     order.status = 'PAID'
#     order.pg_response = serializer.validated_data.get('pg_response')
#     order.save()
#
#     # Optional: create transaction record
#     # TransactionModel.objects.create(...)
#
#     return Response({
#         "message": "Participation successful!",
#         "registration_id": participation.registration_id,
#         "event": EventBasicSerializer(event).data
#     }, status=status.HTTP_201_CREATED)
