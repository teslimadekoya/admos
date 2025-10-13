# Generated manually to update payment method choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0023_add_pos_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('transfer', 'Bank Transfer'),
                    ('card', 'Card'),
                    ('paystack_card', 'Paystack Card'),
                    ('paystack_bank_transfer', 'Paystack Bank Transfer'),
                    ('paystack_ussd', 'Paystack USSD'),
                    ('paystack_mobile_money', 'Paystack Mobile Money'),
                    ('paystack_qr', 'Paystack QR'),
                ],
                default='paystack_card',
                max_length=25,
            ),
        ),
    ]

