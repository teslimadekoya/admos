from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone

# -------------------
# User Manager
# -------------------
class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, role='customer', **extra_fields):
        if not phone_number:
            raise ValueError("Users must have a phone number")
        
        # Prevent creating admin users through create_user
        if role == 'admin':
            from django.core.exceptions import ValidationError
            raise ValidationError("Admin users can only be created through create_superuser.")
        
        user = self.model(phone_number=phone_number, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        # Allow up to 2 admin accounts
        admin_count = User.objects.filter(role='admin').count()
        if admin_count >= 2:
            from django.core.exceptions import ValidationError
            raise ValidationError("Maximum of 2 admin accounts allowed.")
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        user = self.create_user(phone_number, password, role='admin', **extra_fields)
        return user
    
    def create_accountant(self, phone_number, password=None, **extra_fields):
        """Create an accountant user with view-only access."""
        # Check if accountant already exists
        if User.objects.filter(role='accountant').exists():
            from django.core.exceptions import ValidationError
            raise ValidationError("Only one accountant account is allowed.")
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)
        user = self.create_user(phone_number, password, role='accountant', **extra_fields)
        return user


# -------------------
# User Model
# -------------------
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('manager', 'Manager'),
        ('accountant', 'Accountant'),
        ('admin', 'Admin'),
    )


    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True)
    delivery_address = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else None

    def clean(self):
        """Ensure maximum of 2 admin accounts, 1 manager account, and 1 accountant account."""
        super().clean()
        if self.role == 'admin':
            # Check if there are already 2 admin accounts (excluding self if updating)
            existing_admins = User.objects.filter(role='admin').exclude(pk=self.pk)
            if existing_admins.count() >= 2:
                from django.core.exceptions import ValidationError
                raise ValidationError("Maximum of 2 admin accounts allowed.")
        elif self.role == 'manager':
            # Check if there's already a manager account (excluding self if updating)
            existing_manager = User.objects.filter(role='manager').exclude(pk=self.pk)
            if existing_manager.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("Only one manager account is allowed.")
        elif self.role == 'accountant':
            # Check if there's already an accountant account (excluding self if updating)
            existing_accountant = User.objects.filter(role='accountant').exclude(pk=self.pk)
            if existing_accountant.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("Only one accountant account is allowed.")

    def save(self, *args, **kwargs):
        """Override save to call clean method."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.phone_number} ({self.role})"


# -------------------
# OTP Model
# -------------------
class OTP(models.Model):
    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 300

    def __str__(self):
        return f"{self.phone_number} - {self.code}"
