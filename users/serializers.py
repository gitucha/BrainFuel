from rest_framework import serializers
from django.contrib.auth import get_user_model,authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import TermsAndConditions, UserTermsAcceptance

User = get_user_model()

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field =  'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
  
        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        
        data = super().validate(attrs)
        data["Welcome Back!"] = user.username
        
        return data
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        token['Welcome back!'] = user.username
        
        return token
    

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("email", "username", "password")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already registered")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username is already taken")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email','is_premium','subscription_plan',  'xp', 'level', 'badges', 'bio', 'profile_picture','is_staff']

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

class TermsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndConditions
        fields = ['id', 'version', 'content', 'created_at', 'updated_at']

class UserTermsAcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTermsAcceptance
        fields = ['id', 'user', 'terms', 'accepted_at']