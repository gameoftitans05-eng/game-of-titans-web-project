from django.shortcuts import render
from api.services.incentive_service import (
    calculate_weekly_summary,
    calculate_gym_payouts,
    calculate_employee_payouts
)
from api.models import IncentiveConfig


def incentive_dashboard(request):
    summary = calculate_weekly_summary()
    gym_data = calculate_gym_payouts()
    employee_data = calculate_employee_payouts()

    config = IncentiveConfig.objects.filter(is_active=True).first()

    context = {
        "summary": summary,
        "gym_data": gym_data,
        "employee_data": employee_data,
        "config": config
    }

    return render(request, "dashboard/incentive_dashboard.html", context)