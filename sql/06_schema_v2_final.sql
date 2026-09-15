-- ============================================================
-- 美味出租屋 (MeiWeiChuZuWu) — MySQL 完整建表脚本 v2
-- 版本：v2.0 | 日期：2026-08-17
-- 说明：一次性建表，包含所有 v2 特性（偏好权重/菜谱缓存/对话会话/口味权重）
-- 兼容：MySQL 8.0.16+ (需支持 CHECK 约束和 JSON 函数)
-- 用法：直接执行本脚本即可完成全量建表，无需先跑 01/05
-- ============================================================

CREATE DATABASE IF NOT EXISTS meiweichuzuwu
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE meiweichuzuwu;

-- 清理旧表（按依赖顺序删除，避免外键冲突）
DROP TABLE IF EXISTS chat_turns;
DROP TABLE IF EXISTS chat_sessions;
DROP TABLE IF EXISTS recipe_cache;
DROP TABLE IF EXISTS preference_weights;
DROP TABLE IF EXISTS shopping_items;
DROP TABLE IF EXISTS daily_fortunes;
DROP TABLE IF EXISTS takeout_records;
DROP TABLE IF EXISTS cook_records;
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS user_preferences;
DROP TABLE IF EXISTS users;

-- ============================================================
-- 1. 用户表
-- ============================================================
CREATE TABLE users (
    id                  VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    device_id           VARCHAR(64)  NULL,
    nickname            VARCHAR(50)  NOT NULL DEFAULT '',
    avatar_url          VARCHAR(500) NULL,
    created_at          DATETIME     NOT NULL DEFAULT (NOW()),
    last_active_at      DATETIME     NULL,
    total_cook_count    INT          NOT NULL DEFAULT 0,
    total_takeout_count INT          NOT NULL DEFAULT 0,
    streak_days         INT          NOT NULL DEFAULT 0
) COMMENT '用户表';

-- ============================================================
-- 2. 用户偏好表（1:1 关联 users）
-- ============================================================
CREATE TABLE user_preferences (
    id                           VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id                      VARCHAR(36)  UNIQUE NOT NULL,
    -- 基础信息
    zodiac                       VARCHAR(10)  NOT NULL DEFAULT '',
    mbti                         VARCHAR(4)   NOT NULL DEFAULT '',
    chinese_zodiac               VARCHAR(5)   NOT NULL DEFAULT '',
    -- 做饭偏好
    taste_preference             VARCHAR(10)  NOT NULL DEFAULT '不挑',
    taste_weights                JSON         NOT NULL DEFAULT (JSON_OBJECT())
        COMMENT '口味维度权重JSON, 如{"辣":0.72,"甜":0.30}',
    budget_level                 VARCHAR(10)  NOT NULL DEFAULT '正常',
    cooking_skill                VARCHAR(10)  NOT NULL DEFAULT '一般',
    cookware                     JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    disliked_ingredients         JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    liked_dishes                 JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    -- 外卖偏好
    liked_takeout_categories     JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    disliked_takeout_categories  JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    -- 元数据
    created_at                   DATETIME     NOT NULL DEFAULT (NOW()),
    updated_at                   DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '用户偏好表，双方向推荐引擎的核心数据源';

CREATE INDEX idx_prefs_user_id ON user_preferences(user_id);

DELIMITER //
CREATE TRIGGER trg_prefs_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;

-- ============================================================
-- 3. 食材库存表
-- ============================================================
CREATE TABLE ingredients (
    id          VARCHAR(36)   PRIMARY KEY DEFAULT (UUID()),
    user_id     VARCHAR(36)   NOT NULL,
    name        VARCHAR(50)   NOT NULL COMMENT '食材中文常用名',
    category    VARCHAR(10)   NOT NULL COMMENT '品类：蔬菜|肉蛋|水产|主食|调料|乳制品|其他',
    quantity    VARCHAR(20)   NOT NULL DEFAULT '' COMMENT '如"3个""半斤""200g"',
    expiry_date DATE          NULL,
    photo_data  TEXT          NULL,
    confidence  DECIMAL(3,2)  NULL COMMENT 'AI识别置信度0-1',
    source      VARCHAR(10)   NOT NULL DEFAULT 'manual' COMMENT '录入来源：photo|voice|manual',
    status      VARCHAR(10)  NOT NULL DEFAULT 'available' COMMENT '状态：available|used_up|expired',
    created_at  DATETIME      NOT NULL DEFAULT (NOW()),
    updated_at  DATETIME      NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '食材库存表，AI推荐菜谱的核心输入';

CREATE INDEX idx_ingredients_user     ON ingredients(user_id);
CREATE INDEX idx_ingredients_category ON ingredients(user_id, category);
CREATE INDEX idx_ingredients_expiry   ON ingredients(user_id, expiry_date);
CREATE INDEX idx_ingredients_status   ON ingredients(user_id, status);

DELIMITER //
CREATE TRIGGER trg_ingredients_updated_at
    BEFORE UPDATE ON ingredients
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;

-- ============================================================
-- 4. 做饭日记表（Cook Mode 核心）
-- ============================================================
CREATE TABLE cook_records (
    id              VARCHAR(36)   PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)   NOT NULL,
    dish_name       VARCHAR(100)  NOT NULL COMMENT '菜名',
    photo_url       TEXT          NULL,
    mood            VARCHAR(10)   NOT NULL DEFAULT '' COMMENT '心情：开心|难过|烦躁|焦虑|疲惫|庆祝|嘴馋|平淡|满足|超好吃|翻车了|空',
    rating          TINYINT       NULL COMMENT '1-3星评分: 1=踩雷 2=还行 3=好吃',
    cooking_time    SMALLINT      NULL COMMENT '实际烹饪时间（分钟）',
    difficulty      VARCHAR(10)   NOT NULL DEFAULT '' COMMENT '简单|中等|挑战',
    estimated_cost  DECIMAL(6,2)  NULL COMMENT '预估成本（元）',
    note            VARCHAR(200)  NOT NULL DEFAULT '',
    tags            JSON          NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '标签JSON数组',
    ai_recommend_id VARCHAR(36)   NULL COMMENT '关联的菜谱缓存ID',
    created_at      DATETIME      NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '做饭日记表，偏好学习主要来源';

CREATE INDEX idx_cook_user_date ON cook_records(user_id, created_at DESC);
CREATE INDEX idx_cook_mood      ON cook_records(user_id, mood);

-- ============================================================
-- 5. 每日运势缓存表（先于 takeout_records 创建，因外键依赖）
-- ============================================================
CREATE TABLE daily_fortunes (
    id                      VARCHAR(36)   PRIMARY KEY DEFAULT (UUID()),
    user_id                 VARCHAR(36)   NOT NULL,
    date                    DATE          NOT NULL,
    zodiac                  VARCHAR(10)   NOT NULL,
    chinese_zodiac          VARCHAR(5)    NOT NULL,
    mbti                    VARCHAR(4)    NOT NULL,
    zodiac_fortune          VARCHAR(500)  NOT NULL DEFAULT '',
    chinese_zodiac_fortune  VARCHAR(500)  NOT NULL DEFAULT '',
    mbti_energy             VARCHAR(300)  NOT NULL DEFAULT '',
    food_keywords           JSON          NOT NULL DEFAULT (JSON_ARRAY()),
    lucky_color             VARCHAR(10)   NOT NULL DEFAULT '',
    lucky_number            TINYINT       NULL,
    suggestion              VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '综合饮食建议',
    source                  VARCHAR(50)   NOT NULL DEFAULT 'llm_web_search',
    created_at              DATETIME      NOT NULL DEFAULT (NOW()),
    UNIQUE(user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '每日运势缓存表，每天每个用户仅一条';

CREATE INDEX idx_fortune_date ON daily_fortunes(date);

-- ============================================================
-- 6. 外卖日记表（Order Mode 核心）
-- ============================================================
CREATE TABLE takeout_records (
    id                  VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id             VARCHAR(36)  NOT NULL,
    fortune_id          VARCHAR(36)  NULL COMMENT '关联的运势ID',
    mood                VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '心情：开心|难过|烦躁|焦虑|疲惫|庆祝|嘴馋|平淡|空',
    fortune_summary     VARCHAR(500) NOT NULL DEFAULT '' COMMENT '运势摘要快照',
    fortune_keywords    JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    final_choice        VARCHAR(100) NOT NULL DEFAULT '' COMMENT '最终选择的外卖',
    choice_reason       VARCHAR(500) NOT NULL DEFAULT '' COMMENT '选择理由',
    conversation_rounds TINYINT      NULL COMMENT '对话总轮次，1-5',
    satisfaction        VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '事后反馈：好吃|一般|踩雷|空',
    created_at          DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (fortune_id) REFERENCES daily_fortunes(id) ON DELETE SET NULL
) COMMENT '外卖日记表，方向二核心数据';

CREATE INDEX idx_takeout_user_date    ON takeout_records(user_id, created_at DESC);
CREATE INDEX idx_takeout_satisfaction ON takeout_records(user_id, satisfaction);
CREATE INDEX idx_takeout_mood         ON takeout_records(user_id, mood);

-- ============================================================
-- 7. 对话会话表 — 5轮状态机会话状态追踪
-- ============================================================
CREATE TABLE chat_sessions (
    id                VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id           VARCHAR(36)  NOT NULL,
    takeout_id        VARCHAR(36)  NULL COMMENT '关联的外卖记录ID，完成后回填',
    current_round     TINYINT      NOT NULL DEFAULT 1,
    total_rounds      TINYINT      NOT NULL DEFAULT 5,
    status            VARCHAR(20)  NOT NULL DEFAULT 'active' COMMENT 'active|completed|abandoned',
    -- 5轮维度收集结果
    taste_choice      VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第1轮: 口味选择',
    staple_choice     VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第2轮: 主食类型',
    meat_choice       VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第3轮: 肉类偏好',
    form_choice       VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第4轮: 烹饪形式',
    budget_choice     VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第5轮: 预算范围',
    -- LLM最终推荐
    final_recommend   VARCHAR(100) NOT NULL DEFAULT '',
    recommend_reason  VARCHAR(500) NOT NULL DEFAULT '',
    alternatives      JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    total_tokens      INT          NOT NULL DEFAULT 0,
    created_at        DATETIME     NOT NULL DEFAULT (NOW()),
    completed_at      DATETIME     NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (takeout_id) REFERENCES takeout_records(id) ON DELETE SET NULL
) COMMENT '外卖对话会话，5轮状态机控制';

CREATE INDEX idx_chat_session_user ON chat_sessions(user_id, status, created_at DESC);

DELIMITER //
CREATE TRIGGER trg_chat_session_complete
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
BEGIN
    IF NEW.status = 'completed' AND (OLD.status != 'completed' OR OLD.status IS NULL) THEN
        SET NEW.completed_at = NOW();
    END IF;
END//
DELIMITER ;

-- ============================================================
-- 8. AI对话记录表 — 每轮对话内容
-- ============================================================
CREATE TABLE chat_turns (
    id            VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    session_id    VARCHAR(36)  NULL COMMENT '关联的会话ID（v2新增）',
    takeout_id    VARCHAR(36)  NULL COMMENT '关联的外卖记录ID（完成后回填，可空）',
    turn          TINYINT      NOT NULL COMMENT '第几轮对话，从1开始',
    role          VARCHAR(10)  NOT NULL COMMENT '说话方：ai|user',
    content       VARCHAR(500) NOT NULL DEFAULT '',
    ai_guess      VARCHAR(100) NULL COMMENT '当轮AI猜测的品类',
    ai_confidence DECIMAL(3,2) NULL COMMENT '当轮AI置信度0-1',
    created_at    DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (takeout_id) REFERENCES takeout_records(id) ON DELETE SET NULL
) COMMENT 'AI对话记录表，每轮次内容';

CREATE INDEX idx_chat_session ON chat_turns(session_id, turn);
CREATE INDEX idx_chat_takeout ON chat_turns(takeout_id, turn);

-- ============================================================
-- 9. 偏好权重历史表 — 加权移动平均: newW = oldW×0.7 + feedback×0.3
-- ============================================================
CREATE TABLE preference_weights (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    dimension       VARCHAR(20)  NOT NULL COMMENT '维度名: 辣|甜|酸|咸|清淡|油腻|清爽|预算|快手',
    weight          DECIMAL(4,3) NOT NULL DEFAULT 0.500,
    feedback_count  INT          NOT NULL DEFAULT 0 COMMENT '累计反馈次数',
    last_feedback   VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '最近反馈值: good|ok|bad',
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, dimension)
) COMMENT '偏好权重历史表，加权移动平均的核心存储';

CREATE INDEX idx_pref_weights_user ON preference_weights(user_id);

DELIMITER //
CREATE TRIGGER trg_pref_weights_updated
    BEFORE UPDATE ON preference_weights
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;

-- ============================================================
-- 10. 菜谱推荐缓存表 — LLM输出结果缓存
-- ============================================================
CREATE TABLE recipe_cache (
    id                  VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id             VARCHAR(36)  NOT NULL,
    recipe_name         VARCHAR(100) NOT NULL,
    difficulty          TINYINT      NOT NULL DEFAULT 1 COMMENT '1简单 2中等 3挑战',
    cooking_time        VARCHAR(10)  NOT NULL DEFAULT '',
    estimated_cost      VARCHAR(10)  NOT NULL DEFAULT '',
    reason              VARCHAR(500) NOT NULL DEFAULT '',
    steps               JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    matched_ingredients JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    missing_ingredients JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    llm_model           VARCHAR(50)  NOT NULL DEFAULT 'deepseek-v3',
    llm_temperature     DECIMAL(3,2) NOT NULL DEFAULT 0.70,
    prompt_hash         VARCHAR(64)  NOT NULL DEFAULT '',
    created_at          DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '菜谱推荐缓存，LLM输出结果持久化';

CREATE INDEX idx_recipe_user ON recipe_cache(user_id, created_at DESC);
CREATE INDEX idx_recipe_hash ON recipe_cache(user_id, prompt_hash);

-- ============================================================
-- 11. 购物清单表
-- ============================================================
CREATE TABLE shopping_items (
    id             VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id        VARCHAR(36)  NOT NULL,
    name           VARCHAR(50)  NOT NULL,
    category       VARCHAR(10)  NOT NULL COMMENT '品类：蔬菜|肉蛋|水产|主食|调料|乳制品|其他',
    quantity       VARCHAR(20)  NOT NULL DEFAULT '',
    checked        TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否已购',
    source_recipe  VARCHAR(100) NOT NULL DEFAULT '' COMMENT '来源菜谱名',
    source_cook_id VARCHAR(36)  NULL,
    created_at     DATETIME     NOT NULL DEFAULT (NOW()),
    checked_at     DATETIME     NULL COMMENT '勾选时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '购物清单表';

CREATE INDEX idx_shopping_user     ON shopping_items(user_id, checked);
CREATE INDEX idx_shopping_category ON shopping_items(user_id, category);

-- ============================================================
-- 12. 视图：周度统计
-- ============================================================
CREATE OR REPLACE VIEW v_user_weekly_stats AS
SELECT
    u.id AS user_id,
    u.nickname,
    DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) AS week_start,
    COUNT(CASE WHEN cr.created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) THEN cr.id END) AS weekly_cook_count,
    COUNT(CASE WHEN tr.created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) THEN tr.id END) AS weekly_takeout_count,
    COALESCE(SUM(CASE WHEN cr.created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) THEN cr.estimated_cost END), 0) AS weekly_cook_cost,
    COUNT(CASE WHEN cr.mood = '超好吃' AND cr.created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY) THEN cr.id END) AS great_cook_count
FROM users u
LEFT JOIN cook_records    cr ON cr.user_id = u.id
LEFT JOIN takeout_records tr ON tr.user_id = u.id
GROUP BY u.id, u.nickname;

-- ============================================================
-- 13. 视图：偏好权重汇总
-- ============================================================
CREATE OR REPLACE VIEW v_user_preference_weights AS
SELECT
    pw.user_id,
    pw.dimension,
    pw.weight,
    pw.feedback_count,
    pw.last_feedback,
    pw.updated_at,
    u.nickname
FROM preference_weights pw
JOIN users u ON u.id = pw.user_id
ORDER BY pw.user_id, pw.weight DESC;

-- ============================================================
-- 14. 视图：月度统计
-- ============================================================
CREATE OR REPLACE VIEW v_monthly_stats AS
SELECT
    u.id AS user_id,
    u.nickname,
    DATE_FORMAT(CURDATE(), '%Y-%m') AS stat_month,
    COUNT(DISTINCT cr.id) AS cook_count,
    COUNT(DISTINCT tr.id) AS takeout_count,
    COALESCE(SUM(cr.estimated_cost), 0) AS total_cook_cost,
    COALESCE(AVG(cr.rating), 0) AS avg_cook_rating,
    COALESCE(AVG(CASE
        WHEN tr.satisfaction = '好吃' THEN 3
        WHEN tr.satisfaction = '一般' THEN 2
        WHEN tr.satisfaction = '踩雷' THEN 1
        ELSE 0
    END), 0) AS avg_takeout_rating
FROM users u
LEFT JOIN cook_records cr ON cr.user_id = u.id
    AND DATE_FORMAT(cr.created_at, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
LEFT JOIN takeout_records tr ON tr.user_id = u.id
    AND DATE_FORMAT(tr.created_at, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
GROUP BY u.id, u.nickname;

-- ============================================================
-- 完成
-- ============================================================
SELECT 'v2 schema created successfully' AS status;
SELECT CONCAT('   tables: 10, views: 3, triggers: 4, indexes: 16') AS detail;
