from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

# 1️⃣ Signup Serializer (used after OTP verification)
class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'password', 'role']
        extra_kwargs = {'email': {'required': False}}

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

# 2️⃣ OTP Verification Serializer
class OTPVerifySerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField()
    otp = serializers.CharField(max_length=5)
    role = serializers.ChoiceField(choices=[('customer', 'Customer')], default='customer')

# 3️⃣ Login Serializer
class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

# 4️⃣ Profile Serializer
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'delivery_address', 'role']
