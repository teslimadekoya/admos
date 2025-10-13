"""
Security Monitoring Script for Food Ordering System
Real-time security monitoring and alerting
"""

import os
import sys
import django
import time
import logging
from datetime import datetime, timedelta
from django.core.management import execute_from_command_line

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_ordering.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.conf import settings
import psutil

User = get_user_model()
logger = logging.getLogger('food_ordering.security')

class SecurityMonitor:
    """
    Real-time security monitoring system
    """
    
    def __init__(self):
        self.alert_thresholds = {
            'failed_logins': 5,  # 5 failed logins per minute
            'api_requests': 1000,  # 1000 API requests per minute
            'memory_usage': 80,  # 80% memory usage
            'cpu_usage': 90,  # 90% CPU usage
            'disk_usage': 90,  # 90% disk usage
        }
        
        self.monitoring_active = True
    
    def start_monitoring(self):
        """Start the security monitoring loop"""
        logger.info("Security monitoring started")
        
        while self.monitoring_active:
            try:
                # Check system resources
                self.check_system_resources()
                
                # Check database security
                self.check_database_security()
                
                # Check user activity
                self.check_user_activity()
                
                # Check API activity
                self.check_api_activity()
                
                # Check for suspicious patterns
                self.check_suspicious_patterns()
                
                # Sleep for 60 seconds
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Security monitoring stopped by user")
                self.monitoring_active = False
            except Exception as e:
                logger.error(f"Error in security monitoring: {e}")
                time.sleep(60)
    
    def check_system_resources(self):
        """Check system resource usage"""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > self.alert_thresholds['memory_usage']:
                self.send_alert(
                    'HIGH_MEMORY_USAGE',
                    f"Memory usage is {memory.percent}% (threshold: {self.alert_thresholds['memory_usage']}%)"
                )
            
            # CPU usage
            cpu = psutil.cpu_percent(interval=1)
            if cpu > self.alert_thresholds['cpu_usage']:
                self.send_alert(
                    'HIGH_CPU_USAGE',
                    f"CPU usage is {cpu}% (threshold: {self.alert_thresholds['cpu_usage']}%)"
                )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > self.alert_thresholds['disk_usage']:
                self.send_alert(
                    'HIGH_DISK_USAGE',
                    f"Disk usage is {disk_percent:.1f}% (threshold: {self.alert_thresholds['disk_usage']}%)"
                )
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
    
    def check_database_security(self):
        """Check database security metrics"""
        try:
            with connection.cursor() as cursor:
                # Check for failed login attempts
                cursor.execute("""
                    SELECT COUNT(*) FROM django_session 
                    WHERE expire_date < %s
                """, [datetime.now()])
                expired_sessions = cursor.fetchone()[0]
                
                if expired_sessions > 1000:
                    self.send_alert(
                        'HIGH_EXPIRED_SESSIONS',
                        f"High number of expired sessions: {expired_sessions}"
                    )
                
                # Check for suspicious user activity
                cursor.execute("""
                    SELECT COUNT(*) FROM accounts_user 
                    WHERE last_login < %s AND is_active = 1
                """, [datetime.now() - timedelta(days=30)])
                inactive_users = cursor.fetchone()[0]
                
                if inactive_users > 100:
                    self.send_alert(
                        'MANY_INACTIVE_USERS',
                        f"Many inactive users: {inactive_users}"
                    )
        
        except Exception as e:
            logger.error(f"Error checking database security: {e}")
    
    def check_user_activity(self):
        """Check user activity patterns"""
        try:
            # Check for multiple failed login attempts
            failed_logins = cache.get('failed_logins', {})
            current_time = time.time()
            
            # Clean old entries
            failed_logins = {
                ip: attempts for ip, attempts in failed_logins.items()
                if current_time - attempts['last_attempt'] < 300  # 5 minutes
            }
            
            # Check for suspicious activity
            for ip, data in failed_logins.items():
                if data['count'] > self.alert_thresholds['failed_logins']:
                    self.send_alert(
                        'BRUTE_FORCE_ATTEMPT',
                        f"Brute force attempt detected from IP: {ip} ({data['count']} attempts)"
                    )
        
        except Exception as e:
            logger.error(f"Error checking user activity: {e}")
    
    def check_api_activity(self):
        """Check API activity patterns"""
        try:
            # Check API request rates
            api_requests = cache.get('api_requests', {})
            current_time = time.time()
            
            # Clean old entries
            api_requests = {
                ip: requests for ip, requests in api_requests.items()
                if current_time - requests['last_request'] < 60  # 1 minute
            }
            
            # Check for suspicious API activity
            for ip, data in api_requests.items():
                if data['count'] > self.alert_thresholds['api_requests']:
                    self.send_alert(
                        'API_ABUSE',
                        f"High API request rate from IP: {ip} ({data['count']} requests/minute)"
                    )
        
        except Exception as e:
            logger.error(f"Error checking API activity: {e}")
    
    def check_suspicious_patterns(self):
        """Check for suspicious patterns in logs"""
        try:
            # Check for SQL injection attempts
            sql_attempts = cache.get('sql_injection_attempts', 0)
            if sql_attempts > 10:
                self.send_alert(
                    'SQL_INJECTION_ATTEMPTS',
                    f"Multiple SQL injection attempts detected: {sql_attempts}"
                )
                cache.set('sql_injection_attempts', 0, 3600)  # Reset counter
            
            # Check for path traversal attempts
            path_traversal_attempts = cache.get('path_traversal_attempts', 0)
            if path_traversal_attempts > 5:
                self.send_alert(
                    'PATH_TRAVERSAL_ATTEMPTS',
                    f"Multiple path traversal attempts detected: {path_traversal_attempts}"
                )
                cache.set('path_traversal_attempts', 0, 3600)  # Reset counter
        
        except Exception as e:
            logger.error(f"Error checking suspicious patterns: {e}")
    
    def send_alert(self, alert_type, message):
        """Send security alert"""
        timestamp = datetime.now().isoformat()
        alert_message = f"[{timestamp}] SECURITY ALERT - {alert_type}: {message}"
        
        # Log the alert
        logger.warning(alert_message)
        
        # Store in cache for dashboard
        alerts = cache.get('security_alerts', [])
        alerts.append({
            'type': alert_type,
            'message': message,
            'timestamp': timestamp
        })
        
        # Keep only last 100 alerts
        if len(alerts) > 100:
            alerts = alerts[-100:]
        
        cache.set('security_alerts', alerts, 86400)  # 24 hours
        
        # In production, you would send email/SMS alerts here
        print(f"🚨 SECURITY ALERT: {alert_message}")
    
    def get_security_status(self):
        """Get current security status"""
        status = {
            'monitoring_active': self.monitoring_active,
            'alerts': cache.get('security_alerts', []),
            'system_health': {
                'memory_usage': psutil.virtual_memory().percent,
                'cpu_usage': psutil.cpu_percent(),
                'disk_usage': psutil.disk_usage('/').percent,
            },
            'security_metrics': {
                'failed_logins': len(cache.get('failed_logins', {})),
                'api_requests': len(cache.get('api_requests', {})),
                'blocked_ips': len(cache.get('blocked_ips', {})),
            }
        }
        
        return status

def main():
    """Main function to run security monitoring"""
    monitor = SecurityMonitor()
    
    try:
        monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\nSecurity monitoring stopped.")
    except Exception as e:
        print(f"Error starting security monitoring: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
