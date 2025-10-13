# Generated manually for POS support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0022_merge_20250924_1444'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_type',
            field=models.CharField(choices=[('online', 'Online'), ('physical', 'Physical')], default='online', max_length=10),
        ),
        migrations.AddField(
            model_name='payment',
            name='payment_method',
            field=models.CharField(choices=[('cash', 'Cash'), ('transfer', 'Bank Transfer'), ('card', 'Card'), ('paystack', 'Paystack Online')], default='paystack', max_length=10),
        ),
    ]
