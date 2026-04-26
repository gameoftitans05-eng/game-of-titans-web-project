"""
URL configuration for titan_api_proj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from api.admin import admin_site
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from api import registration_views
from api.dashboard import incentive_dashboard


urlpatterns = [
    path('superadmin/', admin.site.urls),
    path('admin/dashboard/', incentive_dashboard),
    path('admin/', admin_site.urls),
    path('api/v1/', include('api.urls')),

    path('', TemplateView.as_view(template_name='index.html'), name='home'),

    path('mumbai/', registration_views.mumbai, name='mumbai'),
    path('delhi/', registration_views.delhi, name='delhi'),
    path('bengaluru/', registration_views.bengaluru, name='bengaluru'),

    path('register/', registration_views.register, name='register'),
    path('sponsors/', registration_views.sponsors, name='sponsors'),
    path('about/', registration_views.about, name='about'),

    path('terms/', registration_views.get_terms_policy, name='terms'),
    path('privacy/', registration_views.get_privacy_policy, name='privacy'),
    path('refund/', registration_views.get_refund_policy, name='refund'),

]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
