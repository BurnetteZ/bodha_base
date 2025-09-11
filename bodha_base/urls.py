"""
URL configuration for bodha_base project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views as root_views

urlpatterns = [
    # 1. 根路径根据登录状态重定向
    path('', root_views.root_redirect, name='root-redirect'),

    # 2. Admin 后台
    path('admin/', admin.site.urls),

    # 3. Django 自带的认证路由：login、logout、password_change、password_reset 等
    path('accounts/', include('django.contrib.auth.urls')),


    # 4. benford路由
    path('benford/', include('benford.urls')),

    # 5. Excel 合并应用
    path('excel_merge/', include('excel_merge.urls')),

    # 6. 登录后应用选择页面
    path('apps/', root_views.app_selector, name='app_selector'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
