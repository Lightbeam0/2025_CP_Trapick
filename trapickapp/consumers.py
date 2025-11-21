# trapickapp/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
import asyncio

# Import the functions directly (they're now defined in progress.py)
from .progress import get_all_active_progress, progress_store

class VideoProgressConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for individual video progress tracking"""
    
    async def connect(self):
        self.video_id = self.scope['url_route']['kwargs']['video_id']
        self.room_group_name = f'video_progress_{self.video_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        print(f"✅ WebSocket connected for video {self.video_id}")
        
        # Send current progress immediately upon connection
        progress_data = progress_store.get(self.video_id)
        if progress_data:
            await self.send(text_data=json.dumps({
                'type': 'progress_update',
                'video_id': self.video_id,
                'progress': progress_data['progress'],
                'message': progress_data['message'],
                'status': 'processing'
            }))
            print(f"📤 Sent initial progress: {progress_data['progress']}%")
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"❌ WebSocket disconnected for video {self.video_id}")
    
    async def progress_update(self, event):
        """Handle progress update messages"""
        print(f" imap VideoProgressConsumer received progress: {event}")
        await self.send(text_data=json.dumps({
            'type': 'progress_update',
            'video_id': event.get('video_id', self.video_id),
            'progress': event['progress'],
            'message': event['message'],
            'status': 'processing'
        }))
    
    async def processing_complete(self, event):
        """Handle processing complete messages"""
        print(f"🎉 VideoProgressConsumer received completion: {event}")
        
        # Build completion message with ALL data
        completion_message = {
            'type': 'processing_complete',
            'video_id': event['video_id'],
            'message': event['message'],
            'progress': 100,
            'status': 'completed'
        }
        
        # Include video_info if available
        if 'video_info' in event:
            completion_message['video_info'] = event['video_info']
            print(f"📋 Forwarding video_info to video consumer: {event['video_info']}")
        
        await self.send(text_data=json.dumps(completion_message))
        print(f"✅ Sent completion message to video client: {completion_message}")

    async def processing_failed(self, event):
        """Handle processing failed messages"""
        print(f"❌ VideoProgressConsumer received failure: {event}")
        await self.send(text_data=json.dumps({
            'type': 'processing_failed',
            'video_id': event['video_id'],
            'message': event['message'],
            'progress': 0,
            'status': 'failed'
        }))

class GeneralProgressConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for all active video progress (for sidebar)"""
    
    async def connect(self):
        try:
            print(f"🔌 WebSocket connection attempt received!")
            print(f"🔌 Path: {self.scope['path']}")
            
            self.room_group_name = 'general_progress'
            
            # Join general progress group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
            print("✅ WebSocket connected for general progress")
            
            # Send all active progress immediately
            all_progress = get_all_active_progress()
            print(f"📤 Sending initial progress for {len(all_progress)} videos")
            
            await self.send(text_data=json.dumps({
                'type': 'all_progress',
                'progress_data': all_progress
            }))
            print(f"✅ Sent initial progress for {len(all_progress)} videos")
            
        except Exception as e:
            print(f"❌ Error in WebSocket connect: {e}")
            await self.accept()

    async def disconnect(self, close_code):
        print(f"❌ WebSocket disconnected from general progress. Code: {close_code}")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def progress_update(self, event):
        """Handle progress updates from any video"""
        print(f" imap GeneralProgressConsumer received progress: {event}")
        await self.send(text_data=json.dumps({
            'type': 'progress_update',
            'video_id': event['video_id'],
            'progress': event['progress'],
            'message': event['message'],
            'status': 'processing'
        }))
    
    async def processing_complete(self, event):
        """Handle processing complete from any video"""
        print(f"🎉 GeneralProgressConsumer received completion: {event}")
        
        # Build completion message with ALL data
        completion_message = {
            'type': 'processing_complete',
            'video_id': event['video_id'],
            'message': event['message'],
            'progress': 100,
            'status': 'completed'
        }
        
        # Include video_info if available - THIS IS CRITICAL!
        if 'video_info' in event:
            completion_message['video_info'] = event['video_info']
            print(f"📋 Forwarding video_info to general consumer: {event['video_info']}")
        else:
            print("⚠️ No video_info found in completion event!")
        
        await self.send(text_data=json.dumps(completion_message))
        print(f"✅ Sent completion message to general client: {completion_message}")
    
    async def processing_failed(self, event):
        """Handle processing failed from any video"""
        print(f"❌ GeneralProgressConsumer received failure: {event}")
        await self.send(text_data=json.dumps({
            'type': 'processing_failed',
            'video_id': event['video_id'],
            'message': event['message'],
            'progress': 0,
            'status': 'failed'
        }))

class NotificationConsumer(AsyncWebsocketConsumer):
    """General notification consumer"""
    
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