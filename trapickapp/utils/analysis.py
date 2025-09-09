import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from ..models import HourlyTrafficSummary, TrafficPrediction
from datetime import datetime

def analyze_traffic_patterns():
    # Get all hourly traffic summary data
    data = HourlyTrafficSummary.objects.all().values(
        'date', 'hour', 'vehicle_type__name', 'count'
    )
    df = pd.DataFrame(data)

    if df.empty:
        return None

    # Add derived fields
    df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
    df['hour_of_day'] = df['hour']
    df['vehicle_count'] = df['count']

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
    data = HourlyTrafficSummary.objects.all().values(
        'date', 'hour', 'vehicle_type__id', 'count'
    )
    df = pd.DataFrame(data)

    if df.empty:
        return

    # Prepare features and target
    df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
    X = df[['day_of_week', 'hour']]
    y = df['count']

    # Train model
    model = RandomForestRegressor()
    model.fit(X, y)

    # Predict for all possible day/hour combinations
    predictions = []
    for day in range(7):
        for hour in range(24):
            pred = model.predict([[day, hour]])[0]
            predictions.append({
                'prediction_date': datetime.today().date(),
                'hour': hour,
                'vehicle_type_id': df['vehicle_type__id'].iloc[0],  # simple assumption
                'predicted_count': pred,
                'confidence_interval_lower': pred * 0.9,
                'confidence_interval_upper': pred * 1.1,
                'model_version': "v1"
            })

    # Save predictions
    TrafficPrediction.objects.all().delete()  # Clear old predictions
    for pred in predictions:
        TrafficPrediction.objects.create(**pred)

