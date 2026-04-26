from datetime import timedelta
from django.utils import timezone
from api.models import Participation, IncentiveConfig


def get_last_week_range():
    today = timezone.now().date()
    start = today - timedelta(days=today.weekday() + 7)
    end = start + timedelta(days=6)
    return start, end


def calculate_weekly_summary():
    start, end = get_last_week_range()

    qs = Participation.objects.filter(
        payment_status="success",
        # created_at__date__range=[start, end]
    )

    total = qs.count()

    gross = total * 1999
    gateway = total * 40
    incentive_budget = total * 700
    net = gross - gateway - incentive_budget
    iqbal_cut = net * 0.07

    return {
        "total": total,
        "gross": gross,
        "gateway": gateway,
        "budget": incentive_budget,
        "net": net,
        "iqbal": iqbal_cut,
        "start": start,
        "end": end
    }

def calculate_gym_payouts():
    config = IncentiveConfig.objects.filter(is_active=True).first()

    if not config or not config.gym_rate:
        return []

    data = []

    gyms = Participation.objects.filter(
        payment_status="success"
    ).exclude(gym=None).values("gym").distinct()

    for g in gyms:
        gym_id = g["gym"]

        count = Participation.objects.filter(
            gym_id=gym_id,
            payment_status="success"
        ).count()

        data.append({
            "gym_id": gym_id,
            "count": count,
            "payout": count * config.gym_rate
        })

    return data


def calculate_employee_payouts():
    config = IncentiveConfig.objects.filter(is_active=True).first()

    if not config or not config.employee_rate:
        return []

    data = []

    qs = Participation.objects.filter(payment_status="success")

    for p in qs:
        emp = p.athlete.got_employee
        if not emp:
            continue

        data.append(emp.id)

    from collections import Counter
    counts = Counter(data)

    return [
        {
            "employee_id": emp_id,
            "count": count,
            "payout": count * config.employee_rate
        }
        for emp_id, count in counts.items()
    ]