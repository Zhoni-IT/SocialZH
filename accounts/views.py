from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.conf import settings
from .forms import RegisterForm, ProfilePictureForm, PostForm
from .models import CustomUser, Post, Hashtag, SavedPost, HiddenPost, PostReport, Chat, Message, Notification
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
import random
import string
import time
import os
import json
import requests
from pathlib import Path
import datetime


# --- ДЕКОРАТОРЫ ДЛЯ ПРОВЕРКИ РОЛЕЙ ---
def admin_required(view_func):
    """Проверяет, является ли пользователь админом"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin:
            return JsonResponse({'success': False, 'message': 'Доступ запрещен'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def moderator_or_admin_required(view_func):
    """Проверяет, является ли пользователь модератором или админом"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_moderator or request.user.is_admin):
            return JsonResponse({'success': False, 'message': 'Доступ запрещен'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper

# ====================== CHATBOT HELPERS ======================
BOT_HISTORY_DIR = os.path.join(settings.BASE_DIR, 'bot_data')
Path(BOT_HISTORY_DIR).mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = getattr(settings, 'GROQ_API_KEY', None)
GROQ_MODEL = getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_API_URL = getattr(settings, 'GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')

PROJECT_DESCRIPTION = '''Ты помощник проекта SocialZH.
SocialZH — это мобильная социальная сеть на Django.

Проект содержит:
- модель CustomUser с ролями user/moderator/admin, монетами, попытками викторины, аватаркой и подписчиками;
- посты с изображениями, подписью, локацией, хэштегами и упоминаниями;
- возможность сохранять посты, скрывать их и жаловаться;
- чат между пользователями и хранение сообщений;
- уведомления для новых сообщений, подписок, упоминаний и системных предупреждений;
- дополнительные сервисы: магазин, викторина, генератор паролей, проверка пароля, сортировка слов.

Чатбот должен отвечать на любые вопросы, понимать контекст проекта и помогать пользователю как умный ассистент.'''


def get_bot_history_path(user):
    return os.path.join(BOT_HISTORY_DIR, f'bot_history_{user.id}.json')


def load_bot_history(user):
    path = get_bot_history_path(user)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get('messages', [])
            return []
    except Exception:
        return []


def save_bot_history(user, messages):
    path = get_bot_history_path(user)
    payload = {
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        },
        'messages': messages,
        'updated_at': datetime.datetime.now().isoformat()
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def call_groq_api(prompt_text, history=None):
    if not GROQ_API_KEY:
        return None

    messages = [
        {'role': 'system', 'content': PROJECT_DESCRIPTION}
    ]

    if history:
        for item in history[-10:]:
            sender_id = item.get('sender__id')
            role = 'assistant' if sender_id == 'bot' else 'user'
            content = item.get('content', '').strip()
            if content:
                messages.append({'role': role, 'content': content})

    messages.append({'role': 'user', 'content': prompt_text})

    payload = {
        'model': GROQ_MODEL,
        'messages': messages,
        'temperature': 0.7,
        'max_tokens': 500
    }

    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)
        if settings.DEBUG:
            print('Groq API status:', response.status_code)
            if response.status_code != 200:
                print('Groq full error:', response.text[:1000])

        if response.status_code != 200:
            return None

        data = response.json()
        choices = data.get('choices') or []
        if choices:
            first_choice = choices[0]
            message = first_choice.get('message', {})
            if isinstance(message, dict):
                content = message.get('content')
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    return '\n'.join([c.get('text', '') for c in content if isinstance(c, dict) and c.get('text')])
    except requests.RequestException as e:
        if settings.DEBUG:
            print('Groq API error:', e)
        return None

    return None


def generate_bot_response(input_text, user=None):
    input_text = input_text.strip()
    if not input_text:
        return 'Пожалуйста, задайте вопрос.'

    history = []
    if user is not None:
        history = load_bot_history(user) or []

    response = call_groq_api(input_text, history=history)
    if response:
        return response

    return 'Извините, не удалось получить ответ от чатбота. Попробуйте задать вопрос чуть позже.'


import json
import re


# ====================== АВТОРИЗАЦИЯ И ПРОФИЛЬ ======================

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('profile')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if not username or not password:
            return render(request, 'accounts/login.html', {'error': 'Введите имя пользователя и пароль'})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('feed')
        else:
            return render(request, 'accounts/login.html', {'error': 'Неверное имя пользователя или пароль'})
    return render(request, 'accounts/login.html')


@login_required
def profile(request):
    posts = Post.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfilePictureForm(instance=request.user)
    context = {
        'profile_user': request.user,
        'posts': posts,
        'is_owner': True,
        'is_following': False,
        'form': form,
        'request': request,
    }
    return render(request, 'accounts/profile.html', context)


def profile_view(request, username):  # Новое
    profile_user = get_object_or_404(CustomUser, username=username)
    posts = Post.objects.filter(user=profile_user).order_by('-created_at')
    is_owner = request.user.is_authenticated and request.user == profile_user
    context = {
        'profile_user': profile_user,
        'posts': posts,
        'is_owner': is_owner,
        'is_following': request.user.is_authenticated and request.user.is_following(profile_user),
        'request': request,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def follow_toggle(request, username):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)

    target = get_object_or_404(CustomUser, username=username)
    user = request.user

    if target == user:
        return JsonResponse({'success': False, 'message': 'Нельзя подписаться на себя'})

    if user.is_following(target):
        user.following.remove(target)
        action = 'unfollow'
    else:
        user.following.add(target)
        action = 'follow'

    return JsonResponse({
        'success': True,
        'action': action,
        'followers_count': target.followers_count,
        'following_count': user.following_count,
    })


@login_required
def followers_list(request, username):
    profile_user = get_object_or_404(CustomUser, username=username)
    followers = profile_user.followers.all()
    following = profile_user.following.all()
    tab = request.GET.get('tab', 'followers')  # Можно выбрать, какую часть показать первой
    return render(request, 'accounts/followers.html', {
        'profile_user': profile_user,
        'followers': followers,
        'following': following,
        'tab': tab,
        'is_owner': request.user == profile_user,
        'request': request,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


# ====================== ЛЕНТА И КОНТЕНТ ======================

def feed(request):
    posts = Post.objects.order_by('-created_at')

    if request.user.is_authenticated:
        hidden_ids = HiddenPost.objects.filter(user=request.user).values_list('post_id', flat=True)
        posts = posts.exclude(id__in=hidden_ids)

    return render(request, 'accounts/feed.html', {'posts': posts})


@login_required
def post_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'accounts/post_detail.html', {'post': post})


@login_required
def hide_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)

    hidden, created = HiddenPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        return JsonResponse({'success': False, 'message': 'Пост уже скрыт'})

    return JsonResponse({'success': True, 'message': 'Пост скрыт'})


@login_required
def save_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)

    saved, created = SavedPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        saved.delete()
        return JsonResponse({'success': True, 'action': 'unsave', 'message': 'Пост удален из сохраненных'})
    else:
        return JsonResponse({'success': True, 'action': 'save', 'message': 'Пост сохранен'})


@login_required
def report_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)

    reason = request.POST.get('reason', '').strip() or 'Пожаловались без причины'
    PostReport.objects.create(reporter=request.user, post=post, reason=reason)
    return JsonResponse({'success': True, 'message': 'Жалоба отправлена'});


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            updated_post = form.save(commit=False)
            location = request.POST.get('location')
            if location is not None:
                updated_post.location = location
            updated_post.save()
            return redirect('feed')
    else:
        form = PostForm(instance=post)

    return render(request, 'accounts/edit_post.html', {'form': form, 'post': post})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if request.method == 'POST':
        post.delete()
        return JsonResponse({'success': True, 'message': 'Пост удален'})
    return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)


def search(request):  # Изменено
    query = request.GET.get('q', '').strip()
    profiles = []
    posts = []
    tag = None
    if query:
        if query.startswith('#'):
            tag_name = query[1:].lower()
            tag = Hashtag.objects.filter(name__iexact=tag_name).first()
            if tag:
                posts = Post.objects.filter(hashtags=tag).order_by('-created_at')
        else:
            profiles = CustomUser.objects.filter(username__icontains=query)
            posts = Post.objects.filter(caption__icontains=query).order_by('-created_at')
    context = {
        'query': query,
        'profiles': profiles,
        'posts': posts,
        'tag': tag,
    }
    return render(request, 'accounts/search.html', context)


@login_required
def add(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user

            # 1. Сохраняем локацию из скрытого поля (которое заполняется через prompt)
            location = request.POST.get('location')
            if location:
                post.location = location

            post.save()  # Сначала сохраняем пост, чтобы получить его ID для ManyToMany связей

            # 2. Обработка хэштегов (#тег)
            # Ищем все слова после символа #
            tags = re.findall(r'#(\w+)', post.caption)
            for tag_name in tags:
                # get_or_create найдет существующий тег или создаст новый
                tag, created = Hashtag.objects.get_or_create(name=tag_name.lower())
                post.hashtags.add(tag)

            # 3. Обработка упоминаний (@username)
            # Ищем все слова после символа @
            usernames = re.findall(r'@(\w+)', post.caption)
            for uname in usernames:
                try:
                    mentioned_user = CustomUser.objects.get(username=uname)
                    post.mentions.add(mentioned_user)
                except CustomUser.DoesNotExist:
                    continue  # Если пользователя не существует, просто пропускаем

            return redirect('feed')
    else:
        form = PostForm()
    return render(request, 'accounts/add.html', {'form': form})


def messages(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Получить все чаты текущего пользователя
    chats = request.user.chats.all().prefetch_related('participants').prefetch_related('messages')
    
    # Добавить информацию о другом пользователе для каждого чата
    chats_with_users = []
    unread_count = 0
    for chat in chats:
        other_user = chat.get_other_user(request.user)
        if other_user:
            chat.other_user = other_user
            chats_with_users.append(chat)
            unread_count += chat.messages.filter(is_read=False).exclude(sender=request.user).count()

    # Счётчик непрочитанных уведомлений
    unread_notifications = request.user.notifications.filter(is_read=False).count()

    return render(request, 'accounts/messages.html', {
        'chats': chats_with_users,
        'unread_count': unread_count,
        'unread_notifications': unread_notifications,
    })


# ====================== МОНЕТЫ И ИНСТРУМЕНТЫ ======================

@login_required
def update_coins(request):
    """Обновление монет (например, из мини-игр)"""
    if request.method == 'POST':
        try:
            earned = int(request.POST.get('earned', 0))
            request.user.coins += earned
            request.user.save()
            return JsonResponse({'status': 'OK', 'new_coins': request.user.coins})
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid value'})
    return JsonResponse({'status': 'error'})


def password_generator(request):
    context = {'password': '', 'length': 12}
    if request.method == 'POST':
        try:
            length = int(request.POST.get('length', 12))
            use_nums = request.POST.get('use_nums') == 'on'
            use_spec = request.POST.get('use_spec') == 'on'
            use_upper = request.POST.get('use_upper') == 'on'
            chars = string.ascii_lowercase
            if use_nums: chars += string.digits
            if use_spec: chars += "!@#$%^&*"
            if use_upper: chars += string.ascii_uppercase
            password = ''.join(random.choice(chars) for _ in range(length))
            context = {
                'password': password, 'length': length,
                'use_nums': use_nums, 'use_spec': use_spec, 'use_upper': use_upper,
            }
        except ValueError:
            context['error'] = 'Некорректная длина пароля'
    return render(request, 'accounts/password_generator.html', context)


def password_check(request):
    context = {}
    if request.method == 'POST':
        pwd = request.POST.get('password', '')
        checks = [
            len(pwd) >= 8,
            any(c.isupper() for c in pwd) and any(c.islower() for c in pwd),
            any(c.isdigit() for c in pwd),
            any(c in "!@#$%^&*()_+-=" for c in pwd)
        ]
        score = sum(checks)
        if score == 4:
            res, color = "Жоғары (Өте жақсы! ✅)", "#00b894"
        elif score >= 2:
            res, color = "Орташа (Жақсартуға болады ⚠️)", "#ff9f43"
        else:
            res, color = "Төмен (Қауіпті! ❌)", "#ee5253"
        context = {'pwd': pwd, 'res': res, 'color': color}
    return render(request, 'accounts/password_check.html', context)


@csrf_exempt
def sort_words(request):
    context = {}
    if request.method == 'POST':
        raw_text = request.POST.get('words_input', '')
        if raw_text:
            words_list = [w.strip() for w in re.split(r'[,\s\-]+', raw_text) if w.strip()]
            words_list.sort(key=str.lower)
            context['words'] = words_list
    return render(request, 'accounts/sort_words_result.html', context)


# ====================== ВИКТОРИНА (С ЛИМИТОМ) ======================

@login_required
def quiz(request):
    attempts_left = request.user.check_quiz_attempts()
    return render(request, 'accounts/quiz.html', {'attempts_left': attempts_left})


@login_required
def submit_quiz(request):
    if request.method == 'POST':
        user = request.user
        
        # Админ может играть без лимита
        if not user.is_admin:
            attempts_left = user.check_quiz_attempts()
            if attempts_left <= 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Күнделікті шектеуге жеттіңіз (3/3). Ертең қайтып келіңіз!'
                })

        score = int(request.POST.get('score', 0))
        
        # Модератор получает 1.5x награду, админ 2x
        if user.is_admin:
            earned = score * 20
        elif user.is_moderator:
            earned = score * 15
        else:
            earned = score * 10
            
        user.coins += earned
        user.quiz_attempts += 1
        user.last_quiz_date = timezone.now()
        user.save()

        return JsonResponse({
            'success': True,
            'earned': earned,
            'new_coins': user.coins,
            'score': score,
            'attempts_left': 3 - user.quiz_attempts if not user.is_admin else '∞'
        })
    return JsonResponse({'success': False})

@login_required
def buy_quiz_attempt(request):
    if request.method == 'POST':
        user = request.user
        
        # Админ может играть бесплатно
        if user.is_admin:
            if user.quiz_attempts > 0:
                user.quiz_attempts -= 1
            user.save()
            return JsonResponse({
                'success': True,
                'new_coins': user.coins,
                'message': 'Мүмкіндік сатып алынды!'
            })
        
        # Модератор со скидкой 50%
        cost = 15 if user.is_moderator else 30
        
        if user.coins >= cost:
            user.coins -= cost
            if user.quiz_attempts > 0:
                user.quiz_attempts -= 1
            user.save()
            return JsonResponse({
                'success': True,
                'new_coins': user.coins,
                'message': 'Мүмкіндік сатып алынды!'
            })
        return JsonResponse({'success': False, 'message': f'Монета жеткіліксіз ({cost} монета қажет)'})
    return JsonResponse({'success': False})


# ====================== МАГАЗИН ======================

@login_required
def buy_upgrade(request):
    if request.method == 'POST':
        item_type = request.POST.get('item_type')
        price = int(request.POST.get('price', 0))
        user = request.user

        # Админ получает все бесплатно
        if user.is_admin:
            discount_price = 0
        # Модератор со скидкой 50%
        elif user.is_moderator:
            discount_price = price // 2
        # Обычный пользователь - полная цена
        else:
            discount_price = price

        # Проверка монет (администратор может не платить)
        if not user.is_admin and user.coins < discount_price:
            return JsonResponse({'success': False, 'message': 'Недостаточно монет'})

        duration = datetime.timedelta(hours=24)
        expiry = timezone.now() + duration
        if item_type == 'goldBorder':
            user.gold_border_until = expiry
        elif item_type == 'verified':
            user.verified_until = expiry
        else:
            return JsonResponse({'success': False, 'message': 'Неверный тип улучшения'})

        # Вычитаем монеты только если не админ
        if not user.is_admin:
            user.coins -= discount_price
        
        user.save()
        return JsonResponse({
            'success': True, 
            'new_coins': user.coins,
            'message': 'Улучшение куплено!' if user.is_admin else f'Улучшение куплено за {discount_price} монет!'
        })
    return JsonResponse({'success': False})


@login_required
def disable_upgrade(request):
    if request.method == 'POST':
        upgrade_type = request.POST.get('upgrade_type')
        if upgrade_type == 'goldBorder':
            request.user.gold_border_until = None
        elif upgrade_type == 'verified':
            request.user.verified_until = None
        else:
            return JsonResponse({'success': False, 'message': 'Неверный тип улучшения'})
        request.user.save()
        return JsonResponse({'success': True, 'message': 'Улучшение отключено'})
    return JsonResponse({'success': False})


# ====================== СООБЩЕНИЯ И УВЕДОМЛЕНИЯ ======================

@login_required
def chat_detail(request, user_id):
    """Получить чат с определённым пользователем"""
    if user_id == 'bot':
        # Special bot chat
        class MockUser:
            id = 'bot'
            username = 'AI Bot'
            profile_picture = None
        other_user = MockUser()
        chat = None
        bot_messages = load_bot_history(request.user)
    else:
        other_user = get_object_or_404(CustomUser, id=user_id)

        # Найти или создать чат между пользователями
        chat = None
        for c in request.user.chats.all():
            if other_user in c.participants.all():
                chat = c
                break

        if not chat:
            chat = Chat.objects.create()
            chat.participants.add(request.user, other_user)

        # Отметить все сообщения как прочитанные для текущего пользователя
        chat.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    # Если запрос AJAX, вернуть JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if user_id == 'bot':
            messages_list = bot_messages
        elif chat:
            messages_list = chat.messages.all().values('id', 'sender__username', 'sender__id', 'content', 'is_read', 'created_at')
        else:
            messages_list = []

        return JsonResponse({
            'success': True,
            'chat_id': chat.id if chat else None,
            'other_user': {
                'id': other_user.id,
                'username': other_user.username,
                'profile_picture': other_user.profile_picture.url if other_user.profile_picture else '/static/default.jpg'
            },
            'messages': list(messages_list)
        })
    
    # Иначе отрендерить HTML страницу
    return render(request, 'accounts/chat_detail.html', {
        'other_user': other_user,
        'other_user_id': other_user.id,
        'chat': chat
    })


@login_required
def send_message(request, user_id):
    """Отправить сообщение пользователю"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)
    
    content = request.POST.get('content', '').strip()
    
    if not content:
        return JsonResponse({'success': False, 'message': 'Сообщение не может быть пустым'})
    
    if user_id == 'bot':
        bot_response = generate_bot_response(content, request.user)
        now_iso = datetime.datetime.now().isoformat()

        # Записываем историю в JSON
        messages_history = load_bot_history(request.user) or []
        messages_history.append({
            'sender__id': request.user.id,
            'content': content,
            'created_at': now_iso,
        })
        messages_history.append({
            'sender__id': 'bot',
            'content': bot_response,
            'created_at': datetime.datetime.now().isoformat(),
        })
        save_bot_history(request.user, messages_history)

        return JsonResponse({
            'success': True,
            'message': {
                'sender_id': 'bot',
                'content': bot_response,
                'created_at': datetime.datetime.now().isoformat()
            }
        })

    other_user = get_object_or_404(CustomUser, id=user_id)
    
    # Найти или создать чат
    chat = None
    for c in request.user.chats.all():
        if other_user in c.participants.all():
            chat = c
            break
    
    if not chat:
        chat = Chat.objects.create()
        chat.participants.add(request.user, other_user)
    
    # Создать сообщение
    message = Message.objects.create(
        chat=chat,
        sender=request.user,
        content=content
    )
    
    # Создать уведомление получателю
    Notification.objects.create(
        user=other_user,
        type='message',
        sender=request.user,
        title=f'Новое сообщение от @{request.user.username}',
        content=content[:100]
    )
    
    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'sender_id': message.sender.id,
            'content': message.content,
            'created_at': message.created_at.isoformat()
        }
    })


@login_required
def get_notifications(request):
    """Получить уведомления пользователя (JSON API)"""
    notifications = request.user.notifications.all()[:20]
    
    data = {
        'success': True,
        'notifications': [],
        'unread_count': request.user.notifications.filter(is_read=False).count()
    }
    
    for notif in notifications:
        data['notifications'].append({
            'id': notif.id,
            'type': notif.get_type_display(),
            'type_key': notif.type,
            'title': notif.title,
            'content': notif.content,
            'sender': notif.sender.username if notif.sender else 'Система',
            'sender_id': notif.sender.id if notif.sender else None,
            'is_read': notif.is_read,
            'created_at': notif.created_at.isoformat()
        })
    
    return JsonResponse(data)


@login_required
def notifications_page(request):
    """Страница списка уведомлений пользователя"""
    notifications = request.user.notifications.all().order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    return render(request, 'accounts/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })


@login_required
def mark_notification_as_read(request, notif_id):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, id=notif_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})


@admin_required
def send_system_warning(request, user_id):
    """Отправить системное предупреждение пользователю (только для админов)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Метод не поддерживается'}, status=405)
    
    user = get_object_or_404(CustomUser, id=user_id)
    title = request.POST.get('title', 'Системное предупреждение')
    content = request.POST.get('content', '')
    
    if not content:
        return JsonResponse({'success': False, 'message': 'Содержание не может быть пустым'})
    
    notification = Notification.objects.create(
        user=user,
        type='system_warning',
        sender=request.user,
        title=title,
        content=content
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Предупреждение отправлено пользователю {user.username}'
    })


def shop(request):
    return render(request, 'accounts/shop.html')


def reports(request):
    return render(request, 'accounts/reports.html')


# ============= АДМИНИСТРИРОВАНИЕ =============

@admin_required
def admin_dashboard(request):
    """Админ-панель для управления пользователями"""
    users = CustomUser.objects.all().order_by('-date_joined')

    # Статистика по ролям
    admin_count = users.filter(role='admin').count()
    moderator_count = users.filter(role='moderator').count()
    user_count = users.filter(role='user').count()

    # Статистика по улучшениям
    gold_border_count = users.filter(gold_border_until__gt=timezone.now()).count()
    verified_count = users.filter(verified_until__gt=timezone.now()).count()

    # Статистика по контенту
    total_posts = Post.objects.count()
    total_saved_posts = SavedPost.objects.count()
    total_hidden_posts = HiddenPost.objects.count()
    total_reports = PostReport.objects.count()

    # Статистика по перепискам и уведомлениям
    total_chats = Chat.objects.count()
    total_messages = Message.objects.count()
    unread_messages = Message.objects.filter(is_read=False).exclude(sender=request.user).count() if request.user.is_authenticated else 0
    total_notifications = Notification.objects.count()
    unread_notifications = Notification.objects.filter(is_read=False).count()

    # Помощная информация по каждому пользователю
    user_stats = []
    for user in users:
        user_stats.append({
            'user': user,
            'posts_count': Post.objects.filter(user=user).count(),
            'saved_count': SavedPost.objects.filter(user=user).count(),
            'hidden_count': HiddenPost.objects.filter(user=user).count(),
            'reports_count': PostReport.objects.filter(post__user=user).count(),
            'chats_count': Chat.objects.filter(participants=user).count(),
            'unread_notifications_count': Notification.objects.filter(user=user, is_read=False).count(),
            'unread_messages_count': Message.objects.filter(chat__participants=user, is_read=False).exclude(sender=user).count(),
        })

    recent_reports = PostReport.objects.select_related('reporter', 'post').order_by('-created_at')[:8]
    recent_chats = list(Chat.objects.prefetch_related('participants').order_by('-updated_at')[:6])
    for chat in recent_chats:
        # для админа/модератора показываем другого участника
        other = chat.get_other_user(request.user)
        if not other:
            other = chat.participants.first()
        chat.other_user = other
    recent_notifications = Notification.objects.select_related('user', 'sender').order_by('-created_at')[:8]

    return render(request, 'accounts/admin_dashboard.html', {
        'users': users,
        'user_stats': user_stats,
        'admin_count': admin_count,
        'moderator_count': moderator_count,
        'user_count': user_count,
        'gold_border_count': gold_border_count,
        'verified_count': verified_count,
        'total_posts': total_posts,
        'total_saved_posts': total_saved_posts,
        'total_hidden_posts': total_hidden_posts,
        'total_reports': total_reports,
        'total_chats': total_chats,
        'total_messages': total_messages,
        'unread_messages': unread_messages,
        'total_notifications': total_notifications,
        'unread_notifications': unread_notifications,
        'recent_reports': recent_reports,
        'recent_chats': recent_chats,
        'recent_notifications': recent_notifications,
    })


@admin_required
def change_user_role(request):
    """Изменить роль пользователя"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        
        if new_role not in ['user', 'moderator', 'admin']:
            return JsonResponse({'success': False, 'message': 'Неверная роль'})
        
        try:
            user = CustomUser.objects.get(id=user_id)
            user.role = new_role
            user.save()
            return JsonResponse({
                'success': True, 
                'message': f'Роль пользователя {user.username} изменена на {new_role}'
            })
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Пользователь не найден'})
    
    return JsonResponse({'success': False})


@admin_required
def delete_user(request):
    """Удалить пользователя (только админ)"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        
        try:
            user = CustomUser.objects.get(id=user_id)
            username = user.username
            user.delete()
            return JsonResponse({
                'success': True, 
                'message': f'Пользователь {username} удален'
            })
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Пользователь не найден'})
    
    return JsonResponse({'success': False})


@admin_required
def set_user_coins(request):
    """Установить количество монет пользователю"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        coins = int(request.POST.get('coins', 0))
        
        try:
            user = CustomUser.objects.get(id=user_id)
            user.coins = coins
            user.save()
            return JsonResponse({
                'success': True, 
                'message': f'Баланс пользователя {user.username} установлен на {coins} монет'
            })
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Пользователь не найден'})
    
    return JsonResponse({'success': False})