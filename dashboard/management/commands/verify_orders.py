"""
Django management command to verify order integrity.
Usage: python manage.py verify_orders --order-id 34
"""
from django.core.management.base import BaseCommand, CommandError
from dashboard.order_utils import verify_order_integrity
from store.models import Order


class Command(BaseCommand):
    help = 'Verify order integrity and relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=int,
            help='Specific order ID to verify',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Verify all orders',
        )

    def handle(self, *args, **options):
        order_id = options['order_id']
        verify_all = options['all']

        if order_id:
            self.verify_single_order(order_id)
        elif verify_all:
            self.verify_all_orders()
        else:
            raise CommandError('Please specify --order-id or --all')

    def verify_single_order(self, order_id):
        self.stdout.write(f'🔍 Verifying Order #{order_id}...')
        
        verification = verify_order_integrity(order_id)
        
        if verification['success']:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Order #{order_id} verification passed!')
            )
            self.stdout.write(f'   Status: {verification["status"]}')
            self.stdout.write(f'   Bags: {verification["bags_count"]}')
            self.stdout.write(f'   Items: {verification["total_items"]}')
            self.stdout.write(f'   Subtotal: ₦{verification["subtotal"]:,.0f}')
            self.stdout.write(f'   Payment valid: {verification["payment_valid"]}')
            self.stdout.write(f'   Totals match: {verification["totals_match"]}')
            
            if verification['items_details']:
                self.stdout.write(f'   Items:')
                for item in verification['items_details']:
                    self.stdout.write(f'     Bag {item["bag_id"]}: {item["item_name"]} x{item["quantity"]}')
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Order #{order_id} verification failed: {verification["error"]}')
            )

    def verify_all_orders(self):
        self.stdout.write('🔍 Verifying all orders...')
        
        orders = Order.objects.all().order_by('id')
        total_orders = orders.count()
        passed = 0
        failed = 0
        
        for order in orders:
            verification = verify_order_integrity(order.id)
            
            if verification['success']:
                if verification['bags_count'] > 0 and verification['payment_valid'] and verification['totals_match']:
                    passed += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Order #{order.id}: OK')
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Order #{order.id}: Issues found')
                    )
                    if verification['bags_count'] == 0:
                        self.stdout.write('     - No bags linked')
                    if not verification['payment_valid']:
                        self.stdout.write('     - Payment missing/invalid')
                    if not verification['totals_match']:
                        self.stdout.write('     - Totals mismatch')
            else:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Order #{order.id}: {verification["error"]}')
                )
        
        self.stdout.write(f'\n📊 Verification Summary:')
        self.stdout.write(f'   Total orders: {total_orders}')
        self.stdout.write(f'   Passed: {passed}')
        self.stdout.write(f'   Failed: {failed}')
        
        if failed == 0:
            self.stdout.write(
                self.style.SUCCESS('🎉 All orders are healthy!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  {failed} orders need attention')
            )
