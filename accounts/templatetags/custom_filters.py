import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def format_post(text):
    # Делаем хэштеги кликабельными
    text = re.sub(r'#(\w+)', r'<a href="/search/?q=\1" style="color: #6366f1; text-decoration: none;">#\1</a>', text)
    # Делаем упоминания кликабельными
    text = re.sub(r'@(\w+)', r'<a href="/profile/\1/" style="color: #6366f1; font-weight: 600; text-decoration: none;">@\1</a>', text)
    return mark_safe(text)