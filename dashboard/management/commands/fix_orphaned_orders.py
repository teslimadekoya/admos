"""
Management command to fix orphaned orders (orders without linked bags).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from store.models import Order, Bag
from store.order_utils import fix_orphaned_order, validate_order_integrity


class Command(BaseCommand):
    help = 'Fix orphaned orders by linking them to appropriate bags'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--order-id',
            type=int,
            help='Fix a specific order by ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        order_id = options.get('order_id')
        
        if order_id:
            # Fix specific order
            try:
                order = Order.objects.get(id=order_id)
                self.fix_single_order(order, dry_run)
            except Order.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Order #{order_id} not found')
                )
        else:
            # Fix all orphaned orders
            self.fix_all_orphaned_orders(dry_run)

    def fix_single_order(self, order, dry_run):
        """Fix a single orphaned order."""
        self.stdout.write(f'Checking Order #{order.id}...')
        
        try:
            validate_order_integrity(order)
            self.stdout.write(
                self.style.SUCCESS(f'Order #{order.id} is already valid')
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Order #{order.id} has issues: {e}')
            )
            
            if not dry_run:
                if fix_orphaned_order(order):
                    self.stdout.write(
                        self.style.SUCCESS(f'Fixed Order #{order.id}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Could not fix Order #{order.id}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would attempt to fix Order #{order.id}')
                )

    def fix_all_orphaned_orders(self, dry_run):
        """Fix all orphaned orders in the system."""
        self.stdout.write('Scanning for orphaned orders...')
        
        # Find orders without bags
        orphaned_orders = Order.objects.filter(bags__isnull=True).distinct()
        
        if not orphaned_orders.exists():
            self.stdout.write(
                self.style.SUCCESS('No orphaned orders found!')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {orphaned_orders.count()} orphaned orders')
        )
        
        fixed_count = 0
        failed_count = 0
        
        for order in orphaned_orders:
            self.stdout.write(f'Processing Order #{order.id}...')
            
            if not dry_run:
                if fix_orphaned_order(order):
                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Fixed Order #{order.id}')
                    )
                else:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'Could not fix Order #{order.id}')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would attempt to fix Order #{order.id}')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would fix {orphaned_orders.count()} orders')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Fixed {fixed_count} orders, {failed_count} failed')
            )
        
        # Also check for orders with bags but no items
        self.check_orders_with_empty_bags(dry_run)

    def check_orders_with_empty_bags(self, dry_run):
        """Check for orders that have bags but the bags have no items."""
        self.stdout.write('Checking for orders with empty bags...')
        
        orders_with_empty_bags = []
        for order in Order.objects.all():
            if order.bags.exists():
                for bag in order.bags.all():
                    if not bag.items.exists():
                        orders_with_empty_bags.append((order, bag))
        
        if orders_with_empty_bags:
            self.stdout.write(
                self.style.WARNING(f'Found {len(orders_with_empty_bags)} orders with empty bags')
            )
            
            for order, bag in orders_with_empty_bags:
                self.stdout.write(
                    self.style.WARNING(f'Order #{order.id} has empty bag "{bag.name}"')
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('No orders with empty bags found!')
            )
