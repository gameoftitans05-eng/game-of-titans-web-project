from django.shortcuts import render
from rest_framework.routers import DefaultRouter
from django.urls import include, path
from . import views
from . import registration_views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

router = DefaultRouter()
# router.register(r'gym', views.GymViewSet, basename='gym')
# router.register(r'members', views.MemberViewSet, basename='member')
# router.register(r'events', views.EventViewSet, basename='event')

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # path(route='test/', view=views.TestAPIView.as_view(), name='test_view'),

    # path('payment/confirm/', views.confirm_participation, name='payment-confirm'),
    path('employees/', registration_views.get_employees, name='get_employees'),

    path('payment/success/', registration_views.payment_success, name='payment-success'),
    # Webhook (Cashfree sends POST here)
    path('webhooks/cashfree/', registration_views.cashfree_webhook, name='cashfree-webhook'),

    path('register-gym/', registration_views.register_gym, name='register-gym'),
    path('initiate-participation/', registration_views.initiate_participation, name='initiate-participation'),
    # path('active-events/', registration_views.active_events_list, name='active-events-list'),

    path('sponsor/create/', registration_views.create_sponsor, name='create-sponsor'),
    path('sponsor/success/', lambda request: render(request, 'sponsor_success.html'), name='sponsor-success'),

    # path('stats/', registration_views.get_stats, name='stats'),

    path('', include(router.urls)),
]
