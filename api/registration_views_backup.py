import base64
import hashlib
import hmac
import json
import re
import uuid
import datetime

from django.conf import settings
from django.contrib.sites import requests
from django.db import transaction
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils.html import strip_tags

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cashfree_pg.api_client import Cashfree
from cashfree_pg.models import CreateOrderRequest, CustomerDetails, OrderMeta

from .models import Gym, Athlete, PaymentOrder, Sponsor, GOTEmployee, MPCG_STATES, Participation, EmailLog

# =========================================================
# EMAIL CONFIG (MANDATORY FROM PDF)
# =========================================================
REGISTRATIONS_EMAIL = getattr(settings, 'REGISTRATIONS_EMAIL', 'registrations@gameoftitans.in')
OFFICE_EMAIL = getattr(settings, 'OFFICE_EMAIL', 'office@gameoftitans.in')
ADMIN_EMAIL = getattr(settings, 'ADMIN_EMAIL', 'admin@gameoftitans.in')

INTERNAL_CC = [REGISTRATIONS_EMAIL, OFFICE_EMAIL]


# =========================================================
# CASHFREE INIT
# =========================================================
def init_cashfree():
    import certifi
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


# =========================================================
# EMAIL HELPERS (WITH LOGGING)
# =========================================================
def send_got_email(subject, html_content, to_email, gym=None, athlete=None, extra_cc=None):
    """
        Send email to primary recipient.
        Always CC: registrations@gameoftitans.in + office@gameoftitans.in
        """

    log = EmailLog.objects.create(
        to_email=to_email,
        subject=subject,
        status="pending",
        related_gym=gym,
        related_athlete=athlete
    )

    try:
        text = strip_tags(html_content)
        cc_list = INTERNAL_CC.copy()
        if extra_cc:
            cc_list += extra_cc

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            cc=INTERNAL_CC
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)

        print(f"Email sent to {to_email}, CC: {cc_list}")

        log.status = "sent"
        log.save()

        return True

    except Exception as e:
        log.status = "failed"
        log.save()

        print("Email error:", str(e))
        return False


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

        return True

    except Exception as e:
        log.status = "failed"
        log.save()

        print("Internal alert error:", str(e))
        return False


def send_satya_technical_ping(error_type, error_msg=None):
    try:
        send_mail(
            "GOT SYSTEM ERROR",
            f"Type: {error_type}\nTime: {datetime.datetime.now()} \nMessage: {error_msg}",
            settings.DEFAULT_FROM_EMAIL,
            [ADMIN_EMAIL],
            fail_silently=True
        )
        return True
    except Exception:
        return False


# =========================================================
# GYM REGISTRATION (PDF COMPLIANT)
# =========================================================
# ─────────────────────────────────────────────
# GYM REGISTRATION (PRODUCTION READY)
# ─────────────────────────────────────────────
@csrf_exempt
@require_POST
def register_gym(request):
    try:
        data = request.POST

        # ─────────────────────────────────────────
        # REQUIRED FIELDS (STRICT VALIDATION)
        # ─────────────────────────────────────────
        required_fields = [
            "name", "contact_person", "role", "email", "phone",
            "state", "city", "address",
            "active_members", "expected_athletes",
            "event_leg", "consent"
        ]

        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    "success": False,
                    "error": f"{field.replace('_', ' ').title()} is required."
                }, status=400)

        # ─────────────────────────────────────────
        # BASIC EXTRACTION
        # ─────────────────────────────────────────
        name = data.get("name").strip()
        email = data.get("email").strip()
        phone = data.get("phone").strip()
        state = data.get("state").strip()
        city = data.get("city").strip()

        is_mpcg = state in MPCG_STATES

        # ─────────────────────────────────────────
        # DUPLICATE CHECKS
        # ─────────────────────────────────────────
        if Gym.objects.filter(email=email).exists():
            return JsonResponse({
                "success": False,
                "error": "This email is already registered."
            }, status=400)

        if Gym.objects.filter(phone=phone).exists():
            return JsonResponse({
                "success": False,
                "error": "This phone number is already registered."
            }, status=400)

        # ─────────────────────────────────────────
        # GOT EMPLOYEE ASSIGNMENT
        # ─────────────────────────────────────────
        employee = None

        if is_mpcg:
            # Auto assign MPCG regional partner (must exist in DB)
            employee = GOTEmployee.objects.filter(
                name__icontains="Regional Partner",
                is_active=True
            ).first()
        else:
            employee_id = data.get("got_employee")
            if employee_id:
                employee = GOTEmployee.objects.filter(id=employee_id).first()

        # ─────────────────────────────────────────
        # CREATE GYM (ATOMIC)
        # ─────────────────────────────────────────
        with transaction.atomic():
            gym = Gym.objects.create(
                name=name,
                contact_person=data.get("contact_person"),
                role=data.get("role"),
                email=email,
                phone=phone,
                state=state,
                city=city,
                address=data.get("address"),
                active_members=data.get("active_members"),
                instagram=data.get("instagram"),
                expected_athletes=data.get("expected_athletes"),
                event_leg=data.get("event_leg"),
                got_employee=employee
            )

        # ─────────────────────────────────────────
        # MPCG FLOW (NO TITAN ID)
        # ─────────────────────────────────────────
        if gym.is_mpcg:

            # Email 2 → Gym Pending
            send_got_email(
                subject="Game of Titans — Your Registration is Being Processed",
                to_email=gym.email,
                html_content=f"""
                Dear {gym.name},<br><br>
                Thank you for registering.<br><br>
                Our MP & Chhattisgarh Regional Partner will contact you within 48 hours to complete onboarding.<br><br>
                For queries: mpcg@gameoftitans.in
                """
            )

            # Email 3 → Regional Partner
            send_internal_alert(
                subject="New Gym Lead — MP/CG — Action Required Within 48 Hours",
                message=f"""
                Gym: {gym.name}
                Contact: {gym.contact_person}
                Phone: {gym.phone}
                City: {gym.city}
                Expected Athletes: {gym.expected_athletes}
                """
            )

            return JsonResponse({
                "success": True,
                "type": "mpcg_pending",
                "message": "Your registration is under review. Regional partner will contact you within 48 hours.",
                "gym": {
                    "name": gym.name,
                    "contact_person": gym.contact_person,
                    "email": gym.email,
                    "phone": gym.phone,
                    "state": gym.state,
                    "city": gym.city,
                    "address": gym.address,
                    "active_members": gym.active_members,
                    "expected_athletes": gym.expected_athletes,
                    "event_leg": gym.event_leg,
                }
            })

        # ─────────────────────────────────────────
        # NORMAL FLOW (TITAN ID GENERATED)
        # ─────────────────────────────────────────
        else:

            # Email 1 → Gym Confirmation
            send_got_email(
                subject="Welcome to Game of Titans — Your Titan Gym ID is Ready",
                to_email=gym.email,
                html_content=f"""
                Dear {gym.name},<br><br>
                Your Titan Gym ID:<br>
                <h2>{gym.titan_id}</h2><br>
                Share this ID with your athletes.<br><br>
                """
            )

            # Internal notification (Employee)
            if gym.got_employee:
                send_internal_alert(
                    subject=f"New Gym Registered Under You — {gym.name} | {gym.city}",
                    message=f"""
                    Gym: {gym.name}
                    Phone: {gym.phone}
                    Titan ID: {gym.titan_id}
                    """
                )

            return JsonResponse({
                "success": True,
                "type": "success",
                "titan_id": gym.titan_id,
                "gym": {
                    "name": gym.name,
                    "contact_person": gym.contact_person,
                    "email": gym.email,
                    "phone": gym.phone,
                    "state": gym.state,
                    "city": gym.city,
                    "address": gym.address,
                    "active_members": gym.active_members,
                    "expected_athletes": gym.expected_athletes,
                    "event_leg": gym.event_leg,
                },
                "message": "Gym registered successfully."
            })

    except Exception as e:
        import datetime
        send_satya_technical_ping(
            "Gym Registration Error",
            f"{str(e)} | {datetime.datetime.now()}"
        )
        return JsonResponse({
            "success": False,
            "error": "Something went wrong. Please try again."
        }, status=500)


# ─────────────────────────────────────────────
# ATHLETE REGISTRATION + PAYMENT (NEW SYSTEM)
# ─────────────────────────────────────────────
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_participation(request):
    try:
        data = request.data

        # ─────────────────────────────────────────
        # REQUIRED FIELDS
        # ─────────────────────────────────────────
        required = [
            "name", "email", "phone", "gender",
            "registration_type", "state", "city", "event_leg"
        ]

        for field in required:
            if not data.get(field):
                return Response({
                    "success": False,
                    "error": f"{field} is required"
                }, status=400)

        name = data["name"].strip()
        email = data["email"].strip()
        phone = data["phone"].strip()
        gender = data["gender"].lower()
        registration_type = data["registration_type"].lower()
        state = data["state"].strip()
        city = data["city"].strip()
        event_leg = data["event_leg"]

        is_mpcg = state in MPCG_STATES

        # ─────────────────────────────────────────
        # GYM VALIDATION
        # ─────────────────────────────────────────
        gym = None
        titan_id_input = None

        if not is_mpcg and registration_type == "gym":
            titan_id_input = data.get("titan_id", "").strip().upper()

            if not titan_id_input:
                return Response({
                    "success": False,
                    "error": "Titan Gym ID is required"
                }, status=400)

            try:
                gym = Gym.objects.get(titan_id=titan_id_input)
            except Gym.DoesNotExist:
                return Response({
                    "success": False,
                    "error": "Invalid Titan Gym ID"
                }, status=400)

        # ─────────────────────────────────────────
        # GOT EMPLOYEE (FIXED)
        # ─────────────────────────────────────────
        employee = None

        if is_mpcg:
            employee = GOTEmployee.objects.filter(
                name__icontains="Regional Partner",
                is_active=True
            ).first()

        else:
            emp_id = data.get("got_employee")
            if emp_id and emp_id != "self":
                try:
                    employee = GOTEmployee.objects.get(code=emp_id)
                except (ValueError, GOTEmployee.DoesNotExist):
                    return Response({
                        "success": False,
                        "error": "Invalid GOT employee selected"
                    }, status=400)

            else:
                employee = None  # self registered
        # ─────────────────────────────────────────
        # ATOMIC FLOW
        # ─────────────────────────────────────────
        with transaction.atomic():

            # ─────────────────────────────
            # ATHLETE
            # ─────────────────────────────
            athlete, _ = Athlete.objects.get_or_create(
                email=email,
                defaults={
                    "name": name,
                    "phone": phone,
                    "gender": gender,
                    "state": state,
                    "city": city,
                }
            )

            athlete.name = name
            athlete.phone = phone
            athlete.state = state
            athlete.city = city
            athlete.event_leg = event_leg
            athlete.registration_type = registration_type
            athlete.got_employee = employee
            if registration_type == "gym":
                athlete.gym = gym
                athlete.titan_id = titan_id_input
            athlete.save()

            # ─────────────────────────────
            # CHECK EXISTING PARTICIPATION
            # ─────────────────────────────
            existing = Participation.objects.filter(
                athlete=athlete,
                event_leg=event_leg
            ).order_by("-created_at").first()

            if existing:

                # print('existing:', existing.payment_status, existing.event_leg)
                # ✅ SUCCESS → BLOCK
                if existing.payment_status == "success":
                    return Response({
                        "success": False,
                        "error": "You are already registered for this event"
                    }, status=409)

                # ✅ PENDING / FAILED → RETRY
                if existing.payment_status in ["pending", "failed"]:
                    existing.payment_status = "expired"
                    existing.retry_count += 1
                    existing.save()

                    # expire old orders
                    PaymentOrder.objects.filter(
                        participation=existing,
                        status="created"
                    ).update(status="expired")

            # ─────────────────────────────
            # CREATE NEW PARTICIPATION
            # ─────────────────────────────
            participation = Participation.objects.create(
                athlete=athlete,
                event_leg=event_leg,
                tracking_id=f"TXN-{uuid.uuid4().hex[:6].upper()}",
                payment_status="pending"
            )

            # ─────────────────────────────
            # CREATE ORDER
            # ─────────────────────────────
            order_id = f"ORDER-{uuid.uuid4().hex[:10].upper()}"

            payment_order = PaymentOrder.objects.create(
                athlete=athlete,
                participation=participation,
                order_id=order_id,
                amount=1999,
                status="created"
            )

        # ─────────────────────────────────────────
        # PAYMENT GATEWAY (CASHFREE)
        # ─────────────────────────────────────────
        try:
            cf = init_cashfree()
            api_version = getattr(settings, 'CASHFREE_API_VERSION', "2025-01-01")

            phone = data["phone"].strip()

            # Remove spaces, +, etc.
            phone = re.sub(r'\D', '', phone)

            # Convert +91XXXXXXXXXX → XXXXXXXXXX
            if phone.startswith("91") and len(phone) == 12:
                phone = phone[2:]

            # Final validation
            if len(phone) != 10:
                return Response({
                    "success": False,
                    "error": "Enter valid 10 digit phone number"
                }, status=400)

            customer = CustomerDetails(
                customer_id=f"ath-{athlete.id}",
                customer_name=name,
                customer_email=email,
                customer_phone=phone,
            )

            # meta = OrderMeta(
            #     return_url=f"{settings.DOMAIN}/payment-success?order_id={order_id}",
            #     notify_url=f"{settings.DOMAIN}/api/webhooks/cashfree/"
            # )

            return_url = getattr(
                settings,
                'CASHFREE_RETURN_URL',
                'https://gameoftitans.in/api/v1/payment/success/?order_id={order_id}'
            )
            notify_url = getattr(
                settings,
                'CASHFREE_NOTIFY_URL',
                'https://gameoftitans.in/api/v1/webhooks/cashfree/'
            )

            meta = OrderMeta(
                return_url=return_url.format(order_id=order_id),
                notify_url=notify_url,
            )

            req = CreateOrderRequest(
                order_id=order_id,
                order_amount=1999.0,
                order_currency="INR",
                customer_details=customer,
                order_meta=meta,
                order_note=f"Game of Titans — {event_leg} — "
                           f"{'Gym: ' + gym.id if gym else 'Individual'}",
            )

            cf_response = cf.PGCreateOrder(
                x_api_version=api_version,
                create_order_request=req
            )

            print(cf_response.data)


            return Response({
                "success": True,
                "payment_session_id": cf_response.data.payment_session_id,
                "order_id": order_id,
                "tracking_id": participation.tracking_id
            })

        except Exception as e:
            participation.payment_status = "failed"
            participation.save()

            payment_order.status = "failed"
            payment_order.save()

            send_internal_alert(
                subject=f"Payment Failure — {name} | ₹1999",
                message=f"{str(e)}"
            )

            send_satya_technical_ping("Payment Error", str(e))

            print('Payment Error: ', str(e))

            return Response({
                "success": False,
                "error": "Payment error. Try again."
            }, status=500)

    except Exception as e:
        send_satya_technical_ping("Participation Error", str(e))
        print("Participation Error: ", str(e))
        return Response({
            "success": False,
            "error": "Something went wrong"
        }, status=500)


# =========================================================
# PAYMENT SUCCESS
# =========================================================
def payment_success(request):
    order_id = request.GET.get("order_id")

    if not order_id:
        return render(request, "payment_error.html", {
            "message": "No order ID received."
        })

    try:
        cf = init_cashfree()
        api_version = getattr(settings, "CASHFREE_API_VERSION", "2025-01-01")

        # 🔐 Verify from Cashfree
        api_response = cf.PGFetchOrder(api_version, order_id, None)

        if api_response.data.order_status != "PAID":
            return render(request, "payment_failed.html", {
                "message": "Payment not completed.",
                "order_id": order_id,
            })

        with transaction.atomic():

            # ─────────────────────────────────────
            # FETCH ORDER
            # ─────────────────────────────────────
            order = PaymentOrder.objects.select_related(
                "athlete", "participation", "participation__gym"
            ).get(order_id=order_id)

            participation = order.participation

            if not participation:
                raise Exception("Participation not linked to order")

            # ─────────────────────────────────────
            # IDEMPOTENCY (VERY IMPORTANT)
            # ─────────────────────────────────────
            if order.status == "success" and participation.payment_status == "success":
                # Already processed → safe return
                athlete = participation.athlete
                gym = participation.gym

            else:

                # ─────────────────────────────────────
                # UPDATE ORDER
                # ─────────────────────────────────────
                order.status = "success"
                order.save()

                # ─────────────────────────────────────
                # UPDATE PARTICIPATION
                # ─────────────────────────────────────
                participation.payment_status = "success"
                participation.is_confirmed = True
                participation.save()

                athlete = participation.athlete
                gym = participation.gym

        # ─────────────────────────────────────────
        # EMAIL 7 — ATHLETE CONFIRMATION
        # ─────────────────────────────────────────
        if athlete.email:
            email_html = f"""
            <h2>Registration Successful. You Are a Titan.</h2>
            <p>Dear {athlete.name},</p>

            <p>Your Tracking ID:</p>
            <h1>{participation.tracking_id}</h1>

            <p>Event: {participation.event_leg}</p>
            <p>Gym: {gym.name if gym else 'Independent Athlete'}</p>

            <p>Save your Tracking ID for future communication.</p>
            """

            # send_got_email(
            #     subject="You're a Titan. Welcome to Game of Titans.",
            #     to_email=athlete.email,
            #     html_content=email_html
            # )

        # ─────────────────────────────────────────
        # EMAIL 8 — EMPLOYEE NOTIFICATION
        # ─────────────────────────────────────────
        if participation.athlete.got_employee:
            emp = participation.athlete.got_employee

            # send_internal_alert(
            #     subject=f"New Athlete Registered Under You — {athlete.name}",
            #     message=f"""
            #     Athlete: {athlete.name}
            #     Phone: {athlete.phone}
            #     Tracking ID: {participation.tracking_id}
            #     Event: {participation.event_leg}
            #     """
            # )

        # ─────────────────────────────────────────
        # SUCCESS PAGE
        # ─────────────────────────────────────────
        context = {
            "order_id": order.order_id,
            "tracking_id": participation.tracking_id,
            "amount": f"₹{order.amount}",
            "athlete_name": athlete.name,
            "gym_name": gym.name if gym else "Independent Athlete",
            "event_leg": participation.event_leg,
        }

        return render(request, "payment_success.html", context)


    except PaymentOrder.DoesNotExist:
        # send_satya_technical_ping("Payment Success Error", "Order not found. Contact support.")
        return render(request, "payment_error.html", {
            "message": "Order not found. Contact support."
        })

    except Exception as e:
        # send_satya_technical_ping("Payment Success Error", str(e))
        print("Payment Success Error:", str(e))
        return render(request, "payment_error.html", {
            "message": "Something went wrong. Contact support."
        })


# ─────────────────────────────────────────────
# CASHFREE WEBHOOK
# ─────────────────────────────────────────────
@csrf_exempt
@permission_classes([AllowAny])
def cashfree_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Method not allowed")

    raw_body = request.body
    signature = request.headers.get('x-webhook-signature')
    timestamp = request.headers.get('x-webhook-timestamp')

    if not signature or not timestamp:
        return HttpResponseBadRequest("Missing webhook headers")

    if not verify_cashfree_signature(raw_body, signature):
        return HttpResponseBadRequest("Invalid webhook signature")

    try:
        payload = json.loads(raw_body)
        data = payload.get('data', {})
        order_data = data.get('order', {})
        payment_data = data.get('payment', {})

        order_id = order_data.get('order_id')
        cf_payment_id = payment_data.get('cf_payment_id')
        payment_status = payment_data.get('payment_status')

        if not order_id:
            return HttpResponse("Missing order_id — acknowledged", status=200)

        try:
            order = PaymentOrder.objects.get(order_id=order_id)
        except PaymentOrder.DoesNotExist:
            return HttpResponse("Order not found — acknowledged", status=200)

        if order.status == 'PAID':
            return HttpResponse("Already processed", status=200)

        order.pg_response = json.dumps(payload)

        if payment_status == 'SUCCESS':
            order.status = 'PAID'
        elif payment_status in ['FAILED', 'USER_DROPPED']:
            order.status = payment_status

            # ── Payment failure alert ──────────────────────────────────
            member = order.member
            import datetime
            # send_internal_alert(
            #     subject=f"Payment Failure — {member.name if member else 'Unknown'} | Order {order_id}",
            #     message=(
            #         f"Payment failed via Cashfree webhook.\n\n"
            #         f"Athlete: {member.name if member else 'N/A'}\n"
            #         f"Email: {member.email if member else 'N/A'}\n"
            #         f"Phone: {member.contact_number if member else 'N/A'}\n"
            #         f"Amount: ₹{order.amount}\n"
            #         f"Order ID: {order_id}\n"
            #         f"Payment Status: {payment_status}\n"
            #         f"CF Payment ID: {cf_payment_id}\n"
            #         f"Timestamp: {datetime.datetime.now()}\n\n"
            #         f"Action required: Contact the athlete if needed."
            #     )
            # )
        else:
            order.status = 'UNKNOWN'

        order.save()
        return HttpResponse(f"Processed: {payment_status}", status=200)

    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload")
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return HttpResponse("Error acknowledged", status=200)


def verify_cashfree_signature(raw_body: bytes, received_signature: str) -> bool:
    webhook_secret = getattr(settings, 'CASHFREE_WEBHOOK_SECRET', None)
    if not webhook_secret:
        print("WARNING: CASHFREE_WEBHOOK_SECRET not set — skipping verification")
        return True  # Don't block in production if secret not configured yet

    try:
        computed_hmac = hmac.new(
            key=webhook_secret.encode('utf-8'),
            msg=raw_body,
            digestmod=hashlib.sha256
        ).digest()
        computed_signature = base64.b64encode(computed_hmac).decode('utf-8')
        return hmac.compare_digest(computed_signature, received_signature)
    except Exception as e:
        print(f"Signature verification error: {str(e)}")
        return False


# ─────────────────────────────────────────────
# SPONSOR
# ─────────────────────────────────────────────
@require_POST
def create_sponsor(request):
    # 🔐 VERIFY RECAPTCHA
    # token = request.POST.get("recaptcha_token")
    #
    # if not token:
    #     return JsonResponse({
    #         "success": False,
    #         "error": "Captcha missing"
    #     }, status=400)
    #
    # result = verify_recaptcha(token)

    # if not result.get("success") or result.get("score", 0) < 0.5:
    #     return JsonResponse({
    #         "success": False,
    #         "error": "Captcha verification failed"
    #     }, status=400)
    print(request.POST)
    name = request.POST.get("name", "").strip()
    company = request.POST.get("company", "").strip()

    if not name or not company:
        return JsonResponse({
            "success": False,
            "error": "Name and company are required."
        }, status=400)

    if Sponsor.objects.filter(name=name, company=company).exists():
        return JsonResponse({
            "success": False,
            "error": "Already submitted."
        }, status=400)

    sponsor = Sponsor.objects.create(
        name=name,
        company=company,
        email=request.POST.get("email") or None,
        phone=request.POST.get("contact_number") or None,
        message=request.POST.get("message") or None,
    )

    # send_internal_alert(
    #     subject=f"New Sponsor Inquiry — {company}",
    #     message=f"{name} submitted inquiry"
    # )

    return JsonResponse({
        "success": True
    })


def verify_recaptcha(token):
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": settings.RECAPTCHA_SECRET_KEY,
            "response": token
        }
    )
    return response.json()

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def get_stats(request):
    gyms = Gym.objects.count()
    athletes = Athlete.objects.count()
    participations = Participation.objects.filter(payment_status="success").count()

    return Response({
        "gyms": gyms,
        "athletes": athletes,
        "participations": participations
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_employees(request):
    """
    Returns all active GOT employees for dropdown.
    """

    employees = GOTEmployee.objects.filter(is_active=True).order_by('name')

    data = [
        {
            "id": emp.id,
            "name": emp.name,
            "code": emp.code,
            "city": emp.city,
            "event_leg": emp.event_leg
        }
        for emp in employees
    ]

    return Response(data)


# ─────────────────────────────────────────────
# LEGAL PAGES — FIXED (were returning 404)
# ─────────────────────────────────────────────
@require_GET
def get_terms_policy(request):
    return render(request, 'pages/terms.html')


@require_GET
def get_privacy_policy(request):
    return render(request, 'pages/privacy.html')


@require_GET
def get_refund_policy(request):
    return render(request, 'pages/refund.html')


# ─────────────────────────────────────────────
# PAGE VIEWS
# ─────────────────────────────────────────────
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
