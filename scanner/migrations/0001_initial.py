from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[
      migrations.CreateModel(name='Account',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('google_sub',models.CharField(max_length=255,unique=True)),('email',models.EmailField(max_length=254)),('name',models.CharField(blank=True,max_length=200)),('pin_hash',models.CharField(blank=True,max_length=256)),('created_at',models.DateTimeField(auto_now_add=True)),('last_login',models.DateTimeField(auto_now=True))]),
      migrations.CreateModel(name='MonthlyUsage',fields=[('id',models.BigAutoField(primary_key=True,serialize=False)),('month',models.DateField()),('model_name',models.CharField(max_length=80)),('scans',models.PositiveIntegerField(default=0)),('input_tokens',models.PositiveBigIntegerField(default=0)),('output_tokens',models.PositiveBigIntegerField(default=0)),('account',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,to='scanner.account'))]),
      migrations.AddConstraint(model_name='monthlyusage',constraint=models.UniqueConstraint(fields=('account','month','model_name'),name='unique_monthly_usage'))]
