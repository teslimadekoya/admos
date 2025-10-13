"""
Custom Password Validators for Enhanced Security
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger('food_ordering.security')

class ComplexPasswordValidator:
    """
    Validate that the password meets complex security requirements
    """
    
    def __init__(self, min_length=12, require_uppercase=True, require_lowercase=True, 
                 require_digits=True, require_special=True, max_similarity=0.7):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special
        self.max_similarity = max_similarity
    
    def validate(self, password, user=None):
        errors = []
        
        # Check minimum length
        if len(password) < self.min_length:
            errors.append(
                ValidationError(
                    _("Password must be at least %(min_length)d characters long."),
                    code='password_too_short',
                    params={'min_length': self.min_length},
                )
            )
        
        # Check for uppercase letters
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one uppercase letter."),
                    code='password_no_upper',
                )
            )
        
        # Check for lowercase letters
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one lowercase letter."),
                    code='password_no_lower',
                )
            )
        
        # Check for digits
        if self.require_digits and not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one digit."),
                    code='password_no_digit',
                )
            )
        
        # Check for special characters
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)."),
                    code='password_no_special',
                )
            )
        
        # Check for common patterns
        if self._has_common_patterns(password):
            errors.append(
                ValidationError(
                    _("Password contains common patterns and is not secure enough."),
                    code='password_common_pattern',
                )
            )
        
        # Check for sequential characters
        if self._has_sequential_chars(password):
            errors.append(
                ValidationError(
                    _("Password contains sequential characters and is not secure enough."),
                    code='password_sequential',
                )
            )
        
        # Check for repeated characters
        if self._has_repeated_chars(password):
            errors.append(
                ValidationError(
                    _("Password contains too many repeated characters."),
                    code='password_repeated',
                )
            )
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        help_texts = [
            f"Your password must be at least {self.min_length} characters long.",
        ]
        
        if self.require_uppercase:
            help_texts.append("It must contain at least one uppercase letter.")
        if self.require_lowercase:
            help_texts.append("It must contain at least one lowercase letter.")
        if self.require_digits:
            help_texts.append("It must contain at least one digit.")
        if self.require_special:
            help_texts.append("It must contain at least one special character.")
        
        help_texts.extend([
            "It cannot contain common patterns or sequential characters.",
            "It cannot have more than 2 repeated characters in a row."
        ])
        
        return " ".join(help_texts)
    
    def _has_common_patterns(self, password):
        """Check for common password patterns"""
        common_patterns = [
            r'password', r'123456', r'qwerty', r'abc123', r'admin',
            r'welcome', r'login', r'master', r'secret', r'letmein'
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if re.search(pattern, password_lower):
                return True
        return False
    
    def _has_sequential_chars(self, password):
        """Check for sequential characters"""
        # Check for sequential numbers
        for i in range(len(password) - 2):
            if (password[i].isdigit() and password[i+1].isdigit() and password[i+2].isdigit()):
                if (int(password[i+1]) == int(password[i]) + 1 and 
                    int(password[i+2]) == int(password[i]) + 2):
                    return True
        
        # Check for sequential letters
        for i in range(len(password) - 2):
            if (password[i].isalpha() and password[i+1].isalpha() and password[i+2].isalpha()):
                if (ord(password[i+1].lower()) == ord(password[i].lower()) + 1 and 
                    ord(password[i+2].lower()) == ord(password[i].lower()) + 2):
                    return True
        
        return False
    
    def _has_repeated_chars(self, password):
        """Check for repeated characters"""
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        return False

class PhoneNumberValidator:
    """
    Validate phone number format and security
    """
    
    def __init__(self):
        self.phone_pattern = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    def validate(self, phone_number):
        if not phone_number:
            raise ValidationError(_("Phone number is required."))
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone_number)
        
        if not self.phone_pattern.match(cleaned):
            raise ValidationError(
                _("Enter a valid phone number. It should start with a country code."),
                code='invalid_phone'
            )
        
        # Check for suspicious patterns
        if self._is_suspicious_phone(cleaned):
            logger.warning(f"Suspicious phone number detected: {phone_number}")
            raise ValidationError(
                _("This phone number appears to be invalid or suspicious."),
                code='suspicious_phone'
            )
    
    def _is_suspicious_phone(self, phone):
        """Check for suspicious phone number patterns"""
        # Remove + and check for patterns
        digits = phone.lstrip('+')
        
        # All same digits
        if len(set(digits)) == 1:
            return True
        
        # Sequential numbers
        if digits in ['1234567890', '0123456789', '9876543210']:
            return True
        
        # Too short or too long
        if len(digits) < 10 or len(digits) > 15:
            return True
        
        return False

class EmailSecurityValidator:
    """
    Validate email addresses for security
    """
    
    def __init__(self):
        self.email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
    
    def validate(self, email):
        if not email:
            return
        
        if not self.email_pattern.match(email):
            raise ValidationError(
                _("Enter a valid email address."),
                code='invalid_email'
            )
        
        # Check for suspicious email patterns
        if self._is_suspicious_email(email):
            logger.warning(f"Suspicious email detected: {email}")
            raise ValidationError(
                _("This email address appears to be suspicious."),
                code='suspicious_email'
            )
    
    def _is_suspicious_email(self, email):
        """Check for suspicious email patterns"""
        email_lower = email.lower()
        
        # Temporary email services
        temp_domains = [
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        ]
        
        domain = email_lower.split('@')[1] if '@' in email_lower else ''
        if domain in temp_domains:
            return True
        
        # Suspicious patterns
        suspicious_patterns = [
            r'[0-9]{10,}@',  # Many numbers
            r'(.)\1{4,}@',   # Repeated characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, email_lower):
                return True
        
        return False
