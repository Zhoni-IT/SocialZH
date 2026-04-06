from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    CustomUser,
    Post,
    Hashtag,
    SavedPost,
    HiddenPost,
    PostReport,
    Chat,
    Message,
    Notification,
)


# ==================== ЭКШЕНЫ (МАССОВЫЕ ДЕЙСТВИЯ) ====================

@admin.action(description='Сбросить попытки викторины (3/3)')
def reset_quiz_attempts(modeladmin, request, queryset):
    queryset.update(quiz_attempts=0, last_quiz_date=timezone.now())


@admin.action(description='Начислить +100 монет')
def gift_coins(modeladmin, request, queryset):
    for user in queryset:
        user.coins += 100
        user.save()


@admin.action(description='Заблокировать выбранных пользователей')
def deactivate_users(modeladmin, request, queryset):
    queryset.update(is_active=False)


# ==================== ПОСТЫ (МОДЕРАЦИЯ КОНТЕНТА) ====================

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    # Добавляем превью и ID для удобства
    list_display = ('id', 'image_preview', 'user', 'caption_short', 'created_at')
    list_display_links = ('id', 'image_preview')  # Клик по фото открывает пост
    list_filter = ('created_at', 'user')
    search_fields = ('caption', 'user__username')
    ordering = ('-created_at',)

    # Быстрое удаление постов (встроено в Django, но можно добавить свои)

    def caption_short(self, obj):
        """Ограничиваем длину текста в списке, чтобы не раздувать таблицу"""
        return (obj.caption[:50] + '...') if len(obj.caption) > 50 else obj.caption

    caption_short.short_description = 'Текст поста'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="60" height="60" style="object-fit:cover; border-radius:8px; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return "Нет фото"

    image_preview.short_description = 'Превью'


@admin.action(description='Отправить системное предупреждение выбранным пользователям')
def send_system_warning(modeladmin, request, queryset):
    for user in queryset:
        Notification.objects.create(
            user=user,
            type='system_warning',
            sender=request.user if request.user.is_authenticated else None,
            title='Предупреждение от администрации',
            content='Ваш аккаунт получил административное предупреждение. Пожалуйста, соблюдайте правила сообщества.',
            is_read=False
        )
    modeladmin.message_user(request, 'Предупреждения отправлены выбранным пользователям.')


class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = (
        'username',
        'email',
        'role',
        'coins',
        'quiz_attempts',
        'is_active',
        'is_staff',
        'date_joined'
    )
    list_display_links = ('username',)
    list_editable = ('role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff', 'last_quiz_date', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    actions = [reset_quiz_attempts, gift_coins, deactivate_users, send_system_warning]
    ordering = ('username',)
    filter_horizontal = ('followers',)

    fieldsets = UserAdmin.fieldsets + (
        ('Модерация и Экономика', {
            'fields': (
                'role',
                'coins',
                'quiz_attempts',
                'last_quiz_date',
                'gold_border_until',
                'verified_until',
                'profile_picture',
                'reg_stats',
                'followers',
            ),
            'description': 'Управление правами, игровыми ресурсами и связями пользователя.'
        }),
    )

    readonly_fields = ('date_joined', 'last_login')

    def get_full_name(self, obj):
        return obj.get_full_name()


@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(SavedPost)
class SavedPostAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    search_fields = ('user__username', 'post__caption')
    list_filter = ('created_at',)


@admin.register(HiddenPost)
class HiddenPostAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    search_fields = ('user__username', 'post__caption')
    list_filter = ('created_at',)


@admin.register(PostReport)
class PostReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'post', 'reason', 'created_at')
    search_fields = ('reporter__username', 'post__caption', 'reason')
    list_filter = ('created_at',)


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_participants', 'created_at', 'updated_at')
    search_fields = ('participants__username',)
    filter_horizontal = ('participants',)

    def get_participants(self, obj):
        return ", ".join([user.username for user in obj.participants.all()])

    get_participants.short_description = 'Участники'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'sender', 'content_short', 'is_read', 'created_at')
    search_fields = ('content', 'sender__username', 'chat__participants__username')
    list_filter = ('is_read', 'created_at')

    def content_short(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')

    content_short.short_description = 'Сообщение'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sender', 'type', 'title', 'is_read', 'created_at')
    search_fields = ('user__username', 'sender__username', 'title', 'content')
    list_filter = ('type', 'is_read', 'created_at')
    actions = ['mark_as_read', 'mark_as_unread']

    @admin.action(description='Отметить выбранные уведомления как прочитанные')
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, 'Выбранные уведомления отмечены как прочитанные.')

    @admin.action(description='Отметить выбранные уведомления как непрочитанные')
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, 'Выбранные уведомления отмечены как непрочитанные.')


admin.site.register(CustomUser, CustomUserAdmin)
