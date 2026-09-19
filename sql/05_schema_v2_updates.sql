-- ============================================================
-- 美味出租屋 v2 — Schema 增量更新
-- 基于Web原型PRD补充: 偏好权重引擎 / 菜谱缓存 / 对话会话 / 口味权重
-- 日期：2026-08-17
-- 依赖：先执行 01_schema_mysql.sql
-- 注意：全新部署推荐直接使用 06_schema_v2_final.sql
-- ============================================================
USE meiweichuzuwu;

-- ============================================================
-- 1. user_preferences 增列: 口味权重JSON (对齐原型8维口味)
-- ============================================================
ALTER TABLE user_preferences
    ADD COLUMN taste_weights JSON NOT NULL DEFAULT (JSON_OBJECT()) AFTER taste_preference
    COMMENT '口味维度权重JSON, 如{"辣":0.72,"甜":0.30,"酸":0.15,"清淡":0.55}';

-- 原型8种口味: 辣/甜/酸/咸/清淡/油腻/清爽/都行
-- 放宽 taste_preference 约束以兼容原型
-- MySQL 8.0+ 内联CHECK约束自动命名为 {table}_chk_{N}
ALTER TABLE user_preferences DROP CHECK user_preferences_chk_1;
ALTER TABLE user_preferences
    MODIFY COLUMN taste_preference VARCHAR(10) NOT NULL DEFAULT '不挑'
    COMMENT '首选口味(单选): 辣|甜|酸|咸|清淡|油腻|清爽|都行|不挑';

-- ============================================================
-- 2. cook_records 增列: 评分rating (对齐原型3星制)
-- ============================================================
ALTER TABLE cook_records
    ADD COLUMN rating TINYINT NULL CHECK (rating >= 1 AND rating <= 3) AFTER mood
    COMMENT '1-3星评分: 1=踩雷 2=还行 3=好吃';

-- 放宽 mood CHECK 约束以兼容原型
ALTER TABLE cook_records DROP CHECK cook_records_chk_1;
ALTER TABLE cook_records
    MODIFY COLUMN mood VARCHAR(10) NOT NULL DEFAULT ''
    COMMENT '心情: 满足|还行|翻车了|超好吃|开心|难过|烦躁|焦虑|疲惫|庆祝|嘴馋|平淡|空';

-- ============================================================
-- 3. takeout_records 放宽 mood 约束 (对齐原型8种心情)
-- ============================================================
ALTER TABLE takeout_records DROP CHECK takeout_records_chk_1;
ALTER TABLE takeout_records
    MODIFY COLUMN mood VARCHAR(10) NOT NULL DEFAULT ''
    COMMENT '心情: 开心|难过|烦躁|焦虑|疲惫|庆祝|嘴馋|平淡|空';

-- ============================================================
-- 4. 偏好权重历史表 — 加权移动平均: newW = oldW×0.7 + feedback×0.3
-- ============================================================
DROP TABLE IF EXISTS preference_weights;
CREATE TABLE preference_weights (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    dimension       VARCHAR(20)  NOT NULL COMMENT '维度名: 辣|甜|酸|咸|清淡|油腻|清爽|预算|快手',
    weight          DECIMAL(4,3) NOT NULL DEFAULT 0.500 CHECK (weight >= 0 AND weight <= 1),
    feedback_count  INT          NOT NULL DEFAULT 0 COMMENT '累计反馈次数',
    last_feedback   VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '最近反馈值: good|ok|bad',
    updated_at      DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, dimension)
) COMMENT '偏好权重历史表, 加权移动平均的核心存储';

CREATE INDEX idx_pref_weights_user ON preference_weights(user_id);

-- 触发器: 自动更新 updated_at
DELIMITER //
CREATE TRIGGER trg_pref_weights_updated
    BEFORE UPDATE ON preference_weights
    FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END//
DELIMITER ;

-- ============================================================
-- 5. 菜谱推荐缓存表 — LLM输出结果缓存, 减少重复调用
-- ============================================================
DROP TABLE IF EXISTS recipe_cache;
CREATE TABLE recipe_cache (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    recipe_name     VARCHAR(100) NOT NULL,
    difficulty      TINYINT      NOT NULL DEFAULT 1 CHECK (difficulty >= 1 AND difficulty <= 3) COMMENT '1简单 2中等 3挑战',
    cooking_time    VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '如8min, 25min',
    estimated_cost  VARCHAR(10)  NOT NULL DEFAULT '' COMMENT '如¥6, ¥8',
    reason          VARCHAR(500) NOT NULL DEFAULT '' COMMENT 'LLM推荐理由',
    steps           JSON         NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '步骤JSON数组',
    matched_ingredients JSON     NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '匹配到的库存食材',
    missing_ingredients JSON    NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '缺少的食材',
    llm_model       VARCHAR(50)  NOT NULL DEFAULT 'deepseek-v3' COMMENT '使用的LLM模型',
    llm_temperature DECIMAL(3,2) NOT NULL DEFAULT 0.70,
    prompt_hash     VARCHAR(64)  NOT NULL DEFAULT '' COMMENT 'Prompt哈希, 用于换一换去重',
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT '菜谱推荐缓存, LLM输出结果持久化';

CREATE INDEX idx_recipe_user ON recipe_cache(user_id, created_at DESC);
CREATE INDEX idx_recipe_hash ON recipe_cache(user_id, prompt_hash);

-- ============================================================
-- 6. 对话会话表 — 5轮状态机会话状态追踪
-- ============================================================
DROP TABLE IF EXISTS chat_sessions;
CREATE TABLE chat_sessions (
    id              VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id         VARCHAR(36)  NOT NULL,
    takeout_id      VARCHAR(36)  NULL COMMENT '关联的外卖记录ID, 完成后回填',
    current_round   TINYINT      NOT NULL DEFAULT 1 CHECK (current_round >= 1 AND current_round <= 5),
    total_rounds    TINYINT      NOT NULL DEFAULT 5,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    -- 5轮维度收集结果
    taste_choice    VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第1轮: 口味选择',
    staple_choice   VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第2轮: 主食类型',
    meat_choice     VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第3轮: 肉类偏好',
    form_choice     VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第4轮: 烹饪形式',
    budget_choice   VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '第5轮: 预算范围',
    -- LLM最终推荐
    final_recommend VARCHAR(100) NOT NULL DEFAULT '' COMMENT 'LLM最终推荐外卖',
    recommend_reason VARCHAR(500) NOT NULL DEFAULT '' COMMENT '推荐理由',
    alternatives    JSON         NOT NULL DEFAULT (JSON_ARRAY()) COMMENT '备选推荐JSON',
    -- 约束: LLM输出 token统计
    total_tokens    INT          NOT NULL DEFAULT 0 COMMENT '总消耗tokens',
    created_at      DATETIME     NOT NULL DEFAULT (NOW()),
    completed_at    DATETIME     NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (takeout_id) REFERENCES takeout_records(id) ON DELETE SET NULL
) COMMENT '外卖对话会话, 5轮状态机控制';

CREATE INDEX idx_chat_session_user ON chat_sessions(user_id, status, created_at DESC);

-- 触发器: 完成时自动设置completed_at
DELIMITER //
CREATE TRIGGER trg_chat_session_complete
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        SET NEW.completed_at = NOW();
    END IF;
END//
DELIMITER ;

-- ============================================================
-- 7. 周边视图: 偏好权重汇总 (供Diary页面偏好引擎展示)
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
-- 7.5 chat_turns 增列: session_id（v2新增，关联会话而非直接关联外卖记录）
-- ============================================================
ALTER TABLE chat_turns
    ADD COLUMN session_id VARCHAR(36) NULL AFTER id
    COMMENT '关联的对话会话ID';

ALTER TABLE chat_turns
    ADD CONSTRAINT fk_chat_turns_session
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;

-- 放宽 takeout_id 约束: 原为 NOT NULL，对话进行中尚无外卖记录，改为可空
ALTER TABLE chat_turns
    MODIFY COLUMN takeout_id VARCHAR(36) NULL
    COMMENT '关联的外卖记录ID（完成后回填，可空）';

CREATE INDEX idx_chat_turns_session ON chat_turns(session_id, turn);

-- ============================================================
-- 8. 周边视图: 月度统计 (供Diary页面统计面板)
-- ============================================================
CREATE OR REPLACE VIEW v_monthly_stats AS
SELECT
    u.id AS user_id,
    u.nickname,
    DATE_FORMAT(CURDATE(), '%Y-%m') AS stat_month,
    COUNT(DISTINCT cr.id) AS cook_count,
    COUNT(DISTINCT tr.id) AS takeout_count,
    COALESCE(SUM(cr.estimated_cost), 0) AS total_cook_cost,
    COALESCE(SUM(0), 0) AS total_takeout_cost,
    COALESCE(AVG(cr.rating), 0) AS avg_cook_rating,
    COALESCE(AVG(CASE WHEN tr.satisfaction = '好吃' THEN 3 WHEN tr.satisfaction = '一般' THEN 2 WHEN tr.satisfaction = '踩雷' THEN 1 ELSE 0 END), 0) AS avg_takeout_rating
FROM users u
LEFT JOIN cook_records cr ON cr.user_id = u.id
    AND DATE_FORMAT(cr.created_at, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
LEFT JOIN takeout_records tr ON tr.user_id = u.id
    AND DATE_FORMAT(tr.created_at, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
GROUP BY u.id, u.nickname;

-- ============================================================
-- 完成
-- ============================================================
SELECT '✅ Schema v2 更新完成！' AS status;
SELECT '   新增: preference_weights, recipe_cache, chat_sessions' AS detail;
SELECT '   新增列: user_preferences.taste_weights, cook_records.rating' AS detail;
SELECT '   新增视图: v_user_preference_weights, v_monthly_stats' AS detail;
SELECT '   放宽约束: taste_preference, mood (兼容原型8维口味/8种心情)' AS detail;
