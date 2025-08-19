# Generated migration for CanvasOAuth2Token options

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('canvas_oauth', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='canvasoauth2token',
            options={'verbose_name': 'Canvas OAuth2 Token', 'verbose_name_plural': 'Canvas OAuth2 Tokens'},
        ),
    ]