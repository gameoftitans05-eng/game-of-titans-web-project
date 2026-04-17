# registration_views.py
import base64
import hashlib
import hmac
import json

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import trim_whitespace
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import uuid

from cashfree_pg.api_client import Cashfree
from cashfree_pg.models import (
    CreateOrderRequest,
    CustomerDetails,
    OrderMeta
)

from .models import GymModel, MemberModel, EventModel, PaymentOrderModel, ParticipatedMemberModel, SponsorModel, \
    ReferUserModel
from .serializers import EventBasicSerializer


def init_cashfree():
    """
    Return a properly initialized Cashfree instance
    """
    try:
        environment = Cashfree.SANDBOX if getattr(settings, 'CASHFREE_ENV',
                                                  'SANDBOX') == 'SANDBOX' else Cashfree.PRODUCTION

        cf = Cashfree(
            XClientId=settings.CASHFREE_CLIENT_ID,
            XClientSecret=settings.CASHFREE_CLIENT_SECRET,
            XEnvironment=environment
        )
        print("Cashfree initialized successfully with environment:", environment)
        return cf

    except Exception as e:
        print("Cashfree initialization failed:", str(e))
        raise  # re-raise to see full error in view


@api_view(['GET'])
@permission_classes([AllowAny])
def active_events_list(request):
    """
    Returns list of active events for the frontend dropdown
    """
    events = EventModel.objects.filter(active=True).order_by('schedule_on')
    serializer = EventBasicSerializer(events, many=True)
    return Response(serializer.data)


@csrf_exempt
@require_POST
@permission_classes([AllowAny])
def register_gym(request):
    """
    Gym registration endpoint
    Called via form POST or AJAX
    Returns JSON so frontend can display gym_id
    """
    try:
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        contact_number = request.POST.get('contact_number', '').strip()
        # Add more fields if needed: website, location, city, etc.
        print('ccc: ', name, email, contact_number)
        if not all([name, email, contact_number]):
            return JsonResponse({
                "success": False,
                "error": "Name, email and contact number are required"
            }, status=400)

        if GymModel.objects.filter(email=email).exists():
            return JsonResponse({
                "success": False,
                "error": "This email is already registered"
            }, status=400)

        if GymModel.objects.filter(contact_number=contact_number).exists():
            return JsonResponse({
                "success": False,
                "error": "This phone number is already registered"
            }, status=400)

        gym = GymModel.objects.create(
            name=name,
            email=email,
            contact_number=contact_number,
            location={"city": request.POST.get('city', '')}  # example
        )

        return JsonResponse({
            "success": True,
            "gym_id": gym.gym_id,
            "message": f"Gym registered successfully! Your Gym ID: {gym.gym_id}"
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"Server error: {str(e)}"
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_participation(request):
    """
    Member registration + Cashfree payment order creation
    Expects JSON from frontend
    Returns payment_session_id → frontend opens checkout
    """
    data = request.data
    # print(request.data)
    required = ["event_id", "name", "email", "phone", "gender", "registration_type"]
    if not all(field in data for field in required):
        return Response({
            "success": False,
            "error": "Missing required fields"
        }, status=status.HTTP_400_BAD_REQUEST)

    gym_id = str(data["gym_id"]).strip().upper()
    event_id = data["event_id"]
    name = str(data["name"]).strip()
    email = str(data["email"]).strip()
    phone = str(data["phone"]).strip()
    gender = str(data["gender"]).strip().lower()
    registration_type = str(data.get("registration_type", "")).strip().lower()
    refer_code = str(data.get("refer_code", "")).strip().upper()
    pay_type = data.get("payment_type", "UPI")

    referred_user = ReferUserModel.objects.filter(refer_code=refer_code)

    if not referred_user.exists():
        return Response({
            "success": False,
            "error": "Referred code is invalid."
        }, status=400)

    referred_user = referred_user.first()

    # Validate registration_type
    if registration_type not in ['gym_member', 'individual']:
        return Response({
            "success": False,
            "error": "Invalid registration_type. Must be 'gym_member' or 'individual'"
        }, status=400)

    # Gym ID is required only for gym_member
    gym_id = None
    gym = None
    if registration_type == 'gym_member':
        if "gym_id" not in data or not data["gym_id"]:
            return Response({
                "success": False,
                "error": "gym_id is required when registering as gym_member"
            }, status=400)
        gym_id = str(data["gym_id"]).strip().upper()
        try:
            gym = GymModel.objects.get(gym_id=gym_id)
        except GymModel.DoesNotExist:
            return Response({
                "success": False,
                "error": "Invalid Gym Titan ID"
            }, status=400)

    # Validate gender (you can adjust allowed values)
    allowed_genders = ['male', 'female', 'other', 'prefer_not_to_say']
    if gender not in allowed_genders:
        return Response({
            "success": False,
            "error": f"Invalid gender. Allowed: {', '.join(allowed_genders)}"
        }, status=400)

    # return Response({
    #     "success": True,
    #     "gym_id": gym_id,
    #     "event_id": event_id,
    #     "name": name,
    #     "email": email,
    #     "phone": phone,
    #     "gender": gender,
    # })

    try:
        event = EventModel.objects.get(id=event_id, active=True)
    except EventModel.DoesNotExist:
        return Response({
            "success": False,
            "error": "Event not found or inactive"
        }, status=400)

    if event.participation_amount <= 0:
        return Response({
            "success": False,
            "error": "Participation amount is not configured for this event"
        }, status=400)

    # Prevent duplicate registration for same event + email
    if ParticipatedMemberModel.objects.filter(
            event=event,
            member__email=email
    ).exists():
        return Response({
            "success": False,
            "error": "You are already registered for this event"
        }, status=409)

    # Create or update member
    defaults = {
        "name": name,
        "contact_number": phone,
        "gender": gender,
        "registration_type": registration_type,
        "referred_by": referred_user,
    }

    # Get or create member
    member, created = MemberModel.objects.get_or_create(
        email=email,
        defaults=defaults
    )

    if registration_type == 'gym_member':
        member.gym = gym
        member.save()

    if not created:
        member.name = name
        member.contact_number = phone
        member.save()

    # Create internal payment order record
    order_id = f"TITANS-{uuid.uuid4().hex[:12].upper()}"
    amount = float(event.participation_amount)

    payment_order = PaymentOrderModel.objects.create(
        participate_member=None,  # filled later in webhook
        order_id=order_id,
        payment_type=pay_type,
        status="CREATED",
        event=event,
        member=member,
        amount=amount
    )

    try:
        cf = init_cashfree()

        api_version = getattr(settings, 'CASHFREE_API_VERSION', "2025-01-01")
        if not isinstance(api_version, str) or not api_version.strip():
            api_version = "2025-01-01"
            print("WARNING: Using fallback API version:", api_version)

        customer = CustomerDetails(
            customer_id=f"mem-{member.id}-{uuid.uuid4().hex[:8]}",
            customer_name=name,
            customer_email=email,
            customer_phone=phone,
        )

        return_url = getattr(settings, 'CASHFREE_RETURN_URL', 'https://gameoftitans.in/api/v1/payment/success/')
        notify_url = getattr(settings, 'CASHFREE_NOTIFY_URL', 'https://gameoftitans.in/api/v1/webhooks/cashfree/')

        meta = OrderMeta(
            return_url=return_url.format(order_id=order_id),
            notify_url=notify_url,
        )

        req = CreateOrderRequest(
            order_id=order_id,
            order_amount=amount,
            order_currency="INR",
            customer_details=customer,
            order_meta=meta,
            order_note=f"Game of Titans – {event.name} – "
                       f"{'Gym: ' + gym.gym_id if gym else 'Individual'}",
        )

        cf_response = cf.PGCreateOrder(
            x_api_version=api_version,
            create_order_request=req
        )

        # cf_response = cf.PGCreateOrder(
        #     x_api_version=api_version, create_order_request=req, x_request_id=None, x_idempotency_key=None
        #     # object second,
        # )

        # Save Cashfree reference
        payment_order.cf_order_id = cf_response.data.cf_order_id
        payment_order.save()

        return Response({
            "success": True,
            "payment_session_id": cf_response.data.payment_session_id,
            "order_id": order_id,
            "amount": amount,
            "event_name": event.name,
            "registration_type": registration_type,
        })

    except Exception as e:
        payment_order.status = "FAILED"
        payment_order.pg_response = str(e)
        payment_order.save()
        print("error: ", e)
        return Response({
            "success": False,
            "error": f"Payment gateway error: {str(e)}"
        }, status=500)


@permission_classes([AllowAny])
def payment_success(request):
    order_id = request.GET.get('order_id')

    if not order_id:
        return render(request, 'payment_error.html', {
            'message': 'No order ID received from payment gateway'
        })

    try:
        # Fetch order with related data
        cf = init_cashfree()

        api_version = getattr(settings, 'CASHFREE_API_VERSION', "2025-01-01")
        api_response = cf.PGFetchOrder(api_version, order_id, None)
        # print("server order response: ", api_response.data.order_status)

        if api_response.data.order_status != "PAID":
            return render(request, 'payment_error.html', {
                'message': 'Payment Failed or User Cancelled the Payment'
            })

        order = PaymentOrderModel.objects.select_related('event', 'member', 'member__gym', 'participate_member').get(
            order_id=order_id)

        # Update status to PAID if it's still CREATED (safety net)
        if order.status == 'CREATED':
            order.status = 'PAID'
            order.save()

        # Create participation record if not already created
        participation = order.participate_member
        if not participation:
            participation = ParticipatedMemberModel.objects.create(
                event=order.event,
                member=order.member,
                gym=order.member.gym if order.member and order.member.gym else None,
                mail_sent=False,
                registration_type=order.member.registration_type,
                registration_id=f"REG-{uuid.uuid4().hex[:8].upper()}",
                referred_by=order.member.referred_by,
            )
            order.participate_member = participation
            order.save()

            print(order.member, order.member.email and order.participate_member and order.participate_member.mail_sent)

            # Send confirmation email (only if not already sent)
            if order.member and order.member.email and not (
                    order.participate_member and order.participate_member.mail_sent):
                try:
                    html_content = render_to_string('emails/participation_success.html', {
                        'member_name': order.member.name,
                        'event_name': order.event.name if order.event else 'Event',
                        'registration_id': order.participate_member.registration_id,
                        'gym_name': order.member.gym.name if order.member.gym else 'Your Gym',
                        'gym_id': order.member.gym.gym_id if order.member.gym else 'N/A',
                        'event_date': order.event.schedule_on.strftime(
                            "%d %B %Y, %I:%M %p") if order.event and order.event.schedule_on else 'Date & Time TBD',
                        'amount': f"₹{order.amount:,.2f}" if order.amount else 'N/A',
                    })

                    text_content = strip_tags(html_content)

                    email_msg = EmailMultiAlternatives(
                        subject="Game of Titans - Registration Confirmed!",
                        body=text_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[order.member.email],
                    )
                    email_msg.attach_alternative(html_content, "text/html")
                    email_msg.send(fail_silently=False)

                    # Mark as sent
                    order.participate_member.mail_sent = True
                    order.participate_member.save()

                    print(f"Confirmation email sent to {order.member.email}")

                except Exception as email_err:
                    print(f"Email sending failed: {str(email_err)}")  # log but don't crash webhook

            # return HttpResponse("Payment processed + email sent", status=200)

        # Prepare context for template
        context = {
            'order_id': order.order_id,
            'status': order.status,
            'amount': f"₹{order.amount:,.2f}" if order.amount else "N/A",
            'event_name': order.event.name if order.event else "Not specified",
            'member_name': order.member.name if order.member else "Guest",
            'gym_name': order.member.gym.name if order.member and order.member.gym else "N/A",
            'registration_id': order.participate_member.registration_id if order.participate_member else "N/A",
            'event_date': order.event.schedule_on.strftime(
                "%d %B %Y, %I:%M %p") if order.event and order.event.schedule_on else 'Date & Time TBD',
        }

        # Render appropriate template
        if order.status == 'PAID':
            return render(request, 'payment_success.html', context)
        else:
            return render(request, 'payment_pending.html', context)

    except PaymentOrderModel.DoesNotExist:
        return render(request, 'payment_error.html', {
            'message': f'Order {order_id} not found'
        })
    except Exception as e:
        return render(request, 'payment_error.html', {
            'message': f'Error loading order: {str(e)}'
        })


@csrf_exempt
@permission_classes([AllowAny])
def cashfree_webhook(request):
    """
    Receives real-time payment status updates from Cashfree
    Validates signature and updates PaymentOrderModel
    """
    if request.method != 'POST':
        return HttpResponseBadRequest("Method not allowed")

    # Get raw body first (important for signature)
    raw_body = request.body

    # Get headers
    signature = request.headers.get('x-webhook-signature')
    timestamp = request.headers.get('x-webhook-timestamp')

    if not signature or not timestamp:
        return HttpResponseBadRequest("Missing webhook headers")

    # Verify signature
    if not verify_cashfree_signature(raw_body, signature):
        return HttpResponseBadRequest("Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
        event_type = payload.get('type')
        data = payload.get('data', {})

        order_data = data.get('order', {})
        payment_data = data.get('payment', {})

        order_id = order_data.get('order_id')
        cf_payment_id = payment_data.get('cf_payment_id')
        payment_status = payment_data.get('payment_status')  # SUCCESS, FAILED, USER_DROPPED, etc.

        if not order_id:
            return HttpResponse("Missing order_id – acknowledged", status=200)

        # Find the order
        try:
            order = PaymentOrderModel.objects.get(order_id=order_id)
        except PaymentOrderModel.DoesNotExist:
            return HttpResponse("Order not found – acknowledged", status=200)

        # Idempotency check
        if order.status == 'PAID' and order.cf_payment_id == cf_payment_id:
            return HttpResponse("Already processed", status=200)

        # Update order status
        order.pg_response = json.dumps(payload)
        order.cf_payment_id = cf_payment_id

        if payment_status == 'SUCCESS':
            order.status = 'PAID'
            # Here you can trigger email, create ParticipatedMemberModel, etc.
        elif payment_status in ['FAILED', 'USER_DROPPED']:
            order.status = payment_status
        else:
            order.status = 'UNKNOWN'

        order.save()

        return HttpResponse(f"Processed: {payment_status}", status=200)

    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload")
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return HttpResponse("Error processing webhook – acknowledged", status=200)


# Reuse your existing verify_cashfree_signature function (if you have it)
# Or add this if not present
@permission_classes([AllowAny])
def verify_cashfree_signature(raw_body: bytes, received_signature: str) -> bool:
    if not settings.CASHFREE_WEBHOOK_SECRET:
        return False

    computed_hmac = hmac.new(
        key=settings.CASHFREE_WEBHOOK_SECRET.encode('utf-8'),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).digest()

    computed_signature = base64.b64encode(computed_hmac).decode('utf-8')

    return hmac.compare_digest(computed_signature, received_signature)


@require_POST
@permission_classes([AllowAny])
def create_sponsor(request):
    """
    Normal function-based view to handle sponsor form submission
    Expects POST data from HTML form
    """
    if request.method != 'POST':
        return redirect('home')  # or wherever your home page is

    name = request.POST.get('name', '').strip()
    company = request.POST.get('company', '').strip()
    email = request.POST.get('email', '').strip()
    contact_number = request.POST.get('contact_number', '').strip()
    message = request.POST.get('message', '').strip()

    # Basic validation
    errors = []
    if not name:
        errors.append("Name is required.")
    if not company:
        errors.append("Company name is required.")

    if errors:
        # If validation fails, show errors on the same page
        context = {
            'errors': errors,
            'form_data': request.POST,  # preserve form values
        }
        return render(request, 'sponsor_form.html', context)

    try:
        # Check for duplicate (optional but good)
        if SponsorModel.objects.filter(name=name, company=company).exists():
            messages.error(request, "A sponsor with this name and company already exists.")
            return redirect('/')  # or render with error

        # Create sponsor
        sponsor = SponsorModel.objects.create(
            name=name,
            company=company,
            email=email or None,
            contact_number=contact_number or None,
            rejected=False,  # default
            message=message or None,
        )

        messages.success(request,
                         "Thank you! Your sponsor application has been submitted successfully. We will review it soon.")
        return redirect('sponsor-success')  # or home page

    except Exception as e:
        messages.error(request, f"Error submitting form: {str(e)}")
        return redirect('/')


@api_view(['GET'])
@permission_classes([AllowAny])
def get_stats(request):
    """
    Returns total number of gyms and participants (participated members)
    """
    gyms = GymModel.objects.count()
    members = ParticipatedMemberModel.objects.count()
    return Response({
        "gyms": gyms,
        "members": members
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_terms_policy(request):
    return render(request, 'pages/terms.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def get_privacy_policy(request):
    return render(request, 'pages/privacy.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def get_refund_policy(request):
    return render(request, 'pages/refund.html')


def mumbai(request):
    return render(request, 'pages/mumbai.html')

def delhi(request):
    return render(request, 'pages/delhi.html')

def bengaluru(request):
    return render(request, 'pages/bengaluru.html')

def register(request):
    return render(request, 'pages/register.html')

def sponsors(request):
    return render(request, 'pages/sponsors.html')

def about(request):
    return render(request, 'pages/about.html')
