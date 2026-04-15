from django.contrib.auth.models import User
from django.db import models


class CheckIn(models.Model):
    MOOD_CHOICES = [
        (5, 'Отлично'),
        (4, 'Хорошо'),
        (3, 'Нормально'),
        (2, 'Так себе'),
        (1, 'Плохо'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='checkins')
    date = models.DateField(auto_now_add=True)
    mood = models.PositiveSmallIntegerField(choices=MOOD_CHOICES)
    energy = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text='1-5',
    )
    sleep = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text='1-5',
    )
    notes = models.TextField(blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.user.username} - {self.date}'

    def get_owner_object(self):
        return self
