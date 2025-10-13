from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from store.models import Order, Bag
from django.db import transaction


class Command(BaseCommand):
    help = 'Identify and fix incomplete orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=int,
            help='Fix a specific order by ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes'
        )
        parser.add_argument(
            '--delete-incomplete',
            action='store_true',
            help='Delete incomplete orders that cannot be fixed'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_incomplete = options['delete_incomplete']
        order_id = options.get('order_id')

        if order_id:
            self.fix_single_order(order_id, dry_run, delete_incomplete)
        else:
            self.fix_all_incomplete_orders(dry_run, delete_incomplete)

    def fix_single_order(self, order_id, dry_run, delete_incomplete):
        """Fix a specific order."""
        try:
            order = Order.objects.get(id=order_id)
            self.stdout.write(f'🔍 Analyzing Order #{order_id}...')
            
            issues = self.analyze_order_issues(order)
            
            if not issues:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Order #{order_id} is complete and valid.')
                )
                return
            
            self.stdout.write(
                self.style.WARNING(f'⚠️  Order #{order_id} has {len(issues)} issue(s):')
            )
            for issue in issues:
                self.stdout.write(f'   - {issue}')
            
            if dry_run:
                self.stdout.write('🔍 DRY RUN: Would attempt to fix these issues.')
                return
            
            if self.can_fix_order(order, issues):
                self.attempt_fix_order(order, issues)
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Order #{order_id} cannot be fixed automatically.')
                )
                if delete_incomplete:
                    self.delete_incomplete_order(order)
                    
        except Order.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Order #{order_id} not found.')
            )

    def fix_all_incomplete_orders(self, dry_run, delete_incomplete):
        """Fix all incomplete orders."""
        self.stdout.write('🔍 Scanning all orders for completeness issues...')
        
        orders = Order.objects.all().order_by('id')
        total_orders = orders.count()
        incomplete_orders = []
        fixed_orders = 0
        deleted_orders = 0
        
        for order in orders:
            issues = self.analyze_order_issues(order)
            if issues:
                incomplete_orders.append((order, issues))
        
        if not incomplete_orders:
            self.stdout.write(
                self.style.SUCCESS('🎉 All orders are complete and valid!')
            )
            return
        
        self.stdout.write(f'📊 Found {len(incomplete_orders)} incomplete orders out of {total_orders} total.')
        
        for order, issues in incomplete_orders:
            self.stdout.write(f'\n🔍 Order #{order.id}:')
            for issue in issues:
                self.stdout.write(f'   - {issue}')
            
            if dry_run:
                self.stdout.write('   🔍 DRY RUN: Would attempt to fix.')
                continue
            
            if self.can_fix_order(order, issues):
                if self.attempt_fix_order(order, issues):
                    fixed_orders += 1
            else:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Cannot be fixed automatically.')
                )
                if delete_incomplete:
                    self.delete_incomplete_order(order)
                    deleted_orders += 1
        
        # Summary
        self.stdout.write(f'\n📊 Summary:')
        self.stdout.write(f'   Total orders: {total_orders}')
        self.stdout.write(f'   Incomplete orders: {len(incomplete_orders)}')
        if not dry_run:
            self.stdout.write(f'   Fixed: {fixed_orders}')
            if delete_incomplete:
                self.stdout.write(f'   Deleted: {deleted_orders}')

    def analyze_order_issues(self, order):
        """Analyze an order and return list of issues."""
        issues = []
        
        # Check if order has bags
        if not order.bags.exists():
            issues.append("No bags linked to order")
        
        # Check if all bags have items
        for bag in order.bags.all():
            if not bag.items.exists():
                issues.append(f"Bag '{bag.name}' is empty")
        
        # Check delivery address
        if not order.delivery_address or len(order.delivery_address.strip()) < 10:
            issues.append("Invalid or missing delivery address")
        
        # Check contact phone
        if not order.contact_phone or len(order.contact_phone.strip()) < 10:
            issues.append("Invalid or missing contact phone")
        
        # Check fees
        if order.delivery_fee < 0 or order.delivery_fee > 10000:
            issues.append("Invalid delivery fee")
        
        if order.service_charge < 0 or order.service_charge > 5000:
            issues.append("Invalid service charge")
        
        # Check total
        if order.total <= 0:
            issues.append("Invalid order total")
        
        return issues

    def can_fix_order(self, order, issues):
        """Check if an order can be automatically fixed."""
        # Can fix if only missing delivery address or contact phone
        fixable_issues = [
            "Invalid or missing delivery address",
            "Invalid or missing contact phone"
        ]
        
        return all(issue in fixable_issues for issue in issues)

    def attempt_fix_order(self, order, issues):
        """Attempt to fix an order."""
        try:
            with transaction.atomic():
                fixed = False
                
                # Fix delivery address
                if "Invalid or missing delivery address" in issues:
                    order.delivery_address = f"Default Address for Order #{order.id}"
                    fixed = True
                
                # Fix contact phone
                if "Invalid or missing contact phone" in issues:
                    order.contact_phone = order.user.phone_number or "0000000000"
                    fixed = True
                
                if fixed:
                    order.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'   ✅ Fixed Order #{order.id}')
                    )
                    return True
                else:
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ Could not fix Order #{order.id}')
                    )
                    return False
                    
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Error fixing Order #{order.id}: {str(e)}')
            )
            return False

    def delete_incomplete_order(self, order):
        """Delete an incomplete order that cannot be fixed."""
        try:
            order_id = order.id
            order.delete()
            self.stdout.write(
                self.style.WARNING(f'   🗑️  Deleted incomplete Order #{order_id}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'   ❌ Error deleting Order #{order.id}: {str(e)}')
            )
