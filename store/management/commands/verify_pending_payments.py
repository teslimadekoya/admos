"""
Management command to verify pending payments with Paystack.
This can be used to manually verify payments that are stuck in pending status.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from store.models import Payment
import requests


class Command(BaseCommand):
    help = 'Verify pending payments with Paystack'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reference',
            type=str,
            help='Verify a specific payment by reference',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Verify all pending payments',
        )

    def handle(self, *args, **options):
        if options['reference']:
            self.verify_single_payment(options['reference'])
        elif options['all']:
            self.verify_all_pending_payments()
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --reference or --all')
            )

    def verify_single_payment(self, reference):
        """Verify a single payment by reference."""
        try:
            payment = Payment.objects.get(reference=reference)
            self.verify_payment_with_paystack(payment)
        except Payment.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Payment with reference {reference} not found')
            )

    def verify_all_pending_payments(self):
        """Verify all pending payments."""
        pending_payments = Payment.objects.filter(status='pending')
        
        if not pending_payments.exists():
            self.stdout.write(
                self.style.SUCCESS('No pending payments found')
            )
            return
        
        self.stdout.write(
            f'Found {pending_payments.count()} pending payments to verify...'
        )
        
        for payment in pending_payments:
            self.verify_payment_with_paystack(payment)

    def verify_payment_with_paystack(self, payment):
        """Verify a payment with Paystack API."""
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        url = f"https://api.paystack.co/transaction/verify/{payment.reference}"
        
        try:
            response = requests.get(url, headers=headers)
            res_data = response.json()
            
            if res_data.get("status") is True:
                data = res_data.get("data", {})
                status = data.get("status")
                
                if status == "success":
                    # Payment was successful
                    payment.status = "success"
                    
                    # Update payment type if available
                    if "authorization" in data:
                        auth_data = data["authorization"]
                        channel = auth_data.get("channel", "")
                        
                        if channel in ["card"]:
                            payment.payment_type = "card"
                        elif channel in ["bank_transfer", "bank"]:
                            payment.payment_type = "bank_transfer"
                        elif channel in ["ussd"]:
                            payment.payment_type = "ussd"
                        elif channel in ["mobile_money", "mobilemoney"]:
                            payment.payment_type = "mobile_money"
                        elif channel in ["qr"]:
                            payment.payment_type = "qr"
                    
                    payment.save()
                    
                    # Mark order as Pending (payment confirmed)
                    payment.order.status = "Pending"
                    payment.order.save()
                    
                    # Reduce quantities for all items in the order
                    self.reduce_order_quantities(payment.order)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Payment {payment.reference} verified successfully for order #{payment.order.id}'
                        )
                    )
                    
                elif status == "failed":
                    # Payment failed
                    payment.status = "failed"
                    payment.save()
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f'❌ Payment {payment.reference} failed for order #{payment.order.id}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ Payment {payment.reference} status: {status}'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Failed to verify payment {payment.reference}: {res_data.get("message", "Unknown error")}'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Error verifying payment {payment.reference}: {str(e)}'
                )
            )

    def reduce_order_quantities(self, order):
        """Reduce portions for all food items in the order after successful payment."""
        from django.db import transaction
        
        with transaction.atomic():
            for bag in order.bags.all():
                for bag_item in bag.items.all():
                    if bag_item.food_item:  # Only reduce if food_item still exists
                        try:
                            bag_item.food_item.reduce_portions(bag_item.portions)
                        except ValueError as e:
                            # Log the error but don't fail the payment
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Warning: Could not reduce portions for {bag_item.food_item.name}: {e}'
                                )
                            )
