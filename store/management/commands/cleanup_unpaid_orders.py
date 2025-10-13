from django.core.management.base import BaseCommand
from store.models import Order, Payment


class Command(BaseCommand):
    help = 'Delete all unpaid orders and their associated data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find orders that have no successful payment
        unpaid_orders = Order.objects.filter(
            payment__isnull=True
        ) | Order.objects.filter(
            payment__status__in=['pending', 'failed']
        )
        
        unpaid_count = unpaid_orders.count()
        
        if unpaid_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No unpaid orders found.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {unpaid_count} unpaid orders:')
            )
            for order in unpaid_orders:
                self.stdout.write(f'  - Order #{order.id} (User: {order.user.email}, Total: ₦{order.total})')
            return
        
        # Delete unpaid orders and their associated data
        deleted_count = 0
        for order in unpaid_orders:
            # Delete associated payment first (OneToOneField)
            if hasattr(order, 'payment') and order.payment:
                order.payment.delete()
            
            # Delete associated bags and bag items
            for bag in order.bags.all():
                bag.items.all().delete()
                bag.delete()
            
            # Delete the order
            order.delete()
            deleted_count += 1
        
        # Also delete any orphaned payments
        orphaned_payments = Payment.objects.filter(order__isnull=True)
        orphaned_count = orphaned_payments.count()
        
        if orphaned_count > 0:
            orphaned_payments.delete()
            self.stdout.write(
                self.style.SUCCESS(f'Deleted {orphaned_count} orphaned payments.')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} unpaid orders and their associated data.')
        )
