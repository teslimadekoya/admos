"""
Management command to validate and fix payment consistency.
"""

from django.core.management.base import BaseCommand
from store.payment_service import PaymentService, OrderTotalValidator
from store.models import Order


class Command(BaseCommand):
    help = 'Validate and fix payment consistency issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix inconsistent payments automatically',
        )
        parser.add_argument(
            '--validate-orders',
            action='store_true',
            help='Validate order totals as well',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 Starting payment consistency validation...')
        )

        # Validate payments
        inconsistent_payments = PaymentService.validate_payment_consistency()
        
        if inconsistent_payments:
            self.stdout.write(
                self.style.WARNING(f'❌ Found {len(inconsistent_payments)} inconsistent payments:')
            )
            
            for payment_data in inconsistent_payments:
                self.stdout.write(
                    f'  Payment #{payment_data["payment_id"]}: '
                    f'Amount ₦{payment_data["payment_amount"]:,.2f} vs '
                    f'Order #{payment_data["order_id"]} Total ₦{payment_data["order_total"]:,.2f} '
                    f'(Diff: ₦{payment_data["difference"]:,.2f})'
                )
            
            if options['fix']:
                self.stdout.write(
                    self.style.SUCCESS('🔧 Fixing inconsistent payments...')
                )
                fixed_count = PaymentService.fix_inconsistent_payments()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Fixed {fixed_count} payments')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('Use --fix to automatically fix these issues')
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ All payments are consistent!')
            )

        # Validate order totals if requested
        if options['validate_orders']:
            self.stdout.write(
                self.style.SUCCESS('🔍 Validating order totals...')
            )
            
            inconsistent_orders = []
            for order in Order.objects.all():
                try:
                    OrderTotalValidator.validate_order_total(order)
                except Exception as e:
                    inconsistent_orders.append({
                        'order_id': order.id,
                        'error': str(e)
                    })
            
            if inconsistent_orders:
                self.stdout.write(
                    self.style.WARNING(f'❌ Found {len(inconsistent_orders)} orders with incorrect totals:')
                )
                
                for order_data in inconsistent_orders:
                    self.stdout.write(
                        f'  Order #{order_data["order_id"]}: {order_data["error"]}'
                    )
                
                if options['fix']:
                    self.stdout.write(
                        self.style.SUCCESS('🔧 Fixing order totals...')
                    )
                    
                    fixed_orders = 0
                    for order in Order.objects.all():
                        if OrderTotalValidator.recalculate_and_fix_order_total(order):
                            fixed_orders += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Fixed {fixed_orders} order totals')
                    )
            else:
                self.stdout.write(
                    self.style.SUCCESS('✅ All order totals are correct!')
                )

        self.stdout.write(
            self.style.SUCCESS('🎯 Payment consistency validation complete!')
        )
