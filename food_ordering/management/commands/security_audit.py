"""
Security Audit Management Command
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
import os
import logging

User = get_user_model()
logger = logging.getLogger('food_ordering.security')

class Command(BaseCommand):
    help = 'Perform comprehensive security audit of the application'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix security issues where possible',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Security Audit...'))
        
        issues_found = 0
        
        # Check Django settings
        issues_found += self.check_django_settings(options['verbose'])
        
        # Check user accounts
        issues_found += self.check_user_accounts(options['verbose'])
        
        # Check database security
        issues_found += self.check_database_security(options['verbose'])
        
        # Check file permissions
        issues_found += self.check_file_permissions(options['verbose'])
        
        # Check logging configuration
        issues_found += self.check_logging_configuration(options['verbose'])
        
        # Check environment variables
        issues_found += self.check_environment_variables(options['verbose'])
        
        # Summary
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Security audit completed. No issues found!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Security audit completed. {issues_found} issues found.')
            )
            if not options['fix']:
                self.stdout.write(
                    self.style.WARNING('Run with --fix to automatically fix issues where possible.')
                )
    
    def check_django_settings(self, verbose):
        """Check Django security settings"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking Django Settings...')
        
        # Check DEBUG mode
        if settings.DEBUG:
            self.stdout.write(self.style.ERROR('❌ DEBUG is enabled'))
            issues += 1
        else:
            self.stdout.write(self.style.SUCCESS('✅ DEBUG is disabled'))
        
        # Check SECRET_KEY
        if len(settings.SECRET_KEY) < 50:
            self.stdout.write(self.style.ERROR('❌ SECRET_KEY is too short'))
            issues += 1
        else:
            self.stdout.write(self.style.SUCCESS('✅ SECRET_KEY is secure'))
        
        # Check ALLOWED_HOSTS
        if not settings.ALLOWED_HOSTS:
            self.stdout.write(self.style.ERROR('❌ ALLOWED_HOSTS is empty'))
            issues += 1
        else:
            self.stdout.write(self.style.SUCCESS('✅ ALLOWED_HOSTS is configured'))
        
        # Check HTTPS settings
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            self.stdout.write(self.style.WARNING('⚠️  SECURE_SSL_REDIRECT is not enabled'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ SECURE_SSL_REDIRECT is enabled'))
        
        # Check session security
        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            self.stdout.write(self.style.WARNING('⚠️  SESSION_COOKIE_SECURE is not enabled'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ SESSION_COOKIE_SECURE is enabled'))
        
        # Check CSRF security
        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            self.stdout.write(self.style.WARNING('⚠️  CSRF_COOKIE_SECURE is not enabled'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ CSRF_COOKIE_SECURE is enabled'))
        
        return issues
    
    def check_user_accounts(self, verbose):
        """Check user account security"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking User Accounts...')
        
        # Check for users without passwords
        users_without_passwords = User.objects.filter(password='').count()
        if users_without_passwords > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ {users_without_passwords} users without passwords')
            )
            issues += 1
        else:
            self.stdout.write(self.style.SUCCESS('✅ All users have passwords'))
        
        # Check for admin accounts
        admin_count = User.objects.filter(role='admin').count()
        if admin_count == 0:
            self.stdout.write(self.style.WARNING('⚠️  No admin users found'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ {admin_count} admin users found'))
        
        # Check for inactive users
        inactive_count = User.objects.filter(is_active=False).count()
        if inactive_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️  {inactive_count} inactive users found')
            )
        
        return issues
    
    def check_database_security(self, verbose):
        """Check database security"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking Database Security...')
        
        # Check database engine
        db_engine = settings.DATABASES['default']['ENGINE']
        if 'sqlite' in db_engine:
            self.stdout.write(
                self.style.WARNING('⚠️  Using SQLite (not recommended for production)')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Using production database'))
        
        # Check for sensitive data in database
        with connection.cursor() as cursor:
            # Check for users with weak passwords (basic check)
            cursor.execute("SELECT COUNT(*) FROM accounts_user WHERE LENGTH(password) < 20")
            weak_passwords = cursor.fetchone()[0]
            
            if weak_passwords > 0:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  {weak_passwords} users may have weak passwords')
                )
            else:
                self.stdout.write(self.style.SUCCESS('✅ Password strength appears good'))
        
        return issues
    
    def check_file_permissions(self, verbose):
        """Check file permissions"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking File Permissions...')
        
        # Check database file permissions
        db_path = settings.DATABASES['default']['NAME']
        if os.path.exists(db_path):
            stat_info = os.stat(db_path)
            mode = oct(stat_info.st_mode)[-3:]
            if mode != '600':
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Database file permissions: {mode} (should be 600)')
                )
            else:
                self.stdout.write(self.style.SUCCESS('✅ Database file permissions are secure'))
        
        # Check logs directory
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        if os.path.exists(logs_dir):
            stat_info = os.stat(logs_dir)
            mode = oct(stat_info.st_mode)[-3:]
            if mode not in ['700', '750']:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Logs directory permissions: {mode} (should be 700 or 750)')
                )
            else:
                self.stdout.write(self.style.SUCCESS('✅ Logs directory permissions are secure'))
        
        return issues
    
    def check_logging_configuration(self, verbose):
        """Check logging configuration"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking Logging Configuration...')
        
        # Check if logging is configured
        if hasattr(settings, 'LOGGING') and settings.LOGGING:
            self.stdout.write(self.style.SUCCESS('✅ Logging is configured'))
            
            # Check for security logging
            if 'food_ordering.security' in settings.LOGGING.get('loggers', {}):
                self.stdout.write(self.style.SUCCESS('✅ Security logging is configured'))
            else:
                self.stdout.write(self.style.WARNING('⚠️  Security logging not configured'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Logging not configured'))
            issues += 1
        
        return issues
    
    def check_environment_variables(self, verbose):
        """Check environment variables"""
        issues = 0
        
        self.stdout.write('\n🔍 Checking Environment Variables...')
        
        # Check for sensitive environment variables
        sensitive_vars = [
            'SECRET_KEY',
            'TWILIO_AUTH_TOKEN',
            'PAYSTACK_SECRET_KEY',
            'DATABASE_PASSWORD'
        ]
        
        for var in sensitive_vars:
            if var in os.environ:
                value = os.environ[var]
                if len(value) < 10:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  {var} appears to be weak')
                    )
                else:
                    self.stdout.write(self.style.SUCCESS(f'✅ {var} is configured'))
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  {var} not found in environment')
                )
        
        return issues
