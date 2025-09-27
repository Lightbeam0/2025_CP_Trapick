# create_initial_data.py
import os
import django
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.models import VehicleType, Location

def create_initial_data():
    print("Creating initial data...")
    
    # Create vehicle types
    vehicle_types = [
        'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'other'
    ]
    
    for vehicle_name in vehicle_types:
        VehicleType.objects.get_or_create(name=vehicle_name)
        print(f"✓ Created vehicle type: {vehicle_name}")
    
    # Create Zamboanga City locations
    zamboanga_locations = [
        {
            'name': 'baliwasan',
            'display_name': 'Baliwasan Area',
            'description': 'Major intersection near Baliwasan'
        },
        {
            'name': 'sanroque', 
            'display_name': 'San Roque',
            'description': 'San Roque intersection'
        },
        {
            'name': 'downtown',
            'display_name': 'Downtown Zamboanga', 
            'description': 'City center area'
        },
        {
            'name': 'tetuan',
            'display_name': 'Tetuan',
            'description': 'Tetuan commercial area'
        },
        {
            'name': 'guiwan',
            'display_name': 'Guiwan',
            'description': 'Guiwan area'
        }
    ]
    
    for loc_data in zamboanga_locations:
        Location.objects.get_or_create(
            name=loc_data['name'],
            defaults={
                'display_name': loc_data['display_name'],
                'description': loc_data['description']
            }
        )
        print(f"✓ Created location: {loc_data['display_name']}")
    
    print("✓ Initial data creation completed!")

if __name__ == "__main__":
    create_initial_data()