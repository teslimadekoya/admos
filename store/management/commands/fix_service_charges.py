"""
Management command to fix service charges for all existing orders.
This ensures all orders have proper service charges applied.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from store.models import Order, Payment


class Command(BaseCommand):
    help = 'Fix service charges for all existing orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--service-charge',
            type=float,
            default=100.0,
            help='Service charge amount to apply (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        service_charge = Decimal(str(options['service_charge']))
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting service charge fix (Service Charge: ₦{service_charge})')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        # Get all orders
        orders = Order.objects.all().order_by('id')
        total_orders = orders.count()
        
        self.stdout.write(f'Found {total_orders} orders to process')
        
        updated_orders = 0
        updated_payments = 0
        errors = []
        
        with transaction.atomic():
            for order in orders:
                try:
                    # Check if order needs service charge update
                    needs_update = False
                    
                    # Check if service charge is missing or zero
                    if not order.service_charge or order.service_charge == 0:
                        order.service_charge = service_charge
                        needs_update = True
                        self.stdout.write(
                            f'Order #{order.id}: Adding service charge ₦{service_charge}'
                        )
                    
                    # Calculate what the total should be
                    expected_total = order.subtotal + order.delivery_fee + order.service_charge
                    current_total = order.total
                    
                    if expected_total != current_total:
                        self.stdout.write(
                            f'Order #{order.id}: Total mismatch - Expected: ₦{expected_total}, Current: ₦{current_total}'
                        )
                    
                    # Update order if needed
                    if needs_update:
                        if not dry_run:
                            order.save()
                        updated_orders += 1
                    
                    # Update associated payment if it exists
                    try:
                        payment = Payment.objects.get(order=order)
                        expected_payment_amount = order.total
                        
                        if payment.amount != expected_payment_amount:
                            self.stdout.write(
                                f'Payment for Order #{order.id}: Updating amount from ₦{payment.amount} to ₦{expected_payment_amount}'
                            )
                            
                            if not dry_run:
                                payment.amount = expected_payment_amount
                                payment.save()
                            updated_payments += 1
                            
                    except Payment.DoesNotExist:
                        self.stdout.write(
                            f'Order #{order.id}: No payment found (this is normal for some orders)'
                        )
                    except Payment.MultipleObjectsReturned:
                        self.stdout.write(
                            self.style.ERROR(f'Order #{order.id}: Multiple payments found - manual review needed')
                        )
                        errors.append(f'Order #{order.id}: Multiple payments found')
                
                except Exception as e:
                    error_msg = f'Order #{order.id}: Error - {str(e)}'
                    self.stdout.write(self.style.ERROR(error_msg))
                    errors.append(error_msg)
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('SERVICE CHARGE FIX COMPLETE'))
        self.stdout.write('='*50)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN RESULTS:'))
        else:
            self.stdout.write(self.style.SUCCESS('ACTUAL RESULTS:'))
        
        self.stdout.write(f'Total orders processed: {total_orders}')
        self.stdout.write(f'Orders updated: {updated_orders}')
        self.stdout.write(f'Payments updated: {updated_payments}')
        
        if errors:
            self.stdout.write(f'Errors encountered: {len(errors)}')
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('No errors encountered!'))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nTo apply these changes, run the command without --dry-run')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nAll service charges have been fixed!')
            )
