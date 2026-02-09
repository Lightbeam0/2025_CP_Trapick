# build.sh - Build script for Trapick Cloud deployment
#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "=================================================="
echo "🚀 TRAPICK CLOUD BUILD SCRIPT"
echo "=================================================="

# 1. Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# 2. Install Python dependencies (cloud version only)
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# 3. Collect static files for serving
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input --clear

# 4. Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --no-input

# 5. Create default vehicle types (if needed)
echo "🚗 Setting up default vehicle types..."
python manage.py shell << EOF
from trapickapp.models import VehicleType
vehicle_types = ['car', 'truck', 'motorcycle', 'bus', 'bicycle', 'other']
for vt_name in vehicle_types:
    VehicleType.objects.get_or_create(
        name=vt_name,
        defaults={'display_name': vt_name.capitalize()}
    )
print("✓ Vehicle types ready")
EOF

echo "=================================================="
echo "✅ BUILD COMPLETE!"
echo "=================================================="