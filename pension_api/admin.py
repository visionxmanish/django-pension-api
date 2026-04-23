from django.contrib import admin
from .models import User, Nominee, Verification, NomineeVerification


# Register your models here.
admin.site.register(User)
admin.site.register(Nominee)
admin.site.register(Verification)
admin.site.register(NomineeVerification)
