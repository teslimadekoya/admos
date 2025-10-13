from django.core.management.base import BaseCommand
from store.models import SystemSettings


class Command(BaseCommand):
    help = 'Initialize default system settings'

    def handle(self, *args, **options):
        """Initialize default system settings if they don't exist."""
        
        default_settings = [
            {
                'setting_type': 'service_charge',
                'value': 100.00,
                'description': 'Fixed service charge applied to all orders'
            },
            {
                'setting_type': 'vat_percentage',
                'value': 7.5,
                'description': 'VAT percentage applied to order subtotal'
            },
            {
                'setting_type': 'delivery_fee_base',
                'value': 500.00,
                'description': 'Base delivery fee (can be adjusted based on location)'
            },
            {
                'setting_type': 'plate_fee',
                'value': 50.00,
                'description': 'Fee per plate for food items'
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for setting_data in default_settings:
            setting, created = SystemSettings.objects.get_or_create(
                setting_type=setting_data['setting_type'],
                defaults={
                    'value': setting_data['value'],
                    'description': setting_data['description'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created {setting_data["setting_type"]}: {setting_data["value"]}'
                    )
                )
            else:
                # Update description if it's different
                if setting.description != setting_data['description']:
                    setting.description = setting_data['description']
                    setting.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Updated description for {setting_data["setting_type"]}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSystem settings initialization complete!\n'
                f'Created: {created_count} settings\n'
                f'Updated: {updated_count} settings'
            )
        )

