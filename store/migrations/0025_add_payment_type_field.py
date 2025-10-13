# Generated manually to add payment_type field and update payment method choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0024_update_payment_method_choices'),
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
                    ('paystack', 'Paystack'),
                ],
                default='paystack',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='payment',
            name='payment_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('card', 'Card'),
                    ('bank_transfer', 'Bank Transfer'),
                    ('ussd', 'USSD'),
                    ('mobile_money', 'Mobile Money'),
                    ('qr', 'QR Code'),
                ],
                help_text='Specific payment type for Paystack payments',
                max_length=15,
                null=True,
            ),
        ),
    ]

