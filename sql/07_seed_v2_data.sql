-- ============================================================
-- 美味出租屋 v2 — 增量示例数据
-- 补充: 口味权重JSON / 偏好权重表 / 对话会话 / 菜谱缓存
-- 日期：2026-08-17
-- 依赖：先执行 06_schema_v2_final.sql + 02_seed_data_mysql.sql
-- ============================================================
USE meiweichuzuwu;

-- ============================================================
-- 1. 更新用户口味权重JSON (user_preferences.taste_weights)
-- ============================================================
UPDATE user_preferences SET taste_weights = JSON_OBJECT(
    '辣', 0.82, '甜', 0.25, '酸', 0.60, '咸', 0.55,
    '清淡', 0.30, '油腻', 0.70, '清爽', 0.20, '预算', 0.65, '快手', 0.80
) WHERE user_id = 'u-001';

UPDATE user_preferences SET taste_weights = JSON_OBJECT(
    '辣', 0.45, '甜', 0.35, '酸', 0.20, '咸', 0.60,
    '清淡', 0.25, '油腻', 0.85, '清爽', 0.15, '预算', 0.50, '快手', 0.40
) WHERE user_id = 'u-002';

UPDATE user_preferences SET taste_weights = JSON_OBJECT(
    '辣', 0.15, '甜', 0.30, '酸', 0.10, '咸', 0.40,
    '清淡', 0.90, '油腻', 0.10, '清爽', 0.85, '预算', 0.75, '快手', 0.60
) WHERE user_id = 'u-003';

-- ============================================================
-- 2. 偏好权重表 (preference_weights)
-- 加权移动平均: newW = oldW×0.7 + feedback×0.3
-- ============================================================
INSERT INTO preference_weights (user_id, dimension, weight, feedback_count, last_feedback) VALUES
-- u-001: 小陈（深圳租房）— 偏辣、快手菜
('u-001', '辣',    0.820, 12, 'good'),
('u-001', '甜',    0.250,  3, 'ok'),
('u-001', '酸',    0.600,  5, 'good'),
('u-001', '咸',    0.550,  4, 'ok'),
('u-001', '清淡',  0.300,  2, 'bad'),
('u-001', '油腻',  0.700,  6, 'good'),
('u-001', '清爽',  0.200,  1, 'bad'),
('u-001', '预算',  0.650,  8, 'good'),
('u-001', '快手',  0.800, 10, 'good'),

-- u-002: 小王（北京合租）— 偏油腻重口
('u-002', '辣',    0.450,  3, 'ok'),
('u-002', '甜',    0.350,  2, 'ok'),
('u-002', '酸',    0.200,  1, 'bad'),
('u-002', '咸',    0.600,  4, 'ok'),
('u-002', '清淡',  0.250,  1, 'bad'),
('u-002', '油腻',  0.850, 10, 'good'),
('u-002', '清爽',  0.150,  0, ''),
('u-002', '预算',  0.500,  5, 'ok'),
('u-002', '快手',  0.400,  2, 'ok'),

-- u-003: 小李（上海单间）— 偏清淡健康
('u-003', '辣',    0.150,  0, ''),
('u-003', '甜',    0.300,  2, 'ok'),
('u-003', '酸',    0.100,  0, ''),
('u-003', '咸',    0.400,  3, 'ok'),
('u-003', '清淡',  0.900,  4, 'good'),
('u-003', '油腻',  0.100,  2, 'bad'),
('u-003', '清爽',  0.850,  3, 'good'),
('u-003', '预算',  0.750,  2, 'good'),
('u-003', '快手',  0.600,  1, 'ok');

-- ============================================================
-- 3. cook_records 补充 rating 列 (3星制: 1踩雷 2还行 3好吃)
-- ============================================================
UPDATE cook_records SET rating = 3 WHERE dish_name = '西红柿炒鸡蛋' AND user_id = 'u-001';
UPDATE cook_records SET rating = 3 WHERE dish_name = '青椒肉丝'       AND user_id = 'u-001';
UPDATE cook_records SET rating = 2 WHERE dish_name = '蒜蓉炒青菜'     AND user_id = 'u-001';
UPDATE cook_records SET rating = 3 WHERE dish_name = '可乐鸡翅'       AND user_id = 'u-001';
UPDATE cook_records SET rating = 2 WHERE dish_name = '蛋炒饭'         AND user_id = 'u-001';
UPDATE cook_records SET rating = 1 WHERE dish_name = '酸辣土豆丝'     AND user_id = 'u-001';
UPDATE cook_records SET rating = 3 WHERE dish_name = '豆腐青菜汤'     AND user_id = 'u-001';
UPDATE cook_records SET rating = 3 WHERE dish_name = '红烧肉'         AND user_id = 'u-001';

-- ============================================================
-- 4. 对话会话示例 (小王的外卖决策会话)
-- ============================================================
INSERT INTO chat_sessions (id, user_id, current_round, total_rounds, status, taste_choice, staple_choice, meat_choice, form_choice, budget_choice, final_recommend, recommend_reason, alternatives, total_tokens) VALUES
('cs-001', 'u-002', 5, 5, 'completed',
 '油腻', '米饭', '鸡肉', '炒菜', '15-30',
 '川渝麻辣香锅',
 '今日运势关键词"冒险尝试"与你的油腻偏好高度匹配，15-30元预算区间内麻辣香锅是最佳选择',
 JSON_ARRAY('日式豚骨拉面', '韩式烤肉拌饭'),
 1850);

-- 关联第一条外卖记录的 takeout_id
UPDATE chat_sessions SET takeout_id = (
    SELECT id FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1
) WHERE id = 'cs-001';

-- ============================================================
-- 5. 菜谱缓存示例 (小陈的推荐菜谱)
-- ============================================================
INSERT INTO recipe_cache (user_id, recipe_name, difficulty, cooking_time, estimated_cost, reason, steps, matched_ingredients, missing_ingredients, llm_model, llm_temperature, prompt_hash) VALUES
('u-001', '番茄炒蛋', 1, '8min', '¥6',
 '冰箱现成食材，最快最省，符合快手偏好(0.80)和预算偏好(0.65)',
 JSON_ARRAY('西红柿切块', '鸡蛋打散炒熟', '下西红柿翻炒', '加盐糖调味出锅'),
 JSON_ARRAY('鸡蛋', '西红柿'),
 JSON_ARRAY('葱花'),
 'deepseek-chat', 0.70, 'a3f8b2c1d9e7f0a1'),

('u-001', '青椒肉丝', 2, '15min', '¥8',
 '有猪肉和青椒，15分钟可完成，符合下饭偏好',
 JSON_ARRAY('猪肉切丝腌制', '青椒切丝', '热油爆炒肉丝', '下青椒翻炒调味'),
 JSON_ARRAY('猪肉', '青椒'),
 JSON_ARRAY('姜丝', '料酒'),
 'deepseek-chat', 0.70, 'c4d9e2b7a8f10365'),

('u-001', '豆腐青菜汤', 1, '12min', '¥4',
 '热乎暖胃适合疲惫晚上，清淡健康选择',
 JSON_ARRAY('豆腐切块', '青菜洗净', '水烧开放豆腐', '加青菜调味出锅'),
 JSON_ARRAY('豆腐', '青菜'),
 JSON_ARRAY('香油'),
 'deepseek-chat', 0.70, 'b7e2f9a1c3d8e5f2');

-- ============================================================
-- 6. 更新 chat_turns 关联 session_id
-- ============================================================
UPDATE chat_turns ct
JOIN takeout_records tr ON ct.takeout_id = tr.id
SET ct.session_id = 'cs-001'
WHERE tr.user_id = 'u-002'
AND tr.id = (SELECT min_id FROM (SELECT MIN(id) AS min_id FROM takeout_records WHERE user_id = 'u-002') t);

-- ============================================================
-- 7. 验证
-- ============================================================
SELECT '========================================' AS '';
SELECT 'v2 seed data inserted!' AS '';
SELECT '========================================' AS '';
SELECT CONCAT('  preference_weights: ', COUNT(*), ' rows') FROM preference_weights;
SELECT CONCAT('  recipe_cache:       ', COUNT(*), ' rows') FROM recipe_cache;
SELECT CONCAT('  chat_sessions:      ', COUNT(*), ' rows') FROM chat_sessions;
SELECT CONCAT('  cook_records rated: ', COUNT(*), ' rows') FROM cook_records WHERE rating IS NOT NULL;
SELECT CONCAT('  taste_weights set:  ', COUNT(*), ' rows') FROM user_preferences WHERE JSON_LENGTH(taste_weights) > 0;
SELECT '========================================' AS '';
