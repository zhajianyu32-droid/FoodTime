-- ============================================================
-- 美味出租屋 (MeiWeiChuZuWu) — MySQL 建表脚本
-- 版本：v1.0 | 日期：2026-08-05
-- 转换自：01_schema_postgresql.sql
-- 兼容：MySQL 8.4+
-- ============================================================

-- 创建并使用数据库
CREATE DATABASE IF NOT EXISTS meiweichuzuwu
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE meiweichuzuwu;

-- 清理旧表（按依赖顺序删除，避免外键冲突）
DROP TABLE IF EXISTS chat_turns;
DROP TABLE IF EXISTS shopping_items;
DROP TABLE IF EXISTS daily_fortunes;
DROP TABLE IF EXISTS takeout_records;
DROP TABLE IF EXISTS cook_records;
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS user_preferences;
DROP TABLE IF EXISTS users;

-- ============================================================
-- 1. 用户表（MVP阶段预留，需跨设备同步时启用）
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
) COMMENT '用户表（MVP阶段预留）';

-- ============================================================
-- 2. 用户偏好表（1:1 关联 users）
-- ============================================================
CREATE TABLE user_preferences (
    id                          VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id                     VARCHAR(36)  UNIQUE NOT NULL,
    -- 基础信息
    zodiac                      VARCHAR(10)  NOT NULL DEFAULT '',
    mbti                        VARCHAR(4)   NOT NULL DEFAULT '',
    chinese_zodiac              VARCHAR(5)   NOT NULL DEFAULT '',
    -- 方向一：做饭偏好
    taste_preference            VARCHAR(10)  NOT NULL DEFAULT '不挑'
        CHECK (taste_preference IN ('清淡', '重口', '酸甜', '辣', '不挑')),
    budget_level                VARCHAR(10)  NOT NULL DEFAULT '正常'
        CHECK (budget_level IN ('省钱', '正常', '吃好点')),
    cooking_skill               VARCHAR(10)  NOT NULL DEFAULT '一般'
        CHECK (cooking_skill IN ('新手', '一般', '熟练')),
    cookware                    JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    disliked_ingredients        JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    liked_dishes                JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    -- 方向二：外卖偏好
    liked_takeout_categories    JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    disliked_takeout_categories JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    -- 元数据
    created_at                  DATETIME     NOT NULL DEFAULT (NOW()),
    updated_at                  DATETIME     NOT NULL DEFAULT (NOW()),
    -- 外键
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '用户偏好表，双方向推荐引擎的核心数据源';

-- 列注释
ALTER TABLE user_preferences MODIFY COLUMN taste_preference VARCHAR(10) NOT NULL DEFAULT '不挑' COMMENT '口味偏好：清淡|重口|酸甜|辣|不挑';
ALTER TABLE user_preferences MODIFY COLUMN cookware JSON NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '厨具列表JSON，如["电磁炉","空气炸锅","电饭煲"]';
ALTER TABLE user_preferences MODIFY COLUMN disliked_ingredients JSON NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '忌口食材JSON，如["香菜","青椒","内脏"]';
ALTER TABLE user_preferences MODIFY COLUMN liked_dishes JSON NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '历史喜欢菜名JSON，由满意度反馈自动更新';

CREATE INDEX idx_prefs_user_id ON user_preferences(user_id);

-- 自动更新触发器
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
    name        VARCHAR(50)   NOT NULL COMMENT '食材中文常用名，如"鸡蛋""西红柿"',
    category    VARCHAR(10)   NOT NULL
        CHECK (category IN ('蔬菜', '肉蛋', '水产', '主食', '调料', '乳制品', '其他')),
    quantity    VARCHAR(20)   NOT NULL DEFAULT '' COMMENT '数量描述，如"3个""半斤""1把""200g"',
    expiry_date DATE          NULL,
    photo_data  TEXT          NULL,
    confidence  DECIMAL(3,2)  NULL CHECK (confidence >= 0 AND confidence <= 1) COMMENT 'AI识别置信度0-1，<0.7表示不确定',
    source      VARCHAR(10)   NOT NULL DEFAULT 'manual'
        CHECK (source IN ('photo', 'voice', 'manual')),
    status      VARCHAR(10)   NOT NULL DEFAULT 'available'
        CHECK (status IN ('available', 'used_up', 'expired')),
    created_at  DATETIME      NOT NULL DEFAULT (NOW()),
    updated_at  DATETIME      NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '食材库存表，AI推荐菜谱的核心输入';

-- 列注释
ALTER TABLE ingredients MODIFY COLUMN category VARCHAR(10) NOT NULL COMMENT '品类：蔬菜|肉蛋|水产|主食|调料|乳制品|其他';
ALTER TABLE ingredients MODIFY COLUMN source VARCHAR(10) NOT NULL DEFAULT 'manual' COMMENT '录入来源：photo|voice|manual';
ALTER TABLE ingredients MODIFY COLUMN status VARCHAR(10) NOT NULL DEFAULT 'available' COMMENT '状态：available(可用)|used_up(已用完)|expired(已过期)';

CREATE INDEX idx_ingredients_user     ON ingredients(user_id);
CREATE INDEX idx_ingredients_category ON ingredients(user_id, category);
CREATE INDEX idx_ingredients_expiry   ON ingredients(user_id, expiry_date);  -- MySQL不支持部分索引，已改为普通索引
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
-- 4. 做饭日记表（方向一）
-- ============================================================
CREATE TABLE cook_records (
    id              VARCHAR(36)   PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)   NOT NULL,
    dish_name       VARCHAR(100)  NOT NULL COMMENT '菜名，如"西红柿炒鸡蛋"',
    photo_url       TEXT          NULL,
    mood            VARCHAR(10)   NOT NULL DEFAULT ''
        CHECK (mood IN ('满足', '还行', '翻车了', '超好吃', '')),
    cooking_time    SMALLINT      NULL CHECK (cooking_time > 0),
    difficulty      VARCHAR(10)   NOT NULL DEFAULT ''
        CHECK (difficulty IN ('简单', '中等', '挑战', '')),
    estimated_cost  DECIMAL(6,2)  NULL CHECK (estimated_cost >= 0),
    note            VARCHAR(200)  NOT NULL DEFAULT '',
    tags            JSON          NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '标签JSON数组',
    ai_recommend_id VARCHAR(36)   NULL,
    created_at      DATETIME      NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '做饭日记表，方向一核心数据，偏好学习主要来源';

ALTER TABLE cook_records MODIFY COLUMN estimated_cost DECIMAL(6,2) NULL COMMENT '预估成本（元）';
ALTER TABLE cook_records MODIFY COLUMN mood VARCHAR(10) NOT NULL DEFAULT '' COMMENT '心情：满足|还行|翻车了|超好吃';

CREATE INDEX idx_cook_user_date ON cook_records(user_id, created_at DESC);
CREATE INDEX idx_cook_mood      ON cook_records(user_id, mood);

-- ============================================================
-- 5. 外卖日记表（方向二）
-- ============================================================
CREATE TABLE takeout_records (
    id                  VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id             VARCHAR(36)  NOT NULL,
    fortune_id          VARCHAR(36)  NULL,
    mood                VARCHAR(10)  NOT NULL DEFAULT ''
        CHECK (mood IN ('开心', '郁闷', '烦躁', '焦虑', '疲惫', '兴奋', '无聊', '嘴馋', '')),
    fortune_summary     VARCHAR(500) NOT NULL DEFAULT '',
    fortune_keywords    JSON         NOT NULL DEFAULT (JSON_ARRAY()),
    final_choice        VARCHAR(100) NOT NULL DEFAULT '',
    choice_reason       VARCHAR(500) NOT NULL DEFAULT '',
    conversation_rounds TINYINT      NULL CHECK (conversation_rounds >= 1 AND conversation_rounds <= 5),
    satisfaction        VARCHAR(10)  NOT NULL DEFAULT ''
        CHECK (satisfaction IN ('好吃', '一般', '踩雷', '')),
    created_at          DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '外卖日记表，方向二核心数据';

ALTER TABLE takeout_records MODIFY COLUMN fortune_summary VARCHAR(500) NOT NULL DEFAULT '' COMMENT '运势摘要快照，防止运势源变更导致历史不一致';
ALTER TABLE takeout_records MODIFY COLUMN conversation_rounds TINYINT NULL COMMENT '对话总轮次，范围1-5';
ALTER TABLE takeout_records MODIFY COLUMN satisfaction VARCHAR(10) NOT NULL DEFAULT '' COMMENT '事后反馈：好吃|一般|踩雷|空=未反馈';

-- fortune_id 的外键在 daily_fortunes 创建后添加（见下方）

CREATE INDEX idx_takeout_user_date    ON takeout_records(user_id, created_at DESC);
CREATE INDEX idx_takeout_satisfaction ON takeout_records(user_id, satisfaction);
CREATE INDEX idx_takeout_mood         ON takeout_records(user_id, mood);

-- ============================================================
-- 6. AI 对话记录表（方向二子表）
-- ============================================================
CREATE TABLE chat_turns (
    id            VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    takeout_id    VARCHAR(36)  NOT NULL,
    turn          TINYINT      NOT NULL CHECK (turn >= 1 AND turn <= 5),
    role          VARCHAR(10)  NOT NULL CHECK (role IN ('ai', 'user')),
    content       VARCHAR(500) NOT NULL DEFAULT '',
    ai_guess      VARCHAR(100) NULL COMMENT '当轮AI猜测的品类，仅role=ai时填充',
    ai_confidence DECIMAL(3,2) NULL CHECK (ai_confidence >= 0 AND ai_confidence <= 1) COMMENT '当轮AI置信度，仅role=ai时填充',
    created_at    DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (takeout_id) REFERENCES takeout_records(id) ON DELETE CASCADE
) COMMENT 'AI对话记录表，方向二外卖引导对话的每一轮次';

ALTER TABLE chat_turns MODIFY COLUMN turn TINYINT NOT NULL COMMENT '第几轮对话，从1开始';
ALTER TABLE chat_turns MODIFY COLUMN role VARCHAR(10) NOT NULL COMMENT '说话方：ai|user';

CREATE INDEX idx_chat_takeout ON chat_turns(takeout_id, turn);

-- ============================================================
-- 7. 每日运势缓存表
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
    food_keywords           JSON          NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '综合美食关键词JSON',
    lucky_color             VARCHAR(10)   NOT NULL DEFAULT '',
    lucky_number            TINYINT       NULL CHECK (lucky_number >= 1 AND lucky_number <= 99),
    suggestion              VARCHAR(1000) NOT NULL DEFAULT '' COMMENT '综合饮食建议',
    source                  VARCHAR(50)   NOT NULL DEFAULT 'llm_web_search' COMMENT '运势来源',
    created_at              DATETIME      NOT NULL DEFAULT (NOW()),
    UNIQUE(user_id, date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '每日运势缓存表，每天每个用户仅一条';

ALTER TABLE daily_fortunes MODIFY COLUMN date DATE NOT NULL COMMENT '运势日期 YYYY-MM-DD，与user_id组成唯一约束';

CREATE INDEX idx_fortune_date ON daily_fortunes(date);

-- 补充：takeout_records 中 fortune_id 的外键
ALTER TABLE takeout_records
    ADD FOREIGN KEY (fortune_id) REFERENCES daily_fortunes(id) ON DELETE SET NULL;

-- ============================================================
-- 8. 购物清单表
-- ============================================================
CREATE TABLE shopping_items (
    id             VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id        VARCHAR(36)  NOT NULL,
    name           VARCHAR(50)  NOT NULL,
    category       VARCHAR(10)  NOT NULL
        CHECK (category IN ('蔬菜', '肉蛋', '水产', '主食', '调料', '乳制品', '其他')),
    quantity       VARCHAR(20)  NOT NULL DEFAULT '',
    checked        TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否已购（勾选状态）',
    source_recipe  VARCHAR(100) NOT NULL DEFAULT '' COMMENT '来源菜谱名',
    source_cook_id VARCHAR(36)  NULL,
    created_at     DATETIME     NOT NULL DEFAULT (NOW()),
    checked_at     DATETIME     NULL COMMENT '勾选时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '购物清单表，AI推荐菜谱后自动生成';

CREATE INDEX idx_shopping_user     ON shopping_items(user_id, checked);
CREATE INDEX idx_shopping_category ON shopping_items(user_id, category);

-- ============================================================
-- 数据迁移辅助视图（localStorage JSON → 数据库的过渡期使用）
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
-- 完成
-- ============================================================
SELECT '✅ 美味出租屋 MySQL 建表完成！' AS status;
SELECT '   共创建 8 张表、1 个视图、2 个触发器、13 个索引' AS detail;
