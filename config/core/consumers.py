import json
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.utils import timezone

from .models import Notification


class ChatConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_group_name = None

    def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            self.close()
            return
        self.room_group_name = 'chat_global'
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )
        self.accept()
        self.send_json({
            'type': 'system',
            'message': 'Connecté au chat global.',
            'username': user.username,
        })

    def disconnect(self, close_code):
        if self.room_group_name:
            async_to_sync(self.channel_layer.group_discard)(
                self.room_group_name, self.channel_name
            )

    def receive_json(self, content):
        user = self.scope['user']
        message = content.get('message', '').strip()
        if not message:
            return
        if len(message) > 500:
            message = message[:500]
        if timezone.now() - user.last_login < timedelta(seconds=2):
            self.send_json({'type': 'error', 'message': 'Trop rapide !'})
            return
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': user.username,
                'timestamp': timezone.now().isoformat(),
            }
        )

    def chat_message(self, event):
        self.send_json({
            'type': 'message',
            'message': event['message'],
            'username': event['username'],
            'timestamp': event['timestamp'],
        })

class NotificationConsumer(JsonWebsocketConsumer):
    def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            self.close()
            return
        self.user = user
        self.group_name = f'notifications_user_{user.id}'
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        self.send_json({'type': 'count', 'count': unread_count})

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def notify(self, event):
        self.send_json({
            'type': event['type'],
            'count': event.get('count', 0),
            'title': event.get('title', ''),
            'message': event.get('message', ''),
            'url': event.get('url', ''),
        })
