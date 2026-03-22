from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField("显示名称", max_length=80, blank=True)
    phone = models.CharField("联系电话", max_length=32, blank=True)
    is_merchant = models.BooleanField("商家账号", default=False)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.username
