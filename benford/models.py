from django.db import models

from django.conf import settings
from django.db import models


class BenfordAnalysis(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    data_file = models.FileField(upload_to='benford_uploads/')
    result_image = models.ImageField(upload_to='benford_uploads/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # 其他字段：如分析结果的统计数据（可选）
