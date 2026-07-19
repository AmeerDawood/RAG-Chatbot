from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Minimal custom user: email-based login, staff flag gates document admin endpoints.

    Fields that only existed to support dropped features in the original project
    (OTP-based password reset, profile pictures, phone numbers, last-active
    tracking) are intentionally not carried over here.
    """

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
