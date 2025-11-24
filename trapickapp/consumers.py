# trapickapp/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# Import the functions directly
from .progress import get_all_active_progress, progress_store

class VideoProgressConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for individual video progress tracking"""
    
    async def connect(self):
        self.video_id = self.scope['url_route']['kwargs']['video_id']
        self.room_group_name = f'video_progress_{self.video_id}'
        
        logger.info(f"🔌 VIDEO CONSUMER CONNECT: video_id={self.video_id}")
        logger.info(f"🔌 Group name: {self.room_group_name}")
        logger.info(f"🔌 User: {self.scope.get('user', 'Anonymous')}")
        
        # Accept first
        await self.accept()
        logger.info(f"✅ VIDEO CONSUMER ACCEPTED: {self.video_id}")
        
        # Then join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"✅ VIDEO CONSUMER JOINED GROUP: {self.room_group_name}")
        
        # Send current progress immediately upon connection
        progress_data = progress_store.get(self.video_id)
        if progress_data:
            logger.info(f"📤 Sending initial progress: {progress_data}")
            await self.send(text_data=json.dumps({
                'type': 'progress_update',
                'video_id': self.video_id,
                'progress': progress_data['progress'],
                'message': progress_data['message'],
                'status': 'processing'
            }))
            logger.info(f"✅ Sent initial progress: {progress_data['progress']}%")
        else:
            logger.warning(f"⚠️ No initial progress data found for {self.video_id}")
    
    async def disconnect(self, close_code):
        logger.info(f"🔌 VIDEO CONSUMER DISCONNECT: {self.video_id}, code={close_code}")
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f"✅ VIDEO CONSUMER LEFT GROUP: {self.room_group_name}")
        except Exception as e:
            logger.error(f"❌ Error leaving group: {e}")
    
    async def receive(self, text_data):
        """Handle messages from client"""
        logger.info(f"📨 VIDEO CONSUMER RECEIVED: {self.video_id} - {text_data}")
        try:
            data = json.loads(text_data)
            logger.info(f"📨 Parsed data: {data}")
        except Exception as e:
            logger.error(f"❌ Error parsing client message: {e}")
    
    async def progress_update(self, event):
        """Handle progress update messages"""
        logger.info(f"📊 VIDEO CONSUMER PROGRESS_UPDATE: video_id={self.video_id}")
        logger.info(f"📊 Event data: {json.dumps(event, default=str)}")
        
        try:
            message = {
                'type': 'progress_update',
                'video_id': event.get('video_id', self.video_id),
                'progress': event['progress'],
                'message': event['message'],
                'status': 'processing'
            }
            
            logger.info(f"📤 Sending progress to client: {message}")
            await self.send(text_data=json.dumps(message))
            logger.info(f"✅ VIDEO CONSUMER SENT PROGRESS: {event['progress']}%")
            
        except Exception as e:
            logger.error(f"❌ VIDEO CONSUMER PROGRESS SEND ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    async def processing_complete(self, event):
        """Handle processing complete messages"""
        logger.info(f"🎉🎉🎉 VIDEO CONSUMER PROCESSING_COMPLETE: video_id={self.video_id}")
        logger.info(f"🎉 Event data: {json.dumps(event, indent=2, default=str)}")
        
        try:
            completion_message = {
                'type': 'processing_complete',
                'video_id': event.get('video_id', self.video_id),
                'message': event.get('message', 'Processing completed!'),
                'progress': 100,
                'status': 'completed'
            }
            
            # CRITICAL: Include video_info at root level
            if 'video_info' in event:
                completion_message['video_info'] = event['video_info']
                logger.info(f"📋 VIDEO CONSUMER - VIDEO_INFO FOUND: {event['video_info']}")
            else:
                logger.error("❌❌❌ VIDEO CONSUMER - NO VIDEO_INFO IN EVENT!")
                
                # Try to get from progress store as fallback
                stored_data = progress_store.get(self.video_id, {})
                if 'video_info' in stored_data:
                    completion_message['video_info'] = stored_data['video_info']
                    logger.info(f"📋 Using fallback video_info from store: {stored_data['video_info']}")
                else:
                    logger.error("❌ No fallback video_info available!")
            
            logger.info(f"📤 VIDEO CONSUMER SENDING COMPLETION: {json.dumps(completion_message, indent=2)}")
            
            await self.send(text_data=json.dumps(completion_message))
            
            logger.info(f"✅✅✅ VIDEO CONSUMER SUCCESS! Completion sent to client!")
            
        except Exception as e:
            logger.error(f"❌ VIDEO CONSUMER COMPLETION SEND ERROR: {e}")
            import traceback
            traceback.print_exc()

    async def processing_failed(self, event):
        """Handle processing failed messages"""
        logger.info(f"❌ VIDEO CONSUMER PROCESSING_FAILED: video_id={self.video_id}")
        logger.info(f"❌ Event data: {json.dumps(event, default=str)}")
        
        try:
            failure_message = {
                'type': 'processing_failed',
                'video_id': event['video_id'],
                'message': event['message'],
                'progress': 0,
                'status': 'failed'
            }
            
            if 'error_details' in event:
                failure_message['error_details'] = event['error_details']
                logger.info(f"📋 Including error details: {event['error_details']}")
            
            await self.send(text_data=json.dumps(failure_message))
            logger.info(f"✅ VIDEO CONSUMER sent failure message")
            
        except Exception as e:
            logger.error(f"❌ VIDEO CONSUMER FAILURE SEND ERROR: {e}")


class GeneralProgressConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for all active video progress (for sidebar)"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            logger.info("🔌 GENERAL CONSUMER CONNECT ATTEMPT")
            
            # Set group name
            self.room_group_name = 'general_progress'
            
            # Accept connection FIRST
            await self.accept()
            logger.info("✅ GENERAL CONSUMER CONNECTION ACCEPTED")
            
            # Join group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            logger.info("✅ GENERAL CONSUMER JOINED general_progress GROUP")
            
            # Send minimal initial data to test connection
            initial_data = {
                'type': 'connection_established',
                'message': 'WebSocket connected successfully',
                'progress_data': {}
            }
            
            await self.send(text_data=json.dumps(initial_data))
            logger.info("✅ GENERAL CONSUMER Initial data sent")
            
        except Exception as e:
            logger.error(f"❌ GENERAL CONSUMER Connect Error: {e}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"🔌 GENERAL CONSUMER DISCONNECT: code={close_code}")
        try:
            if hasattr(self, 'room_group_name'):
                await self.channel_layer.group_discard(
                    self.room_group_name,
                    self.channel_name
                )
                logger.info("✅ GENERAL CONSUMER LEFT general_progress GROUP")
        except Exception as e:
            logger.error(f"❌ Error leaving group: {e}")
    
    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
            logger.info(f"📨 GENERAL CONSUMER Received: {data.get('type', 'unknown')}")
            
            # Echo back for testing
            await self.send(text_data=json.dumps({
                'type': 'echo',
                'message': 'Message received',
                'your_data': data
            }))
        except Exception as e:
            logger.error(f"❌ GENERAL CONSUMER Error parsing message: {e}")
    
    # ===== ADD THESE HANDLER METHODS ===== #
    
    async def progress_update(self, event):
        """Handle progress update messages from Celery"""
        logger.info(f"📊 GENERAL CONSUMER PROGRESS_UPDATE")
        logger.info(f"📊 Event data: {json.dumps(event, default=str)}")
        
        try:
            message = {
                'type': 'progress_update',
                'video_id': event['video_id'],
                'progress': event['progress'],
                'message': event['message'],
                'status': 'processing'
            }
            
            logger.info(f"📤 GENERAL: Sending progress to client: {message}")
            await self.send(text_data=json.dumps(message))
            logger.info(f"✅ GENERAL CONSUMER sent progress update")
            
        except Exception as e:
            logger.error(f"❌ GENERAL CONSUMER PROGRESS ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    async def processing_complete(self, event):
        """Handle processing complete messages from Celery"""
        logger.info(f"🎉 GENERAL CONSUMER PROCESSING_COMPLETE")
        logger.info(f"🎉 Event data: {json.dumps(event, indent=2, default=str)}")
        
        try:
            completion_message = {
                'type': 'processing_complete',
                'video_id': event.get('video_id'),
                'message': event.get('message', 'Processing completed!'),
                'progress': 100,
                'status': 'completed'
            }
            
            # CRITICAL: Include video_info
            if 'video_info' in event:
                completion_message['video_info'] = event['video_info']
                logger.info(f"📋 GENERAL: Including video_info: {event['video_info']}")
            else:
                logger.warning("⚠️ GENERAL: No video_info in completion event!")
            
            logger.info(f"📤 GENERAL: Sending completion: {json.dumps(completion_message, indent=2)}")
            await self.send(text_data=json.dumps(completion_message))
            logger.info(f"✅ GENERAL CONSUMER sent completion message")
            
        except Exception as e:
            logger.error(f"❌ GENERAL CONSUMER COMPLETION ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    async def processing_failed(self, event):
        """Handle processing failed messages from Celery"""
        logger.info(f"❌ GENERAL CONSUMER PROCESSING_FAILED")
        logger.info(f"❌ Event data: {json.dumps(event, default=str)}")
        
        try:
            failure_message = {
                'type': 'processing_failed',
                'video_id': event['video_id'],
                'message': event['message'],
                'progress': 0,
                'status': 'failed'
            }
            
            if 'error_details' in event:
                failure_message['error_details'] = event['error_details']
            
            await self.send(text_data=json.dumps(failure_message))
            logger.info(f"✅ GENERAL CONSUMER sent failure message")
            
        except Exception as e:
            logger.error(f"❌ GENERAL CONSUMER FAILURE ERROR: {e}")


class NotificationConsumer(AsyncWebsocketConsumer):
    """General notification consumer"""
    
    async def connect(self):
        logger.info(f"🔌 NOTIFICATION CONSUMER CONNECT")
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'WebSocket connection established'
        }))
        logger.info("✅ NOTIFICATION CONSUMER connected")
    
    async def disconnect(self, close_code):
        logger.info(f"🔌 NOTIFICATION CONSUMER DISCONNECT: {close_code}")
    
    async def receive(self, text_data):
        logger.info(f"📨 NOTIFICATION CONSUMER RECEIVED: {text_data}")
        pass