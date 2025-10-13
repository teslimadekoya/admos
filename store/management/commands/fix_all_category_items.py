from django.core.management.base import BaseCommand
from store.models import FoodItem, Category


class Command(BaseCommand):
    help = 'Fix any food items that are incorrectly assigned to the "All" category'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get the "All" category
        try:
            all_category = Category.objects.get(name='All')
        except Category.DoesNotExist:
            self.stdout.write(
                self.style.WARNING('No "All" category found. Nothing to fix.')
            )
            return
        
        # Find items assigned to "All" category
        items_in_all_category = FoodItem.objects.filter(category=all_category)
        
        if not items_in_all_category.exists():
            self.stdout.write(
                self.style.SUCCESS('No items found in "All" category. All good!')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {items_in_all_category.count()} items in "All" category:')
        )
        
        # Get the first available category that's not "All"
        other_category = Category.objects.exclude(name='All').first()
        
        if not other_category:
            self.stdout.write(
                self.style.ERROR('No valid categories found! Cannot fix items.')
            )
            return
        
        for item in items_in_all_category:
            self.stdout.write(f'  - {item.name} (ID: {item.id})')
            
            if not dry_run:
                # Assign to the first available category
                item.category = other_category
                item.save()
                self.stdout.write(
                    self.style.SUCCESS(f'    ✓ Moved to "{other_category.name}" category')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'    → Would move to "{other_category.name}" category')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a dry run. Use without --dry-run to apply changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully fixed {items_in_all_category.count()} items!')
            )
