self.addEventListener('push', function(event) {
    var data = {title: 'REP12', body: 'Новое уведомление'};
    try { data = event.data.json(); } catch(e) {}
    event.waitUntil(
        self.registration.showNotification(data.title || 'REP12', {
            body: data.body || '',
            icon: '/static/images/icon-192.png',
            badge: '/static/images/icon-192.png',
            data: {url: data.url || '/dashboard'}
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    var url = event.notification.data && event.notification.data.url || '/dashboard';
    event.waitUntil(clients.openWindow(url));
});
