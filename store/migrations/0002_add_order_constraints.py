# Generated manually to add constraints for preventing incomplete orders

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0001_initial'),
    ]

    operations = [
        # Add constraints to prevent incomplete orders
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(
                check=models.Q(delivery_fee__gte=0) & models.Q(delivery_fee__lte=10000),
                name='valid_delivery_fee'
            ),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(
                check=models.Q(service_charge__gte=0) & models.Q(service_charge__lte=5000),
                name='valid_service_charge'
            ),
        ),
    ]
