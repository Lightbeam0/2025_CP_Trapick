@echo off
echo.
echo ================================================
echo           TRAPICK CLOUD SYNC
echo ================================================
echo.
echo Checking sync status...
python manage.py check_sync_status
echo.
set /p confirm="Do you want to sync this data to cloud? (y/n): "
if /i "%confirm%"=="y" (
    echo.
    echo Syncing to cloud...
    python manage.py sync_to_cloud
    echo.
    echo Done! Visit https://trapick-cloud.onrender.com to view
    pause
) else (
    echo Sync cancelled.
    pause
)