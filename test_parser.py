import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

from trapickapp.utils.filename_parser import CCTVFilenameParser

# Test cases
test_files = [
    'D11_20250903122635.mp4',  # Your example
    'D12_20250903050000.mp4',  # 5:00 AM
    'D11_20250903220000.mp4',  # 10:00 PM
    'invalid_filename.mp4',     # Should fail
    'CAM01_20250903_120000.mp4', # Different pattern
]

print("🧪 Testing Filename Parser")
print("=" * 50)

for filename in test_files:
    result = CCTVFilenameParser.parse_filename(filename)
    status = "✅ SUCCESS" if result else "❌ FAILED"
    print(f"{status}: {filename}")
    if result:
        print(f"   Camera: {result['camera_id']}")
        print(f"   Date: {result['date']}")
        print(f"   Time: {result['time']}")
        print(f"   DateTime: {result['datetime']}")
    print()