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
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
          username = validated_data.get('username') or validated_data['email'].split('@')[0],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email','is_premium',  'xp', 'level', 'badges', 'bio', 'profile_picture']

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