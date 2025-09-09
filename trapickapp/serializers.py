# trapickapp/serializers.py
from rest_framework import serializers
from .models import VideoFile, Detection, HourlyTrafficSummary, DailyTrafficSummary, TrafficPrediction, VehicleType


class VideoFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoFile
        fields = "__all__"


class DetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detection
        fields = "__all__"


class HourlyTrafficSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = HourlyTrafficSummary
        fields = "__all__"


class DailyTrafficSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyTrafficSummary
        fields = "__all__"


class TrafficPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrafficPrediction
        fields = "__all__"


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = "__all__"
