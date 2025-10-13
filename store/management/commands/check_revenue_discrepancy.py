from django.core.management.base import BaseCommand
from django.utils import timezone
from store.models import Payment, Order
from datetime import timedelta

class Command(BaseCommand):
    help = 'Check revenue discrepancy between payments and orders'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Get today's successful payments
        today_payments = Payment.objects.filter(
            status='success',
            created_at__date=today
        )
        
        # Get today's orders with successful payments
        today_orders = Order.objects.filter(
            payment__status='success',
            payment__created_at__date=today
        )
        
        # Calculate totals
        payments_total = sum(payment.amount for payment in today_payments)
        orders_total = sum(order.total for order in today_orders)
        
        self.stdout.write(f"Today's date: {today}")
        self.stdout.write(f"Number of successful payments: {today_payments.count()}")
        self.stdout.write(f"Number of orders with successful payments: {today_orders.count()}")
        self.stdout.write(f"Payments total: ₦{payments_total:,.2f}")
        self.stdout.write(f"Orders total: ₦{orders_total:,.2f}")
        self.stdout.write(f"Difference: ₦{abs(payments_total - orders_total):,.2f}")
        
        # Check for payments without orders
        payments_without_orders = today_payments.filter(order__isnull=True)
        self.stdout.write(f"Payments without orders: {payments_without_orders.count()}")
        
        if payments_without_orders.exists():
            self.stdout.write("Payments without orders:")
            for payment in payments_without_orders:
                self.stdout.write(f"  - Payment {payment.reference}: ₦{payment.amount}")
        
        # Check for orders without payments
        orders_without_payments = today_orders.filter(payment__isnull=True)
        self.stdout.write(f"Orders without payments: {orders_without_payments.count()}")
        
        # Check for amount mismatches
        mismatched_payments = []
        for payment in today_payments.filter(order__isnull=False):
            if payment.amount != payment.order.total:
                mismatched_payments.append(payment)
        
        self.stdout.write(f"Payments with amount mismatches: {len(mismatched_payments)}")
        for payment in mismatched_payments:
            self.stdout.write(f"  - Payment {payment.reference}: ₦{payment.amount} vs Order {payment.order.id}: ₦{payment.order.total}")
