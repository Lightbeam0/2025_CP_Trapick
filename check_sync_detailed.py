# check_sync_detailed.py
import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trapick.settings')
django.setup()

print("=" * 60)
print("🔍 DETAILED SYNC DIAGNOSTIC")
print("=" * 60)

# 1. Check if classes exist in api_views
print("\n1. Checking api_views.py for sync classes...")
try:
    from trapickapp import api_views
    
    has_sync_status = hasattr(api_views, 'SyncStatusAPI')
    has_sync_execute = hasattr(api_views, 'SyncExecuteAPI')
    has_data_sync = hasattr(api_views, 'DataSyncAPI')
    
    print(f"   SyncStatusAPI: {'✅ Found' if has_sync_status else '❌ Not found'}")
    print(f"   SyncExecuteAPI: {'✅ Found' if has_sync_execute else '❌ Not found'}")
    print(f"   DataSyncAPI: {'✅ Found' if has_data_sync else '❌ Not found'}")
    
    if has_sync_status:
        print(f"   SyncStatusAPI location: {api_views.SyncStatusAPI}")
    if has_sync_execute:
        print(f"   SyncExecuteAPI location: {api_views.SyncExecuteAPI}")
        
except Exception as e:
    print(f"   ❌ Error importing: {e}")

# 2. Check URL patterns
print("\n2. Checking URL registration...")
try:
    from django.urls import get_resolver
    resolver = get_resolver()
    
    # Get all URL patterns
    def get_all_patterns(patterns, prefix=''):
        urls = []
        for pattern in patterns:
            if hasattr(pattern, 'pattern'):
                current = str(pattern.pattern)
                full = prefix + current
                
                if hasattr(pattern, 'url_patterns'):
                    urls.extend(get_all_patterns(pattern.url_patterns, full))
                else:
                    urls.append({
                        'pattern': full,
                        'name': getattr(pattern, 'name', None),
                        'view': str(pattern.callback) if hasattr(pattern, 'callback') else None
                    })
        return urls
    
    all_urls = get_all_patterns(resolver.url_patterns)
    
    # Look for sync URLs
    sync_urls = [u for u in all_urls if 'sync' in u['pattern'].lower()]
    
    if sync_urls:
        print("   ✅ Sync URLs found:")
        for url in sync_urls:
            print(f"      - {url['pattern']}")
            print(f"        name: {url['name']}")
            print(f"        view: {url['view']}")
    else:
        print("   ❌ No sync URLs found")
        
except Exception as e:
    print(f"   ❌ Error checking URLs: {e}")

# 3. Try to import and instantiate the views
print("\n3. Testing view instantiation...")
try:
    from trapickapp.api_views import SyncStatusAPI, SyncExecuteAPI
    
    # Try to create instances
    status_view = SyncStatusAPI()
    execute_view = SyncExecuteAPI()
    
    print("   ✅ Views can be instantiated successfully")
    print(f"   SyncStatusAPI methods: {[m for m in dir(status_view) if not m.startswith('_')][:5]}")
    print(f"   SyncExecuteAPI methods: {[m for m in dir(execute_view) if not m.startswith('_')][:5]}")
    
except Exception as e:
    print(f"   ❌ Error instantiating views: {e}")
    import traceback
    traceback.print_exc()

# 4. Test URL resolution
print("\n4. Testing URL resolution...")
try:
    from django.urls import reverse
    
    try:
        status_url = reverse('sync_status')
        print(f"   ✅ sync_status resolves to: {status_url}")
    except Exception as e:
        print(f"   ❌ sync_status failed: {e}")
    
    try:
        execute_url = reverse('sync_execute')
        print(f"   ✅ sync_execute resolves to: {execute_url}")
    except Exception as e:
        print(f"   ❌ sync_execute failed: {e}")
        
except Exception as e:
    print(f"   ❌ Error testing URL resolution: {e}")

# 5. Check if Django server needs restart
print("\n5. Server status check...")
print("   ⚠️  If URLs are defined but not resolving:")
print("      1. Stop Django server (Ctrl+C)")
print("      2. Restart with: python manage.py runserver")
print("      3. URLs are only loaded at server startup!")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)