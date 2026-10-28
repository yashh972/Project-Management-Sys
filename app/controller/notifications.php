<?php

namespace Controller;

/**
 * In-app notification center.
 */
class Notifications extends \Controller
{
    public function __construct()
    {
        $this->_requireLogin();
    }

    /**
     * GET /notifications
     */
    public function index(\Base $f3): void
    {
        $userId = (int) $f3->get('user.id');
        $f3->set('title', 'Notifications');
        $f3->set('menuitem', 'notifications');
        $f3->set('notifications', \Model\Notification::recent($userId, 50));
        $this->_render('notifications/index.html');
    }

    /**
     * GET /notifications/count
     */
    public function count(\Base $f3): void
    {
        $this->_printJson([
            'count' => \Model\Notification::unreadCount((int) $f3->get('user.id')),
        ]);
    }

    /**
     * POST /notifications/read
     */
    public function read(\Base $f3): void
    {
        $this->validateCsrf();
        $userId = (int) $f3->get('user.id');
        if ($f3->get('POST.all')) {
            \Model\Notification::markAllRead($userId);
        } else {
            \Model\Notification::markRead((int) $f3->get('POST.id'), $userId);
        }

        if ($f3->get('AJAX') || $f3->get('POST.ajax')) {
            $this->_printJson([
                'ok' => true,
                'count' => \Model\Notification::unreadCount($userId),
            ]);
            return;
        }

        $f3->reroute('/notifications');
    }
}
