# trapickapp/management/commands/test_db.py
import os
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
from django.conf import settings

class Command(BaseCommand):
    help = 'Test database connection and show configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed database configuration',
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("DATABASE CONNECTION TEST")
        self.stdout.write("="*60)
        
        # Show current database configuration
        db_config = settings.DATABASES['default']
        self.stdout.write(f"Engine: {db_config['ENGINE']}")
        self.stdout.write(f"Name: {db_config['NAME']}")
        self.stdout.write(f"Host: {db_config.get('HOST', 'Not specified')}")
        self.stdout.write(f"Port: {db_config.get('PORT', 'Not specified')}")
        self.stdout.write(f"User: {db_config.get('USER', 'Not specified')}")
        
        if options['verbose']:
            self.stdout.write("\nFull DATABASES setting:")
            self.stdout.write(str(settings.DATABASES))
        
        self.stdout.write("\n" + "-"*60)
        self.stdout.write("Testing connection...")
        
        # Test the connection
        db_conn = connections['default']
        try:
            db_conn.cursor()
            self.stdout.write(self.style.SUCCESS('✓ Database connection successful!'))
            
            # Try a simple query
            with db_conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                self.stdout.write(f"PostgreSQL version: {version[0]}")
                
        except OperationalError as e:
            self.stdout.write(self.style.ERROR(f'✗ Database connection failed!'))
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            
            # Provide helpful suggestions
            self.stdout.write("\n" + "="*60)
            self.stdout.write("TROUBLESHOOTING SUGGESTIONS:")
            self.stdout.write("="*60)
            
            if 'does not exist' in str(e):
                self.stdout.write("1. Database doesn't exist. Create it with:")
                self.stdout.write(f"   createdb -U {db_config.get('USER', 'postgres')} {db_config['NAME']}")
            
            elif 'Connection refused' in str(e):
                self.stdout.write("1. Is PostgreSQL running?")
                self.stdout.write("   - Windows: Check Services (PostgreSQL service)")
                self.stdout.write("   - Mac: 'brew services list | grep postgres'")
                self.stdout.write("   - Linux: 'sudo service postgresql status'")
            
            elif 'password authentication failed' in str(e).lower():
                self.stdout.write("1. Wrong password. Check your PostgreSQL user password")
                self.stdout.write("2. You might need to reset the password:")
                self.stdout.write(f"   ALTER USER {db_config.get('USER', 'postgres')} WITH PASSWORD 'newpassword';")
            
            elif 'role' in str(e).lower() and 'does not exist' in str(e).lower():
                self.stdout.write("1. PostgreSQL user doesn't exist. Create it:")
                self.stdout.write(f"   createuser -P {db_config.get('USER', 'trapickuser')}")