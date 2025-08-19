import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from .models import TrafficAnalysis, TrafficPrediction
from datetime import datetime

def analyze_traffic_patterns():
    # Get all traffic data
    data = TrafficAnalysis.objects.all().values()
    df = pd.DataFrame(data)
    
    if df.empty:
        return None
    
    # Aggregate by day and hour
    daily_hourly = df.groupby(['day_of_week', 'hour_of_day']).agg({
        'vehicle_count': 'mean'
    }).reset_index()
    
    # Find peak times
    max_congestion = daily_hourly.loc[daily_hourly['vehicle_count'].idxmax()]
    
    return {
        'daily_hourly': daily_hourly.to_dict('records'),
        'peak_day': int(max_congestion['day_of_week']),
        'peak_hour': int(max_congestion['hour_of_day']),
        'peak_volume': float(max_congestion['vehicle_count'])
    }

def predict_congestion():
    # Get historical data
    data = TrafficAnalysis.objects.all().values()
    df = pd.DataFrame(data)
    
    if df.empty:
        return
    
    # Prepare features and target
    X = df[['day_of_week', 'hour_of_day']]
    y = df['vehicle_count']
    
    # Train model
    model = RandomForestRegressor()
    model.fit(X, y)
    
    # Predict for all possible day/hour combinations
    predictions = []
    for day in range(7):
        for hour in range(24):
            pred = model.predict([[day, hour]])[0]
            predictions.append({
                'day_of_week': day,
                'hour_of_day': hour,
                'predicted_congestion': pred
            })
    
    # Save predictions
    TrafficPrediction.objects.all().delete()  # Clear old predictions
    for pred in predictions:
        TrafficPrediction.objects.create(**pred)