# trapickapp/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import VideoFile
from .progress import progress_store
import asyncio

class VideoProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.video_id = self.scope['url_route']['kwargs']['video_id']
        self.room_group_name = f'video_progress_{self.video_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send current progress immediately upon connection
        progress_data = progress_store.get(self.video_id)
        if progress_data:
            await self.send(text_data=json.dumps({
                'type': 'progress_update',
                'progress': progress_data['progress'],
                'message': progress_data['message']
            }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def progress_update(self, event):
        # Send progress update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'progress_update',
            'progress': event['progress'],
            'message': event['message']
        }))

    async def processing_complete(self, event):
        # Send completion notification
        await self.send(text_data=json.dumps({
            'type': 'processing_complete',
            'video_id': event['video_id'],
            'message': event['message']
        }))

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connection established'
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        pass