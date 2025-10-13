"""
Management command to backfill delivered_at field for existing delivered orders.
This ensures accurate delivery tracking for historical data.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from store.models import Order


class Command(BaseCommand):
    help = 'Backfill delivered_at field for existing delivered orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS('🚚 Starting delivered_at backfill...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all delivered orders without delivered_at
        delivered_orders = Order.objects.filter(
            status='Delivered',
            delivered_at__isnull=True
        ).order_by('updated_at')
        
        self.stdout.write(f'Found {delivered_orders.count()} delivered orders without delivered_at')
        
        updated_count = 0
        errors = []
        
        for order in delivered_orders:
            try:
                # Use updated_at as a proxy for delivery time
                # This is the best approximation we have for historical data
                delivery_time = order.updated_at
                
                if verbose:
                    self.stdout.write(
                        f'Order #{order.id}: Setting delivered_at to {delivery_time}'
                    )
                
                if not dry_run:
                    with transaction.atomic():
                        order.delivered_at = delivery_time
                        order.save(update_fields=['delivered_at'])
                
                updated_count += 1
                
            except Exception as e:
                error_msg = f'Order #{order.id}: {str(e)}'
                errors.append(error_msg)
                self.stdout.write(
                    self.style.ERROR(f'❌ {error_msg}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('DELIVERED_AT BACKFILL COMPLETE'))
        self.stdout.write('='*50)
        
        if dry_run:
            self.stdout.write(f'Would update: {updated_count} orders')
        else:
            self.stdout.write(f'Updated: {updated_count} orders')
        
        if errors:
            self.stdout.write(f'Errors: {len(errors)}')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ No errors encountered!'))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nTo apply these changes, run without --dry-run')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n🎉 All delivered orders now have delivered_at timestamps!')
            )
