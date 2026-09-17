from django.db import models

class Account(models.Model):
    google_sub = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True)
    pin_hash = models.CharField(max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

class MonthlyUsage(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    month = models.DateField()
    model_name = models.CharField(max_length=80)
    scans = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['account','month','model_name'], name='unique_monthly_usage')]
