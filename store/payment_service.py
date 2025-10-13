"""
Bulletproof Payment Service
Ensures payment amounts always match order totals with multiple layers of validation.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Payment, Order
import uuid


class PaymentService:
    """
    Service class that ensures payment amounts always match order totals.
    This makes revenue discrepancies impossible.
    """
    
    @staticmethod
    @transaction.atomic
    def create_payment(order, user, payment_method, payment_type=None, **kwargs):
        """
        Create a payment with guaranteed amount consistency.
        
        Args:
            order: Order instance
            user: User instance
            payment_method: Payment method (cash, card, transfer, paystack)
            payment_type: Payment type for Paystack payments
            **kwargs: Additional payment fields
            
        Returns:
            Payment instance
            
        Raises:
            ValidationError: If order total cannot be calculated or is invalid
        """
        # Step 1: Validate order exists and is valid
        if not order or not isinstance(order, Order):
            raise ValidationError("Valid order is required")
        
        # Step 2: Recalculate order total to ensure accuracy
        calculated_total = PaymentService._calculate_order_total(order)
        
        # Step 3: Verify calculated total matches stored total
        if abs(calculated_total - order.total) > Decimal('0.01'):  # Allow 1 kobo tolerance
            raise ValidationError(
                f"Order total mismatch: calculated {calculated_total} vs stored {order.total}. "
                f"Order may be corrupted."
            )
        
        # Step 4: Check if payment already exists
        if hasattr(order, 'payment'):
            raise ValidationError("Payment already exists for this order")
        
        # Step 5: Generate unique reference
        reference = PaymentService._generate_reference()
        
        # Step 6: Create payment with order total as amount
        payment_data = {
            'order': order,
            'user': user,
            'amount': order.total,  # ALWAYS use order total
            'payment_method': payment_method,
            'payment_type': payment_type,
            'reference': reference,
            'status': 'pending',
            **kwargs
        }
        
        # Step 7: Create and validate payment
        payment = Payment(**payment_data)
        payment.full_clean()  # This will trigger our custom validation
        payment.save()
        
        return payment
    
    @staticmethod
    def _calculate_order_total(order):
        """
        Calculate order total from scratch to verify accuracy.
        This is the source of truth for order totals.
        """
        total = Decimal('0.00')
        
        # Add bag totals
        for bag in order.bags.all():
            total += bag.total
        
        # Add delivery fee
        if order.delivery_fee:
            total += Decimal(str(order.delivery_fee))
        
        # Add service charge (all orders are now online orders)
        if order.service_charge:
            total += Decimal(str(order.service_charge))
        
        return total
    
    @staticmethod
    def _generate_reference():
        """Generate unique payment reference."""
        return f"PAY_{uuid.uuid4().hex[:12].upper()}"
    
    @staticmethod
    @transaction.atomic
    def update_payment_status(payment, status, **kwargs):
        """
        Update payment status while maintaining amount consistency.
        """
        if not isinstance(payment, Payment):
            raise ValidationError("Valid payment instance required")
        
        # Verify amount still matches order total
        if payment.amount != payment.order.total:
            raise ValidationError(
                f"Payment amount ({payment.amount}) does not match order total ({payment.order.total}). "
                f"This indicates data corruption."
            )
        
        # Update status and other fields
        for field, value in kwargs.items():
            if hasattr(payment, field):
                setattr(payment, field, value)
        
        payment.status = status
        payment.save()
        
        return payment
    
    @staticmethod
    def validate_payment_consistency():
        """
        Validate all payments in the system for consistency.
        Returns list of inconsistent payments.
        """
        inconsistent_payments = []
        
        for payment in Payment.objects.select_related('order').all():
            if payment.amount != payment.order.total:
                inconsistent_payments.append({
                    'payment_id': payment.id,
                    'payment_amount': payment.amount,
                    'order_id': payment.order.id,
                    'order_total': payment.order.total,
                    'difference': payment.amount - payment.order.total
                })
        
        return inconsistent_payments
    
    @staticmethod
    @transaction.atomic
    def fix_inconsistent_payments():
        """
        Fix all inconsistent payments by setting amount to order total.
        Returns count of fixed payments.
        """
        inconsistent_payments = PaymentService.validate_payment_consistency()
        
        for payment_data in inconsistent_payments:
            payment = Payment.objects.get(id=payment_data['payment_id'])
            payment.amount = payment.order.total
            payment.save()
        
        return len(inconsistent_payments)


class OrderTotalValidator:
    """
    Validator to ensure order totals are always accurate.
    """
    
    @staticmethod
    def validate_order_total(order):
        """
        Validate that an order's total is correct.
        """
        calculated_total = PaymentService._calculate_order_total(order)
        
        if abs(calculated_total - order.total) > Decimal('0.01'):
            raise ValidationError(
                f"Order total is incorrect. Calculated: {calculated_total}, Stored: {order.total}"
            )
        
        return True
    
    @staticmethod
    def recalculate_and_fix_order_total(order):
        """
        Recalculate and fix order total if incorrect.
        """
        calculated_total = PaymentService._calculate_order_total(order)
        
        if abs(calculated_total - order.total) > Decimal('0.01'):
            order.total = calculated_total
            order.save()
            return True
        
        return False
