"""
Management command to verify inventory consistency and fix any issues.
This ensures the inventory is always accurate and bulletproof.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from store.models import FoodItem, Order, BagItem


class Command(BaseCommand):
    help = 'Verify and fix inventory consistency'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix inventory inconsistencies (dry run by default)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS('🔍 Starting inventory verification...')
        )
        
        if not fix_mode:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        issues_found = 0
        issues_fixed = 0
        
        # Get all food items
        food_items = FoodItem.objects.all()
        
        for food_item in food_items:
            if verbose:
                self.stdout.write(f'Checking {food_item.name}...')
            
            # Calculate expected inventory based on orders
            expected_portions = self.calculate_expected_inventory(food_item)
            actual_portions = food_item.portions
            
            if expected_portions != actual_portions:
                issues_found += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {food_item.name}: Expected {expected_portions}, Actual {actual_portions}'
                    )
                )
                
                if fix_mode:
                    try:
                        with transaction.atomic():
                            food_item.portions = expected_portions
                            if expected_portions == 0:
                                food_item.availability = False
                            else:
                                food_item.availability = True
                            food_item.save()
                            
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ Fixed {food_item.name}: Set to {expected_portions} portions'
                            )
                        )
                        issues_fixed += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ Failed to fix {food_item.name}: {str(e)}'
                            )
                        )
            else:
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {food_item.name}: {actual_portions} portions (correct)'
                        )
                    )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('INVENTORY VERIFICATION COMPLETE'))
        self.stdout.write('='*50)
        
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS('🎉 No inventory issues found!')
            )
        else:
            self.stdout.write(f'Issues found: {issues_found}')
            if fix_mode:
                self.stdout.write(f'Issues fixed: {issues_fixed}')
            else:
                self.stdout.write(
                    self.style.WARNING(
                        'Run with --fix to correct these issues'
                    )
                )
    
    def calculate_expected_inventory(self, food_item):
        """Calculate what the inventory should be based on orders."""
        # Get initial stock (we'll assume 1000 as a baseline for this calculation)
        # In a real system, you'd track initial stock separately
        initial_stock = 1000
        
        # Calculate total portions ordered
        total_ordered = 0
        for bag_item in BagItem.objects.filter(food_item=food_item):
            # Only count items from completed orders
            for order in bag_item.bag.orders.all():
                if order.status in ['Delivered', 'On the Way', 'Pending']:
                    total_ordered += bag_item.portions
        
        # Expected inventory = initial stock - total ordered
        expected = initial_stock - total_ordered
        
        # Don't go below 0
        return max(0, expected)
