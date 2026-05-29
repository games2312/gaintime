import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PushSubscription


@login_required
@csrf_exempt
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body)
        sub, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=data['endpoint'],
            defaults={
                'auth_key': data.get('keys', {}).get('auth', ''),
                'p256dh_key': data.get('keys', {}).get('p256dh', ''),
            }
        )
        return JsonResponse({'status': 'ok', 'created': created})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_POST
def push_unsubscribe(request):
    try:
        data = json.loads(request.body) if request.body else {}
        endpoint = data.get('endpoint', '')
        if endpoint:
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        else:
            PushSubscription.objects.filter(user=request.user).delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


@login_required
def push_settings(request):
    enabled = PushSubscription.objects.filter(user=request.user).exists()
    return JsonResponse({'enabled': enabled})
