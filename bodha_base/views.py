from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect


@login_required
def app_selector(request):
    """登录后的应用选择页面"""
    return render(request, 'app_selector.html')


def root_redirect(request):
    """根据登录状态跳转到登录或应用选择页"""
    if request.user.is_authenticated:
        return redirect('app_selector')
    return redirect('login')
