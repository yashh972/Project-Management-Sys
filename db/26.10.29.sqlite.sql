-- SQLite does not enforce the old CHAR(40) width, but keep the version in sync.
UPDATE config SET value = '26.10.29' WHERE attribute = 'version';
