-- =====================================================================
-- 开罗论坛 · 自托管鉴权库 (ns_auth) —— 精简版
-- 说明：仅包含论坛前端实际依赖的表（用户、通知、访问记录）。
-- 执行方式：mysql -uroot -p < ns_auth.sql
-- 默认超管账号：admin / 123456（登录后请立即修改密码）
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `ns_auth` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `ns_auth`;

-- ---------------------------------------------------------------------
-- 1. 用户
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `ns_user`;
CREATE TABLE `ns_user` (
  `id`          BIGINT       NOT NULL AUTO_INCREMENT,
  `name`        VARCHAR(50)  DEFAULT NULL,
  `password`    VARCHAR(64)  DEFAULT NULL,
  `salt`        VARCHAR(32)  DEFAULT NULL,
  `gender`      TINYINT      DEFAULT NULL,
  `birthday`    VARCHAR(20)  DEFAULT NULL,
  `phone`       VARCHAR(20)  DEFAULT NULL,
  `email`       VARCHAR(100) DEFAULT NULL,
  `picture`     VARCHAR(500) DEFAULT NULL,
  `position`    VARCHAR(100) DEFAULT NULL,
  `company`     VARCHAR(100) DEFAULT NULL,
  `home_page`   VARCHAR(200) DEFAULT NULL,
  `intro`       VARCHAR(500) DEFAULT NULL,
  `org_id`      INT          DEFAULT NULL,
  `state`       TINYINT(1)   DEFAULT 1,
  `auth_id`     VARCHAR(100) DEFAULT NULL,
  `auth_source` VARCHAR(50)  DEFAULT NULL,
  `is_admin`    TINYINT(1)   DEFAULT 0,
  `create_time` DATETIME     DEFAULT NULL,
  `update_time` DATETIME     DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_name` (`name`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------------
-- 2. 通知
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `ns_notify`;
CREATE TABLE `ns_notify` (
  `id`         INT          NOT NULL AUTO_INCREMENT,
  `project_id` INT          DEFAULT NULL,
  `message`    VARCHAR(1000) DEFAULT NULL,
  `type`       TINYINT      DEFAULT NULL,
  `is_deleted` TINYINT(1)   DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------------
-- 3. 用户通知（已读状态）
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `ns_notify_user`;
CREATE TABLE `ns_notify_user` (
  `id`          INT      NOT NULL AUTO_INCREMENT,
  `type`        TINYINT  DEFAULT NULL,
  `notify_id`   INT      DEFAULT NULL,
  `user_id`     BIGINT   DEFAULT NULL,
  `is_read`     TINYINT(1) DEFAULT 0,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  `create_user` BIGINT   DEFAULT NULL,
  `update_user` BIGINT   DEFAULT NULL,
  `create_time` DATETIME DEFAULT NULL,
  `update_time` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- ---------------------------------------------------------------------
-- 4. 访问记录
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS `ns_visit`;
CREATE TABLE `ns_visit` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `project_id`  INT          DEFAULT NULL,
  `ip`          VARCHAR(50)  DEFAULT NULL,
  `country`     VARCHAR(50)  DEFAULT NULL,
  `province`    VARCHAR(50)  DEFAULT NULL,
  `city`        VARCHAR(50)  DEFAULT NULL,
  `host_name`   VARCHAR(100) DEFAULT NULL,
  `os`          VARCHAR(50)  DEFAULT NULL,
  `count`       INT          DEFAULT 1,
  `day`         VARCHAR(20)  DEFAULT NULL,
  `title`       VARCHAR(50)  DEFAULT NULL,
  `create_time` DATETIME     DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_ip` (`ip`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- =====================================================================
-- 种子数据
-- =====================================================================

-- 超管用户：admin / 123456（is_admin = 1）
-- password = SHA256(salt + 明文) = SHA256('a1b2c3d4e5f6a7b8' + '123456')
INSERT INTO `ns_user` (`id`, `name`, `password`, `salt`, `gender`, `state`, `org_id`, `is_admin`, `create_time`, `update_time`) VALUES
(1, 'admin', '5514b67fb72216fdd5de7666303225b8f0ac1e9c88612247a169042f329e25bf', 'a1b2c3d4e5f6a7b8', 0, 1, 1, 1, NOW(), NOW());
