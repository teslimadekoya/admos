import random
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from twilio.rest import Client

from .models import OTP
from .serializers import OTPVerifySerializer, ProfileSerializer

User = get_user_model()

# 1️⃣ Request OTP
class RequestOTPView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response({"error": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists by phone number or email
        email = request.data.get('email', '')
        
        # Check by phone number
        try:
            existing_user = User.objects.get(phone_number=phone_number)
            return Response({
                "error": "Account exists. Please log in.",
                "user_exists": True
            }, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            pass
        
        # Check by email (if email is provided)
        if email:
            try:
                existing_user = User.objects.get(email=email)
                return Response({
                    "error": "Account exists. Please log in.",
                    "user_exists": True
                }, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                pass

        # Store user data in session for later use during OTP verification
        request.session['pending_user_data'] = {
            'first_name': request.data.get('first_name', ''),
            'last_name': request.data.get('last_name', ''),
            'email': request.data.get('email', ''),
            'phone_number': phone_number
        }

        otp_code = str(random.randint(10000, 99999))
        OTP.objects.create(phone_number=phone_number, code=otp_code)

        # Format phone number for Twilio (add +234 if it starts with 0)
        formatted_phone = phone_number
        if phone_number.startswith('0'):
            formatted_phone = '+234' + phone_number[1:]
        elif not phone_number.startswith('+'):
            formatted_phone = '+234' + phone_number

        # Send SMS via Twilio
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"Your OTP is {otp_code}",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=formatted_phone
            )
        except Exception as e:
            # Log the error but don't fail the request - OTP is still created
            print(f"Twilio error: {str(e)}")
            # For development, you might want to return success even if SMS fails
            # return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # For development, include OTP in response for testing
        response_data = {"message": "OTP sent successfully"}
        if settings.DEBUG:
            response_data["otp_code"] = otp_code  # Only in development
        
        return Response(response_data, status=status.HTTP_200_OK)

# 2️⃣ Verify OTP & Create User
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        print(f"VerifyOTP request received: {request.data}")
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp')
        
        if not phone_number or not otp_code:
            return Response({"error": "Phone number and OTP required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp = OTP.objects.filter(phone_number=phone_number, code=otp_code).latest('created_at')
            print(f"OTP found: {otp}")
        except OTP.DoesNotExist:
            print(f"No OTP found for phone: {phone_number}, code: {otp_code}")
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_expired():
            print(f"OTP expired: {otp}")
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

        # Get user data from session or request
        user_data = request.session.get('pending_user_data', {})
        if not user_data:
            # Fallback to request data if session data not available
            user_data = {
                'first_name': request.data.get('first_name', ''),
                'last_name': request.data.get('last_name', ''),
                'email': request.data.get('email', ''),
                'phone_number': phone_number
            }

        # Check if user already exists
        try:
            existing_user = User.objects.get(phone_number=phone_number)
            print(f"User already exists: {existing_user}")
            # User already exists, just log them in
            otp.delete()
            
            # Clear session data
            if 'pending_user_data' in request.session:
                del request.session['pending_user_data']
            
            refresh = RefreshToken.for_user(existing_user)
            print(f"Tokens generated for existing user: {existing_user.phone_number}")
            
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "message": "Account already exists. Logged in successfully."
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # User doesn't exist, create new user
            user = User.objects.create(
                phone_number=phone_number,
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                email=user_data.get('email', None),
                role='customer'
            )
            print(f"New user created: {user}")
            
            otp.delete()
            
            # Clear session data
            if 'pending_user_data' in request.session:
                del request.session['pending_user_data']

            refresh = RefreshToken.for_user(user)
            print(f"Tokens generated for new user: {user.phone_number}")
            
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "message": "Account created successfully."
            }, status=status.HTTP_201_CREATED)

# 3️⃣ Login (Phone Only - for customers)
class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        print(f"Login request received: {request.data}")  # Debug log
        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response({"error": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number)
            # Only allow customers to login to customer website
            if user.role != 'customer':
                return Response({"error": "Access denied. This account cannot login to customer website."}, status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(user)
        return Response({"refresh": str(refresh), "access": str(refresh.access_token)}, status=status.HTTP_200_OK)


# 4️⃣ Profile (Authenticated)
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        print(f"Profile request from user: {request.user}")
        print(f"User authenticated: {request.user.is_authenticated}")
        serializer = ProfileSerializer(request.user)
        print(f"Profile data: {serializer.data}")
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Profile updated successfully"}, status=status.HTTP_200_OK)

# 5️⃣ Setup Django Session (for template authentication)
class SetupSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # This endpoint is called after JWT authentication to set up Django session
        # The user is already authenticated via JWT, so we just return success
        return Response({"message": "Session setup successful"}, status=status.HTTP_200_OK)

# 6️⃣ Request Password Reset OTP
class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response({"error": "Phone number required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number, role='customer')
        except User.DoesNotExist:
            return Response({"error": "No account found with this phone number"}, status=status.HTTP_404_NOT_FOUND)

        # Generate and store OTP
        otp_code = str(random.randint(10000, 99999))
        OTP.objects.create(
            phone_number=phone_number,
            code=otp_code
        )
        
        # Send OTP via SMS
        try:
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            # Format phone number for Twilio
            if phone_number.startswith('0'):
                formatted_phone = '+234' + phone_number[1:]
            elif not phone_number.startswith('+'):
                formatted_phone = '+234' + phone_number
            else:
                formatted_phone = phone_number
            
            message = twilio_client.messages.create(
                body=f"Your password reset code is: {otp_code}. This code expires in 10 minutes.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=formatted_phone
            )
            
            response_data = {"message": "OTP sent to your phone for password reset"}
            
            # Include OTP in development
            if settings.DEBUG:
                response_data["otp_code"] = otp_code
                
        except Exception as e:
            print(f"Failed to send OTP: {e}")
            # Still return success in development
            response_data = {"message": "OTP sent to your phone for password reset"}
            if settings.DEBUG:
                response_data["otp_code"] = otp_code
        
        return Response(response_data, status=status.HTTP_200_OK)

# 7️⃣ Verify Password Reset OTP & Reset Password
class VerifyPasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')
        
        if not all([phone_number, otp_code, new_password]):
            return Response({"error": "Phone number, OTP, and new password required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp = OTP.objects.filter(phone_number=phone_number, code=otp_code).latest('created_at')
        except OTP.DoesNotExist:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        if otp.is_expired():
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone_number, role='customer')
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Delete used OTP
        otp.delete()
        
        return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)

# 8️⃣ Logout
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
