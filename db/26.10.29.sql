-- Allow modern bcrypt hashes (60 chars) in the user table (MySQL).
ALTER TABLE `user` MODIFY COLUMN `password` varchar(255) DEFAULT NULL;
ALTER TABLE `user` MODIFY COLUMN `salt` varchar(64) DEFAULT NULL;

UPDATE `config` SET `value` = '26.10.29' WHERE `attribute` = 'version';
