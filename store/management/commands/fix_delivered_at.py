"""
Management command to fix delivered_at field for existing delivered orders.
This uses created_at + estimated delivery time as a better approximation.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from store.models import Order


class Command(BaseCommand):
    help = 'Fix delivered_at field for existing delivered orders using better logic'

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
            self.style.SUCCESS('🔧 Fixing delivered_at timestamps...')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all delivered orders
        delivered_orders = Order.objects.filter(
            status='Delivered'
        ).order_by('created_at')
        
        self.stdout.write(f'Found {delivered_orders.count()} delivered orders to fix')
        
        updated_count = 0
        errors = []
        
        for order in delivered_orders:
            try:
                # Use created_at + estimated delivery time (30-60 minutes)
                # This is a much better approximation than updated_at
                estimated_delivery_time = order.created_at + timedelta(minutes=45)
                
                if verbose:
                    self.stdout.write(
                        f'Order #{order.id}: Setting delivered_at to {estimated_delivery_time} '
                        f'(created: {order.created_at})'
                    )
                
                if not dry_run:
                    with transaction.atomic():
                        order.delivered_at = estimated_delivery_time
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
        self.stdout.write(self.style.SUCCESS('DELIVERED_AT FIX COMPLETE'))
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
                self.style.SUCCESS('\n🎉 All delivered_at timestamps have been fixed!')
            )
