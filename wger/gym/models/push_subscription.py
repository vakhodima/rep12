from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=500)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'endpoint')
        app_label = 'gym'

    def __str__(self):
        return f'Push:{self.user.username}:{self.endpoint[:40]}'
