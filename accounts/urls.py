from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('feed/', views.feed, name='feed'),
    path('search/', views.search, name='search'),
    path('messages/', views.messages, name='messages'),
    path('profile/', views.profile, name='profile'),
    path('profile/<str:username>/', views.profile_view, name='profile_view'),  # Новое
    path('logout/', views.logout_view, name='logout'),
    path('shop/', views.shop, name='shop'),
    path('add/', views.add, name='add'),
    path('update-coins/', views.update_coins, name='update_coins'),
    path('generate-password/', views.password_generator, name='password_generator'),
    path('check-password/', views.password_check, name='password_check'),
    path('sort-words/', views.sort_words, name='sort_words'),
    path('quiz/', views.quiz, name='quiz'),
    path('submit-quiz/', views.submit_quiz, name='submit_quiz'),
    path('buy-upgrade/', views.buy_upgrade, name='buy_upgrade'),
    path('disable-upgrade/', views.disable_upgrade, name='disable_upgrade'),
    path('reports/', views.reports, name='reports'),
    path('buy-quiz-attempt/', views.buy_quiz_attempt, name='buy_quiz_attempt'),

    path('post/<int:post_id>/', views.post_detail, name='post_detail'),

    # Посты (фича меню)
    path('post/<int:post_id>/save/', views.save_post, name='save_post'),
    path('post/<int:post_id>/hide/', views.hide_post, name='hide_post'),
    path('post/<int:post_id>/report/', views.report_post, name='report_post'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),

    # Подписки
    path('follow/<str:username>/', views.follow_toggle, name='follow_toggle'),
    path('followers/<str:username>/', views.followers_list, name='followers_list'),

    # Сообщения и уведомления
    path('messages/chat/<str:user_id>/', views.chat_detail, name='chat_detail'),
    path('messages/send/<str:user_id>/', views.send_message, name='send_message'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/view/', views.notifications_page, name='notifications_page'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_as_read, name='mark_notif_read'),
    path('admin-dashboard/send-warning/<int:user_id>/', views.send_system_warning, name='send_system_warning'),

    # Админ-панель
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/change-role/', views.change_user_role, name='change_user_role'),
    path('admin/delete-user/', views.delete_user, name='delete_user'),
    path('admin/set-coins/', views.set_user_coins, name='set_user_coins'),
]