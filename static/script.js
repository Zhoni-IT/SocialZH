const recommendationsData = [
    { title: "Tech Trends", img: "https://picsum.photos/seed/1/200/300" },
    { title: "Design Life", img: "https://picsum.photos/seed/2/200/300" },
    { title: "Lifestyle", img: "https://picsum.photos/seed/3/200/300" },
    { title: "Coding", img: "https://picsum.photos/seed/4/200/300" },
    { title: "Almaty Art", img: "https://picsum.photos/seed/5/200/300" }
];

function renderCarousel() {
    const carouselContainer = document.getElementById('recommendations-carousel');
    if (!carouselContainer) return;

    // Очищаем и наполняем
    carouselContainer.innerHTML = ''; 
    recommendationsData.forEach(item => {
        const card = document.createElement('div');
        card.className = 'carousel-item';
        card.style.backgroundImage = `url('${item.img}')`;
        card.innerHTML = `
            <div style="background: linear-gradient(transparent, rgba(0,0,0,0.7)); color: white; width: 100%; padding: 8px; font-size: 11px; font-weight: 500; align-self: flex-end;">
                ${item.title}
            </div>
        `;
        carouselContainer.appendChild(card);
    });

    // --- ЛОГИКА АВТО-ДВИЖЕНИЯ ---
    let scrollAmount = 0;
    let direction = 1; // 1 - вправо, -1 - влево
    const speed = 0.5;   // Скорость (чем меньше, тем плавнее)

    function autoScroll() {
        const maxScroll = carouselContainer.scrollWidth - carouselContainer.clientWidth;
        
        // Меняем направление, если дошли до краев
        if (carouselContainer.scrollLeft >= maxScroll - 1) {
            direction = -1;
        } else if (carouselContainer.scrollLeft <= 0) {
            direction = 1;
        }

        carouselContainer.scrollLeft += direction * speed;
    }

    // Запускаем интервал (каждые 30 мс)
    let moveInterval = setInterval(autoScroll, 30);

    // Остановка при касании (HUI UX: пользователь хочет сам покрутить)
    carouselContainer.addEventListener('touchstart', () => clearInterval(moveInterval));
    carouselContainer.addEventListener('mousedown', () => clearInterval(moveInterval));
}

// Функция для переключения видимости меню
function toggleMenu() {
    const menu = document.getElementById('dropdown-menu');
    // Переключаем класс hidden
    if (menu.classList.contains('hidden')) {
        menu.classList.remove('hidden');
    } else {
        menu.classList.add('hidden');
    }
}

// Отслеживание кликов и глобальное делегирование
// (Сразу включает действия постов и закрытие меню по клику вне)
document.addEventListener('click', function(event) {
    console.log("Клик по координатам: ", event.clientX, event.clientY);

    const btnDelete = event.target.closest('.post-delete-btn');
    if (btnDelete) {
        const postId = btnDelete.dataset.postid;
        deletePostAction(postId);
        return;
    }

    const btnSave = event.target.closest('.post-save-btn');
    if (btnSave) {
        const postId = btnSave.dataset.postid;
        toggleSavePost(postId);
        return;
    }

    const btnReport = event.target.closest('.post-report-btn');
    if (btnReport) {
        const postId = btnReport.dataset.postid;
        reportPost(postId);
        return;
    }

    const btnHide = event.target.closest('.post-hide-btn');
    if (btnHide) {
        const postId = btnHide.dataset.postid;
        hidePost(postId);
        return;
    }

    const btnCopy = event.target.closest('.post-copy-btn');
    if (btnCopy) {
        const postId = btnCopy.dataset.postid;
        copyPostLink(postId);
        return;
    }

    // Меню отбросить, если клик вне post-options/btn-меню
    document.querySelectorAll('.post-options.show').forEach(el => {
        const triggerButton = el.previousElementSibling; // post-menu-btn
        if (triggerButton && !el.contains(event.target) && !triggerButton.contains(event.target)) {
            el.classList.remove('show');
        }
    });
});

function togglePostOptions(postId) {
    const current = document.getElementById('post-options-' + postId);
    if (!current) return;

    document.querySelectorAll('.post-options').forEach(el => {
        if (el !== current) el.classList.remove('show');
    });
    current.classList.toggle('show');
}

function notify(message) {
    const toast = document.getElementById('global-toast');
    if (toast) {
        toast.textContent = message;
        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 1800);
    } else {
        alert(message);
    }
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    }

    const themeItemIcon = document.querySelector('#theme-toggle-item .icon');
    if (themeItemIcon) {
        themeItemIcon.textContent = theme === 'dark' ? '🌙' : '🎨';
    }
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme');
    const defaultTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    setTheme(savedTheme || defaultTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    setTheme(current === 'dark' ? 'light' : 'dark');
}

window.toggleTheme = toggleTheme;
window.setTheme = setTheme;
window.loadTheme = loadTheme;

function getCSRFToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || document.getElementById('csrfToken')?.value;
}

function deletePostAction(postId) {
    if (!confirm('Вы точно хотите удалить этот пост?')) return;
    fetch(`/post/${postId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Accept': 'application/json'
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            notify(data.message);
            location.reload();
        } else {
            notify(data.message);
        }
    });
}

function reportPost(postId) {
    const reason = prompt('Почему вы хотите пожаловаться на этот пост?', 'Неприемлемый контент');
    if (reason === null) return;

    const formData = new FormData();
    formData.append('reason', reason);

    fetch(`/post/${postId}/report/`, {
        method: 'POST',
        body: formData,
        headers: {'X-CSRFToken': getCSRFToken()}
    })
    .then(r => r.json())
    .then(data => notify(data.message));
}

function hidePost(postId) {
    fetch(`/post/${postId}/hide/`, {
        method: 'POST',
        headers: {'X-CSRFToken': getCSRFToken()}
    })
    .then(r => r.json())
    .then(data => {
        notify(data.message);
        if (data.success) location.reload();
    });
}

function copyPostLink(postId) {
    const link = `${window.location.origin}/feed/?post=${postId}`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(link)
            .then(() => notify('Ссылка скопирована'))
            .catch(() => notify('Не удалось скопировать ссылку'));
    } else {
        const textarea = document.createElement('textarea');
        textarea.value = link;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            notify('Ссылка скопирована');
        } catch (err) {
            notify('Не удалось скопировать ссылку');
        }
        document.body.removeChild(textarea);
    }
}

function toggleSavePost(postId) {
    fetch(`/post/${postId}/save/`, {
        method: 'POST',
        headers: {'X-CSRFToken': getCSRFToken()}
    })
    .then(r => r.json())
    .then(data => notify(data.message));
}

function refreshNotificationBadge() {
    const badge = document.getElementById('notifBadge');
    if (!badge) return;

    fetch('/notifications/', {
        method: 'GET',
        headers: {'Accept': 'application/json'}
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const count = data.unread_count || 0;
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = count > 0 ? 'inline-flex' : 'none';
        }
    })
    .catch(() => {
        // пока без критики
    });
}

// Вызываем сразу после загрузки страницы, чтобы показать кол-во непрочитанных уведомлений
document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    renderCarousel();
    refreshNotificationBadge();
    const themeButton = document.getElementById('theme-toggle');
    if (themeButton) {
        themeButton.addEventListener('click', function(event) {
            event.preventDefault();
            toggleTheme();
        });
    }
    const themeItem = document.getElementById('theme-toggle-item');
    if (themeItem) {
        themeItem.addEventListener('click', function(event) {
            event.preventDefault();
            toggleTheme();
        });
    }
});

// Добавляем эффект при наведении на важные зоны (визуальная обратная связь)
const posts = document.querySelectorAll('.post-card');
posts.forEach(post => {
    post.addEventListener('mouseenter', () => {
        post.style.backgroundColor = 'rgba(255, 255, 255, 0.08)';
    });
    post.addEventListener('mouseleave', () => {
        post.style.backgroundColor = '';
    });
});

function logout() {
    // 1. Очищаем сохраненные данные
    localStorage.removeItem('userFirstName');
    localStorage.removeItem('userLastName');
    
    // 2. Возвращаемся на главную страницу входа
    window.location.href = 'index.html';
}