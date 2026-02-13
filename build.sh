#!/usr/bin/env bash
# build.sh - Build script for Trapick Cloud deployment
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

# ============================================
# REACT FRONTEND BUILD
# ============================================
echo ""
echo "=================================================="
echo "⚛️  BUILDING REACT FRONTEND"
echo "=================================================="

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
    echo "❌ ERROR: frontend/ directory not found!"
    echo "   Make sure your repository includes the frontend folder"
    exit 1
fi

cd frontend

# Install Node dependencies
echo "📦 Installing Node.js dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi

# Build the React application (DISABLE CI MODE TO ALLOW WARNINGS)
echo "🏗️  Building React app for production..."
echo "   ⚠️  Setting CI=false to allow ESLint warnings during build"
CI=false npm run build

# Verify the build succeeded
if [ ! -f "build/index.html" ]; then
    echo "❌ ERROR: React build failed - index.html not found!"
    echo "   Check the npm build output above for errors"
    exit 1
fi

echo "✅ React build successful - index.html created"
echo "📂 Build directory contents:"
ls -lh build/

# Return to project root
cd ..

echo "=================================================="
echo "⚛️  REACT BUILD COMPLETE"
echo "=================================================="
echo ""

# ============================================
# DJANGO SETUP
# ============================================

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

echo ""
echo "=================================================="
echo "✅ BUILD COMPLETE!"
echo "=================================================="
echo "📋 Build Summary:"
echo "  ✓ Python dependencies installed"
echo "  ✓ React frontend built (with CI=false)"
echo "  ✓ Static files collected"
echo "  ✓ Database migrations applied"
echo "  ✓ Default data initialized"
echo "=================================================="