"""
Django management command to create orders safely.
Usage: python manage.py create_order --phone 2348012345678 --items 3
"""
from django.core.management.base import BaseCommand, CommandError
from dashboard.order_utils import create_random_order, create_order_with_items
from store.models import FoodItem


class Command(BaseCommand):
    help = 'Create a new order with proper relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            help='Customer phone number',
        )
        parser.add_argument(
            '--items',
            type=int,
            default=3,
            help='Number of items to include (default: 3)',
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify order integrity after creation',
        )

    def handle(self, *args, **options):
        phone = options['phone']
        num_items = options['items']
        verify = options['verify']

        self.stdout.write('🛒 Creating new order...')

        # Create the order
        result = create_random_order(phone, num_items)

        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Order #{result["order_id"]} created successfully!')
            )
            self.stdout.write(f'   Customer: {result["customer"]}')
            self.stdout.write(f'   Bags: {result["bags_count"]}')
            self.stdout.write(f'   Subtotal: ₦{result["subtotal"]:,.0f}')
            self.stdout.write(f'   Total: ₦{result["total"]:,.0f}')
            self.stdout.write(f'   Payment: {result["payment_reference"]}')
            self.stdout.write(f'   Status: {result["status"]}')

            # Verify if requested
            if verify:
                from dashboard.order_utils import verify_order_integrity
                self.stdout.write('\n🔍 Verifying order integrity...')
                verification = verify_order_integrity(result['order_id'])
                
                if verification['success']:
                    self.stdout.write(
                        self.style.SUCCESS('✅ Order verification passed!')
                    )
                    self.stdout.write(f'   Bags: {verification["bags_count"]}')
                    self.stdout.write(f'   Items: {verification["total_items"]}')
                    self.stdout.write(f'   Payment valid: {verification["payment_valid"]}')
                    self.stdout.write(f'   Totals match: {verification["totals_match"]}')
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Verification failed: {verification["error"]}')
                    )

        else:
            raise CommandError(f'Failed to create order: {result["error"]}')
