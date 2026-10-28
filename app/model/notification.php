<?php

namespace Model;

/**
 * In-app notifications generated from issue updates.
 *
 * Notifications are intentionally best-effort: a missing migration or a
 * notification write failure must never break the issue save itself.
 */
class Notification extends \Model
{
    protected $_table_name = 'notification';

    public static function unreadCount(int $userId): int
    {
        if ($userId <= 0) {
            return 0;
        }

        try {
            $rows = \Base::instance()->get('db.instance')->exec(
                'SELECT COUNT(*) AS count FROM notification WHERE user_id = ? AND read_date IS NULL',
                [$userId]
            );
            return (int) ($rows[0]['count'] ?? 0);
        } catch (\Throwable $e) {
            return 0;
        }
    }

    /**
     * @return array<int,array>
     */
    public static function recent(int $userId, int $limit = 30): array
    {
        if ($userId <= 0) {
            return [];
        }

        try {
            return \Base::instance()->get('db.instance')->exec(
                'SELECT n.*, u.name AS actor_name, u.username AS actor_username
                 FROM notification n
                 LEFT JOIN user u ON u.id = n.actor_id
                 WHERE n.user_id = ?
                 ORDER BY n.created_date DESC, n.id DESC
                 LIMIT ' . max(1, min(100, $limit)),
                [$userId]
            );
        } catch (\Throwable $e) {
            return [];
        }
    }

    public static function markAllRead(int $userId): void
    {
        try {
            \Base::instance()->get('db.instance')->exec(
                'UPDATE notification SET read_date = ? WHERE user_id = ? AND read_date IS NULL',
                [date('Y-m-d H:i:s'), $userId]
            );
        } catch (\Throwable $e) {
            // best-effort
        }
    }

    public static function markRead(int $id, int $userId): void
    {
        try {
            \Base::instance()->get('db.instance')->exec(
                'UPDATE notification SET read_date = ? WHERE id = ? AND user_id = ? AND read_date IS NULL',
                [date('Y-m-d H:i:s'), $id, $userId]
            );
        } catch (\Throwable $e) {
            // best-effort
        }
    }

    /**
     * Create notifications for watchers and the new owner of an updated issue.
     *
     * @param array<string,array{old:mixed,new:mixed}> $changes
     */
    public static function issueUpdate(
        Issue $issue,
        Issue\Update $update,
        array $changes,
        int $actorId,
        bool $isComment = false
    ): void {
        $f3 = \Base::instance();
        $db = $f3->get('db.instance');

        try {
            $recipients = [];
            foreach ($db->exec('SELECT user_id FROM issue_watcher WHERE issue_id = ?', [(int) $issue->id]) as $row) {
                $recipients[] = (int) $row['user_id'];
            }
            if ($issue->owner_id) {
                $recipients[] = (int) $issue->owner_id;
            }
            if ($issue->author_id) {
                $recipients[] = (int) $issue->author_id;
            }
            $recipients = array_values(array_unique(array_filter(
                $recipients,
                fn ($id) => $id > 0 && $id !== $actorId
            )));
            if ($recipients === []) {
                return;
            }

            $actor = $f3->get('user.name') ?: 'Someone';
            $summary = $isComment ? 'commented' : self::summarize($changes);
            $message = sprintf('%s %s on #%d %s', $actor, $summary, (int) $issue->id, $issue->name);
            if (strlen($message) > 250) {
                $message = substr($message, 0, 247) . '...';
            }

            $url = '/issues/' . (int) $issue->id;
            $created = date('Y-m-d H:i:s');
            foreach ($recipients as $userId) {
                $db->exec(
                    'INSERT INTO notification
                        (user_id, actor_id, issue_id, kind, message, url, created_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [
                        $userId,
                        $actorId ?: null,
                        (int) $issue->id,
                        $isComment ? 'comment' : 'issue',
                        $message,
                        $url,
                        $created,
                    ]
                );
            }
        } catch (\Throwable $e) {
            // Notifications are best-effort and must not break issue saves.
        }
    }

    /**
     * Create notifications for a new comment on an issue.
     */
    public static function issueComment(Issue\Comment $comment): void
    {
        $f3 = \Base::instance();
        $db = $f3->get('db.instance');

        try {
            $issue = new Issue();
            $issue->load((int) $comment->issue_id);
            if (!$issue->id) {
                return;
            }

            $recipients = [];
            foreach ($db->exec('SELECT user_id FROM issue_watcher WHERE issue_id = ?', [(int) $issue->id]) as $row) {
                $recipients[] = (int) $row['user_id'];
            }
            if ($issue->owner_id) {
                $recipients[] = (int) $issue->owner_id;
            }
            if ($issue->author_id) {
                $recipients[] = (int) $issue->author_id;
            }
            $actorId = (int) $comment->user_id;
            $recipients = array_values(array_unique(array_filter(
                $recipients,
                fn ($id) => $id > 0 && $id !== $actorId
            )));
            if ($recipients === []) {
                return;
            }

            $actor = $f3->get('user.name') ?: 'Someone';
            $message = sprintf('%s commented on #%d %s', $actor, (int) $issue->id, $issue->name);
            if (strlen($message) > 250) {
                $message = substr($message, 0, 247) . '...';
            }

            foreach ($recipients as $userId) {
                $db->exec(
                    'INSERT INTO notification
                        (user_id, actor_id, issue_id, kind, message, url, created_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [
                        $userId,
                        $actorId ?: null,
                        (int) $issue->id,
                        'comment',
                        $message,
                        '/issues/' . (int) $issue->id,
                        date('Y-m-d H:i:s'),
                    ]
                );
            }
        } catch (\Throwable $e) {
            // best-effort
        }
    }

    /**
     * @param array<string,array{old:mixed,new:mixed}> $changes
     */
    protected static function summarize(array $changes): string
    {
        $labels = [
            'status' => 'status',
            'owner_id' => 'owner',
            'due_date' => 'due date',
            'priority' => 'priority',
            'name' => 'title',
            'description' => 'description',
            'sprint_id' => 'sprint',
        ];
        $parts = [];
        foreach ($changes as $field => $change) {
            if (isset($labels[$field])) {
                $parts[] = $labels[$field];
            }
            if (count($parts) >= 3) {
                break;
            }
        }

        if ($parts === []) {
            return 'updated';
        }

        return 'updated ' . implode(', ', array_unique($parts));
    }
}
