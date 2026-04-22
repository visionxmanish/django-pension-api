from django.db import models

class User(models.Model):
    pension_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.pension_id})"

class FaceEncoding(models.Model):
    user = models.ForeignKey(User, related_name="face_encodings", on_delete=models.CASCADE)
    embedding = models.JSONField()  # Storing embedding as a JSON list

    def __str__(self):
        return f"Face encoding for {self.user.name}"

class Verification(models.Model):
    user = models.ForeignKey(User, related_name="verifications", on_delete=models.CASCADE)
    status = models.CharField(max_length=50)  # "success" or "failure"
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Verification for {self.user.name} - {self.status}"
