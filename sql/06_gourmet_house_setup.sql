-- ============================================================
-- Gourmet_House 数据库补全脚本
-- 1. 重建触发器
-- 2. v2 schema 增量更新
-- 3. 重建视图
-- ============================================================
USE Gourmet_House;

-- ============================================================
-- 1. 重建触发器
-- ============================================================
DROP TRIGGER IF EXISTS trg_ingredients_updated_at;
DROP TRIGGER IF EXISTS trg_prefs_updated_at;

DELIMITER //
CREATE TRIGGER trg_ingredients_updated_at BEFORE UPDATE ON ingredients FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
CREATE TRIGGER trg_prefs_updated_at BEFORE UPDATE ON user_preferences FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;

-- ============================================================
-- 2. v2 Schema 增量更新
-- ============================================================

-- 删除旧 CHECK 约束 (兼容新 PRD 的 8 种口味)
ALTER TABLE user_preferences DROP CHECK user_preferences_chk_1;
ALTER TABLE user_preferences DROP CHECK user_preferences_chk_2;
ALTER TABLE user_preferences DROP CHECK user_preferences_chk_3;

-- user_preferences 增列: 口味权重JSON
ALTER TABLE user_preferences
    ADD COLUMN taste_weights JSON NOT NULL DEFAULT (JSON_OBJECT()) AFTER taste_preference;

-- 放宽 taste_preference 约束
ALTER TABLE user_preferences
    MODIFY COLUMN taste_preference VARCHAR(10) NOT NULL DEFAULT '不挑';

-- cook_records 增列: 评分rating
ALTER TABLE cook_records
    ADD COLUMN rating TINYINT NULL CHECK (rating >= 1 AND rating <= 3) AFTER mood;

-- 放宽 mood 约束
ALTER TABLE cook_records
    MODIFY COLUMN mood VARCHAR(10) NOT NULL DEFAULT '平淡';

-- ============================================================
-- 3. 偏好权重历史表
-- ============================================================
CREATE TABLE IF NOT EXISTS preference_weights (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    dimension       VARCHAR(20)  NOT NULL,
    weight          DECIMAL(4,3) NOT NULL DEFAULT 0.500 CHECK (weight >= 0 AND weight <= 1),
    feedback_count  INT          NOT NULL DEFAULT 0,
    last_feedback   VARCHAR(10)  NOT NULL DEFAULT '',
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, dimension)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 4. 菜谱缓存表
-- ============================================================
CREATE TABLE IF NOT EXISTS recipe_cache (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    prompt_hash     VARCHAR(64)  NOT NULL,
    recipes_json    JSON         NOT NULL,
    model           VARCHAR(50)  NOT NULL DEFAULT 'deepseek-chat',
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    expires_at      DATETIME     NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_hash_user (prompt_hash, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 5. 对话会话表
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    mood            VARCHAR(10)  NOT NULL DEFAULT '',
    current_round   INT          NOT NULL DEFAULT 1,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active',
    context_json    JSON         NULL,
    final_recommend VARCHAR(200) NULL,
    recommend_reason TEXT        NULL,
    alternatives_json JSON       NULL,
    takeout_id      VARCHAR(36)  NULL,
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. 视图: 偏好权重
-- ============================================================
CREATE OR REPLACE VIEW v_user_preference_weights AS
SELECT
    pw.user_id,
    pw.dimension,
    pw.weight,
    pw.feedback_count,
    pw.last_feedback,
    pw.updated_at
FROM preference_weights pw;

-- ============================================================
-- 7. 视图: 月度统计
-- ============================================================
CREATE OR REPLACE VIEW v_monthly_stats AS
SELECT
    u.id AS user_id,
    COUNT(DISTINCT cr.id) AS cook_count,
    COUNT(DISTINCT tr.id) AS takeout_count,
    COALESCE(SUM(cr.estimated_cost), 0) AS total_cook_cost,
    COALESCE(AVG(cr.rating), 0) AS avg_cook_rating
FROM users u
LEFT JOIN cook_records cr ON cr.user_id = u.id AND cr.created_at >= DATE_FORMAT(NOW(), '%Y-%m-01')
LEFT JOIN takeout_records tr ON tr.user_id = u.id AND tr.created_at >= DATE_FORMAT(NOW(), '%Y-%m-01')
GROUP BY u.id;
