-- Phase 0 intelligence-layer tables (MySQL)
-- Applied once by Helper\Security::updateDatabase().

CREATE TABLE IF NOT EXISTS `model_run` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `model_name` varchar(64) NOT NULL,
  `version` varchar(64) NOT NULL,
  `trained_at` datetime NOT NULL,
  `train_start` date DEFAULT NULL,
  `train_end` date DEFAULT NULL,
  `rows_count` int unsigned NOT NULL DEFAULT 0,
  `metrics_json` text DEFAULT NULL,
  `artifact_path` varchar(255) DEFAULT NULL,
  `dataset_hash` varchar(64) DEFAULT NULL,
  `is_active` tinyint unsigned NOT NULL DEFAULT 1,
  `created_by` int unsigned DEFAULT NULL,
  `created_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `model_run_name_active` (`model_name`, `is_active`),
  KEY `model_run_trained` (`trained_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `prediction` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `issue_id` int unsigned NOT NULL,
  `kind` varchar(16) NOT NULL,
  `model_run_id` int unsigned DEFAULT NULL,
  `value` double DEFAULT NULL,
  `p50` double DEFAULT NULL,
  `p85` double DEFAULT NULL,
  `explanation_json` text DEFAULT NULL,
  `features_json` text DEFAULT NULL,
  `features_hash` varchar(40) DEFAULT NULL,
  `computed_at` datetime NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `prediction_issue_kind` (`issue_id`, `kind`, `computed_at`),
  KEY `prediction_model` (`model_run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `suggestion_log` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned DEFAULT NULL,
  `issue_id` int unsigned DEFAULT NULL,
  `kind` varchar(32) NOT NULL,
  `payload_json` text DEFAULT NULL,
  `model_run_id` int unsigned DEFAULT NULL,
  `shown_at` datetime NOT NULL,
  `action` varchar(16) DEFAULT NULL,
  `acted_at` datetime DEFAULT NULL,
  `outcome_json` text DEFAULT NULL,
  `outcome_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `suggestion_issue` (`issue_id`, `shown_at`),
  KEY `suggestion_user` (`user_id`, `shown_at`),
  KEY `suggestion_action` (`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `forecast_run` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `sprint_id` int unsigned NOT NULL,
  `created_by` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `simulations` int unsigned NOT NULL DEFAULT 0,
  `assumptions_json` text DEFAULT NULL,
  `probability_on_time` double DEFAULT NULL,
  `p50_date` date DEFAULT NULL,
  `p85_date` date DEFAULT NULL,
  `p95_date` date DEFAULT NULL,
  `expected_days` double DEFAULT NULL,
  `drivers_json` text DEFAULT NULL,
  `model_run_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `forecast_sprint` (`sprint_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assignment_run` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `sprint_id` int unsigned DEFAULT NULL,
  `issue_id` int unsigned DEFAULT NULL,
  `created_by` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `objective` varchar(64) DEFAULT NULL,
  `constraints_json` text DEFAULT NULL,
  `result_json` text DEFAULT NULL,
  `baseline_json` text DEFAULT NULL,
  `model_run_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `assignment_sprint` (`sprint_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `assignment_item` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `run_id` int unsigned NOT NULL,
  `issue_id` int unsigned NOT NULL,
  `user_id` int unsigned DEFAULT NULL,
  `score` double DEFAULT NULL,
  `reason_json` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `assignment_item_run` (`run_id`),
  KEY `assignment_item_issue` (`issue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_skill` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `skill` varchar(64) NOT NULL,
  `level` tinyint unsigned NOT NULL DEFAULT 3,
  `created_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_skill_unique` (`user_id`, `skill`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_availability` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `date` date NOT NULL,
  `hours` double NOT NULL DEFAULT 0,
  `kind` varchar(16) NOT NULL DEFAULT 'leave',
  `note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_availability_unique` (`user_id`, `date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `holiday` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `holiday_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `git_installation` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `provider` varchar(16) NOT NULL,
  `installation_id` varchar(64) NOT NULL,
  `account` varchar(128) DEFAULT NULL,
  `token_enc` text DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `git_installation_unique` (`provider`, `installation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `issue_link` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `issue_id` int unsigned NOT NULL,
  `provider` varchar(16) NOT NULL,
  `repo` varchar(255) NOT NULL,
  `kind` varchar(32) NOT NULL,
  `external_id` varchar(64) NOT NULL,
  `url` varchar(512) DEFAULT NULL,
  `state` varchar(32) DEFAULT NULL,
  `meta_json` text DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `issue_link_unique` (`provider`, `kind`, `external_id`),
  KEY `issue_link_issue` (`issue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `dora_event` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `repo` varchar(255) NOT NULL,
  `kind` varchar(32) NOT NULL,
  `external_id` varchar(64) NOT NULL,
  `occurred_at` datetime NOT NULL,
  `value` double DEFAULT NULL,
  `meta_json` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dora_event_unique` (`repo`, `kind`, `external_id`),
  KEY `dora_event_time` (`occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `audit_log` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `workspace_id` int unsigned DEFAULT NULL,
  `actor_id` int unsigned DEFAULT NULL,
  `action` varchar(64) NOT NULL,
  `entity` varchar(64) NOT NULL,
  `entity_id` varchar(64) DEFAULT NULL,
  `before_json` text DEFAULT NULL,
  `after_json` text DEFAULT NULL,
  `ip` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `hash_prev` char(64) DEFAULT NULL,
  `hash` char(64) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `audit_created` (`created_at`),
  KEY `audit_entity` (`entity`, `entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `job` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `queue` varchar(32) NOT NULL DEFAULT 'default',
  `payload_json` text NOT NULL,
  `status` varchar(16) NOT NULL DEFAULT 'queued',
  `attempts` int unsigned NOT NULL DEFAULT 0,
  `available_at` datetime NOT NULL,
  `locked_at` datetime DEFAULT NULL,
  `error` text DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `job_queue_status` (`queue`, `status`, `available_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `event_outbox` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `type` varchar(64) NOT NULL,
  `payload_json` text NOT NULL,
  `created_at` datetime NOT NULL,
  `published_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `event_outbox_pending` (`published_at`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `issue`
  ADD COLUMN `version` int unsigned NOT NULL DEFAULT 1;

CREATE INDEX `issue_status_owner` ON `issue` (`status`, `owner_id`);
CREATE INDEX `issue_sprint_status` ON `issue` (`sprint_id`, `status`);
CREATE INDEX `issue_due_status` ON `issue` (`due_date`, `status`);

UPDATE `config` SET `value` = '26.10.28' WHERE `attribute` = 'version';
