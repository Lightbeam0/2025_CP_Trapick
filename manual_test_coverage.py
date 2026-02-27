# manual_test_coverage.py
"""
Run this with: python manage.py shell < manual_test_coverage.py
"""

from trapickapp.models import LocationDateGroup

print("="*70)
print("🧪 TESTING COVERAGE TRACKING")
print("="*70)

# Get all groups
groups = LocationDateGroup.objects.all()

if not groups.exists():
    print("❌ No groups found. Process some videos first.")
else:
    for group in groups[:3]:
        print(f"\n📍 Testing group: {group.location.display_name} - {group.date}")
        
        # Calculate coverage metrics
        print("   Calculating coverage metrics...")
        coverage = group.calculate_coverage_metrics()
        
        print(f"   ✅ Total coverage: {coverage['total_coverage_minutes']} minutes")
        print(f"   ✅ Continuity score: {coverage['continuity_score']}%")
        print(f"   ✅ Segments: {len(coverage['segments'])}")
        print(f"   ✅ Gaps detected: {len(coverage['coverage_gaps'])}")
        
        # Get detailed time range
        print("\n   Getting detailed time range...")
        detailed = group.get_detailed_time_range()
        
        print(f"   ✅ Full range: {detailed['full_range']}")
        print(f"   ✅ Coverage %: {detailed['coverage_percentage']}%")
        
        if detailed['gaps']:
            print(f"   ⚠️ Gaps found:")
            for gap in detailed['gaps']:
                print(f"      - {gap['start']} to {gap['end']} ({gap['duration']} min)")
        
        # Calculate hourly distribution
        print("\n   Calculating hourly distribution...")
        hourly = group.calculate_hourly_distribution()
        
        # Show top 3 hours
        top_hours = sorted(hourly.items(), key=lambda x: x[1]['vehicles'], reverse=True)[:3]
        print(f"   ✅ Top hours:")
        for hour, data in top_hours:
            print(f"      - {hour:02d}:00: {data['vehicles']} vehicles ({data['minutes']} min recorded)")
        
        # Get coverage summary
        summary = group.get_coverage_summary()
        print(f"\n   📊 Summary: {summary['text']}")
        
        print("\n   " + "-"*50)

print("\n✅ Coverage tracking test complete!")