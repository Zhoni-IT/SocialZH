from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
import datetime


# Функции для путей сохранения файлов
def user_directory_path(instance, filename):
    return f'profile_pics/user_{instance.id}/{filename}'


def post_image_path(instance, filename):
    return f'posts/user_{instance.id}/{filename}'


class CustomUser(AbstractUser):
    # Роли пользователей
    ROLE_CHOICES = [
        ('user', 'Обычный пользователь'),
        ('moderator', 'Модератор'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')

    email = models.EmailField(unique=True, blank=True)
    profile_picture = models.ImageField(upload_to=user_directory_path, default='default.jpg', blank=True)

    # Экономика и Викторина
    coins = models.IntegerField(default=0)
    quiz_attempts = models.IntegerField(default=0)  # Кол-во попыток за сегодня
    last_quiz_date = models.DateTimeField(null=True, blank=True)  # Когда играл в последний раз

    # Улучшения с таймером
    gold_border_until = models.DateTimeField(null=True, blank=True)
    verified_until = models.DateTimeField(null=True, blank=True)

    # Статистика регистрации
    reg_stats = models.JSONField(default=dict, blank=True)

    # Подписки: кто на кого подписан
    followers = models.ManyToManyField('self', symmetrical=False, related_name='following', blank=True)

    def __str__(self):
        return self.username or f"{self.first_name} {self.last_name}"

    # --- ЛОГИКА ВИКТОРИНЫ ---
    def check_quiz_attempts(self):
        """
        Проверяет, нужно ли сбросить счетчик попыток (если прошли сутки).
        Возвращает количество оставшихся бесплатных попыток.
        """
        now = timezone.now()

        # Если записи о последней игре нет или прошел 1 день (24 часа)
        if not self.last_quiz_date or (now - self.last_quiz_date).days >= 1:
            self.quiz_attempts = 0
            self.save()

        return max(0, 3 - self.quiz_attempts)

    # --- УДОБНЫЕ СВОЙСТВА ---
    @property
    def has_gold_border(self):
        return self.gold_border_until and self.gold_border_until > timezone.now()

    @property
    def has_verified(self):
        return self.verified_until and self.verified_until > timezone.now()

    # --- ПРОВЕРКА РОЛЕЙ ---
    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_moderator(self):
        return self.role == 'moderator'

    @property
    def is_regular_user(self):
        return self.role == 'user'

    # Админ имеет бесконечные монеты
    @property
    def has_infinite_coins(self):
        return self.is_admin

    @property
    def followers_count(self):
        return self.followers.count()

    @property
    def following_count(self):
        return self.following.count()

    def is_following(self, other_user):
        return self.following.filter(pk=other_user.pk).exists()
class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return f"#{self.name}"


class Post(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='posts/', null=True, blank=True)
    caption = models.TextField()
    location = models.CharField(max_length=255, blank=True, null=True) # Добавлено
    hashtags = models.ManyToManyField('Hashtag', blank=True)           # Добавлено
    mentions = models.ManyToManyField(CustomUser, blank=True, related_name='mentions') # Добавлено
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.caption[:30]}"


class SavedPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} saved {self.post.id}"


class HiddenPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hidden_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='hidden_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} hid {self.post.id}"


class PostReport(models.Model):
    reporter = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reports')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reporter.username} reported {self.post.id}"


# ====================== СООБЩЕНИЯ И УВЕДОМЛЕНИЯ ======================

class Chat(models.Model):
    """Чат между двумя пользователями"""
    participants = models.ManyToManyField(CustomUser, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Chat {self.id}"
    
    def get_other_user(self, user):
        """Получить другого участника чата"""
        return self.participants.exclude(id=user.id).first()


class Message(models.Model):
    """Сообщение в чате"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    image = models.ImageField(upload_to='messages/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"


class Notification(models.Model):
    """Уведомления для пользователей и системные предупреждения"""
    TYPES = [
        ('message', 'Новое сообщение'),
        ('follow', 'Новый подписчик'),
        ('mention', 'Упоминание в посте'),
        ('system_warning', 'Системное предупреждение'),
        ('system_info', 'Системное уведомление'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPES)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, 
                              related_name='sent_notifications', null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_type_display()}"