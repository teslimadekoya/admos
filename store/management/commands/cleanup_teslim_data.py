from django.core.management.base import BaseCommand
from django.utils import timezone
from store.models import Payment, Order, Bag, BagItem
from accounts.models import User
from datetime import timedelta

class Command(BaseCommand):
    help = 'Delete all of Teslim\'s orders and today\'s payments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        # Find Teslim's user account
        try:
            teslim_user = User.objects.get(phone_number='08027281620')
            self.stdout.write(f"Found user: {teslim_user.first_name} {teslim_user.last_name} ({teslim_user.phone_number})")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Teslim user not found'))
            return
        
        # Get all of Teslim's orders
        teslim_orders = Order.objects.filter(user=teslim_user)
        self.stdout.write(f"Found {teslim_orders.count()} orders for Teslim")
        
        # Get all of today's payments
        today_payments = Payment.objects.filter(created_at__date=today)
        self.stdout.write(f"Found {today_payments.count()} payments from today")
        
        if dry_run:
            self.stdout.write("\n=== DRY RUN - What would be deleted ===")
            
            # Show Teslim's orders
            if teslim_orders.exists():
                self.stdout.write(f"\nTeslim's Orders ({teslim_orders.count()}):")
                for order in teslim_orders:
                    self.stdout.write(f"  - Order #{order.id}: ₦{order.total} ({order.status})")
            
            # Show today's payments
            if today_payments.exists():
                self.stdout.write(f"\nToday's Payments ({today_payments.count()}):")
                for payment in today_payments:
                    order_info = f"Order #{payment.order.id}" if payment.order else "No Order"
                    self.stdout.write(f"  - Payment {payment.reference}: ₦{payment.amount} ({order_info})")
        else:
            # Actually delete the data
            deleted_orders_count = 0
            deleted_payments_count = 0
            
            # Delete today's payments first (to avoid PROTECT constraint)
            if today_payments.exists():
                self.stdout.write(f"\nDeleting {today_payments.count()} payments from today...")
                for payment in today_payments:
                    order_info = f"Order #{payment.order.id}" if payment.order else "No Order"
                    self.stdout.write(f"  Deleting Payment {payment.reference} (₦{payment.amount}) - {order_info}")
                    payment.delete()
                    deleted_payments_count += 1
            
            # Delete Teslim's orders (this will cascade to bags and bag items)
            if teslim_orders.exists():
                self.stdout.write(f"\nDeleting {teslim_orders.count()} orders for Teslim...")
                for order in teslim_orders:
                    self.stdout.write(f"  Deleting Order #{order.id} (₦{order.total})")
                    order.delete()
                    deleted_orders_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Cleanup completed!"))
            self.stdout.write(f"   - Deleted {deleted_orders_count} orders")
            self.stdout.write(f"   - Deleted {deleted_payments_count} payments")
        
        # Show final counts
        remaining_orders = Order.objects.filter(user=teslim_user).count()
        remaining_payments = Payment.objects.filter(created_at__date=today).count()
        
        self.stdout.write(f"\nFinal counts:")
        self.stdout.write(f"   - Teslim's remaining orders: {remaining_orders}")
        self.stdout.write(f"   - Today's remaining payments: {remaining_payments}")
