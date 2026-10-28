-- In-app notification center (MySQL)
CREATE TABLE IF NOT EXISTS `notification` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `actor_id` int unsigned DEFAULT NULL,
  `issue_id` int unsigned DEFAULT NULL,
  `kind` varchar(32) NOT NULL DEFAULT 'issue',
  `message` varchar(255) NOT NULL,
  `url` varchar(255) DEFAULT NULL,
  `created_date` datetime NOT NULL,
  `read_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `notification_user_unread` (`user_id`, `read_date`, `created_date`),
  KEY `notification_issue` (`issue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

UPDATE `config` SET `value` = '26.10.30' WHERE `attribute` = 'version';
