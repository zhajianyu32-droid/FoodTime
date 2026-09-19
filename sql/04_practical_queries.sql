-- ============================================================
-- 美味出租屋 — 实用查询集
-- 版本：v1.0 | 日期：2026-08-05
-- 用途：展示产品核心功能对应的 SQL 查询
-- ============================================================

-- ============================================================
-- 【方向一】拍照识别 → 获取当前库存
-- ============================================================
-- 场景：用户打开"自己做"页面，展示冰箱食材标签云
SELECT
    name,
    category,
    quantity,
    expiry_date,
    CASE
        WHEN expiry_date <= date('now')              THEN 'expired'
        WHEN expiry_date <= date('now', '+2 days')   THEN 'expiring_soon'
        ELSE 'fresh'
    END AS freshness,
    source,
    confidence
FROM ingredients
WHERE user_id = 'u-001'
  AND status  = 'available'
ORDER BY
    CASE freshness
        WHEN 'expired'       THEN 1
        WHEN 'expiring_soon' THEN 2
        ELSE 3
    END,
    category;

-- ============================================================
-- 【方向一】临期食材提醒
-- ============================================================
-- 场景：系统检测到临期食材，触发Push通知 + 页面高亮
SELECT
    name,
    category,
    quantity,
    CAST(julianday(expiry_date) - julianday('now') AS INTEGER) AS days_left
FROM ingredients
WHERE user_id = 'u-001'
  AND status  = 'available'
  AND expiry_date <= date('now', '+2 days')   -- 2天内过期
  AND expiry_date >= date('now')              -- 尚未过期
ORDER BY expiry_date;

-- ============================================================
-- 【方向一】购物清单按品类分组
-- ============================================================
-- 场景：AI推荐菜谱后生成的购物清单，按品类分组展示
SELECT
    category,
    COUNT(*)                                      AS item_count,
    SUM(CASE WHEN checked THEN 1 ELSE 0 END)      AS checked_count,
    string_agg(name, '、' ORDER BY name)          AS items  -- PostgreSQL
    -- group_concat(name, '、')                    AS items  -- SQLite
FROM shopping_items
WHERE user_id = 'u-001'
GROUP BY category
ORDER BY
    CASE category
        WHEN '蔬菜' THEN 1
        WHEN '肉蛋' THEN 2
        WHEN '水产' THEN 3
        WHEN '主食' THEN 4
        WHEN '调料' THEN 5
        WHEN '乳制品' THEN 6
        ELSE 7
    END;

-- ============================================================
-- 【方向一】美食日历热力图 — 最近30天做饭记录
-- ============================================================
-- 场景：美食日记页的日历热力图，深色=做饭次数多
SELECT
    date(created_at)           AS cook_date,
    COUNT(*)                   AS cook_count,
    string_agg(dish_name, '、') AS dishes,
    AVG(estimated_cost)        AS avg_cost,
    MAX(mood)                  AS best_mood    -- 粗略取当天最好心情
FROM cook_records
WHERE user_id      = 'u-001'
  AND created_at  >= date('now', '-30 days')
GROUP BY date(created_at)
ORDER BY cook_date DESC;

-- ============================================================
-- 【方向一】统计面板 — 省钱 & 成就
-- ============================================================
-- 场景：本月做饭次数、省钱金额、最常做菜品
SELECT
    COUNT(*)                            AS this_month_cook_count,
    COALESCE(SUM(estimated_cost), 0)    AS this_month_total_cost,
    COUNT(*) * 35 - COALESCE(SUM(estimated_cost), 0) AS saved_vs_takeout,
    ROUND(AVG(cooking_time), 0)         AS avg_cooking_minutes,
    COUNT(*) FILTER (WHERE mood = '超好吃') AS great_cook_count
FROM cook_records
WHERE user_id     = 'u-001'
  AND created_at >= date('now', 'start of month');

-- 本月最常做的菜 TOP5
SELECT
    dish_name,
    COUNT(*)    AS times_cooked,
    AVG(estimated_cost) AS avg_cost,
    MAX(created_at)     AS last_cooked
FROM cook_records
WHERE user_id     = 'u-001'
  AND created_at >= date('now', 'start of month')
GROUP BY dish_name
ORDER BY times_cooked DESC
LIMIT 5;

-- ============================================================
-- 【方向二】今日运势查询（缓存优先）
-- ============================================================
-- 场景：用户打开"点外卖"页面，先查缓存，无则调AI生成
SELECT
    food_keywords,
    lucky_color,
    lucky_number,
    suggestion,
    zodiac_fortune,
    chinese_zodiac_fortune,
    mbti_energy
FROM daily_fortunes
WHERE user_id = 'u-002'
  AND date   = date('now')   -- 当天运势
LIMIT 1;

-- ============================================================
-- 【方向二】最近外卖决策 — 满意度趋势
-- ============================================================
-- 场景：分析用户外卖满意度，判断推荐质量
SELECT
    date(created_at)    AS decision_date,
    mood,
    final_choice,
    satisfaction,
    conversation_rounds,
    fortune_summary
FROM takeout_records
WHERE user_id    = 'u-002'
  AND created_at >= date('now', '-14 days')
ORDER BY created_at DESC;

-- 满意度统计（用于偏好学习权重调整）
SELECT
    satisfaction,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM takeout_records
WHERE user_id     = 'u-002'
  AND satisfaction != ''
GROUP BY satisfaction
ORDER BY count DESC;

-- ============================================================
-- 【方向二】还原一次完整的外卖决策对话
-- ============================================================
-- 场景：用户点击"觅食日记"卡片，查看当天的完整对话过程
SELECT
    ct.turn,
    ct.role,
    ct.content,
    ct.ai_guess,
    ct.ai_confidence,
    tr.final_choice,
    tr.satisfaction
FROM chat_turns ct
JOIN takeout_records tr ON tr.id = ct.takeout_id
WHERE tr.user_id = 'u-002'
ORDER BY tr.created_at DESC, ct.turn
LIMIT 20;

-- ============================================================
-- 【跨方向】用户偏好引擎 — 综合推荐权重
-- ============================================================
-- 场景：结合两个方向的历史数据，计算用户综合口味偏好
WITH
cook_prefs AS (
    -- 从做饭日记中提取偏好信号
    SELECT
        user_id,
        -- 喜欢辣味菜（菜名或标签含"辣"）
        COUNT(*) FILTER (WHERE dish_name LIKE '%辣%'
            OR tags::text LIKE '%辣%'
            OR mood = '超好吃') AS spicy_preference_score,
        -- 喜欢快手菜（标签含"快手菜" 或 cooking_time < 15）
        COUNT(*) FILTER (WHERE tags::text LIKE '%快手菜%'
            OR cooking_time <= 15) AS quick_meal_score,
        -- 预算敏感度（平均成本越低越敏感）
        AVG(estimated_cost) AS avg_cook_cost
    FROM cook_records
    WHERE user_id = 'u-001'
    GROUP BY user_id
),
takeout_prefs AS (
    -- 从外卖日记中提取偏好信号
    SELECT
        user_id,
        COUNT(*) FILTER (WHERE satisfaction = '好吃')     AS good_count,
        COUNT(*) FILTER (WHERE satisfaction = '踩雷')     AS bad_count,
        ROUND(AVG(conversation_rounds), 1)                AS avg_rounds,
        COUNT(*) FILTER (WHERE mood IN ('郁闷','焦虑','疲惫')) AS negative_mood_count
    FROM takeout_records
    WHERE user_id = 'u-001'
    GROUP BY user_id
)
SELECT
    up.taste_preference,
    up.budget_level,
    up.cooking_skill,
    COALESCE(cp.spicy_preference_score, 0) AS spicy_signals,
    COALESCE(cp.quick_meal_score, 0)       AS quick_meal_signals,
    COALESCE(tp.good_count, 0)             AS successful_recommendations,
    COALESCE(tp.bad_count, 0)              AS failed_recommendations,
    CASE
        WHEN COALESCE(tp.good_count, 0) + COALESCE(tp.bad_count, 0) = 0 THEN 0
        ELSE ROUND(
            COALESCE(tp.good_count, 0) * 100.0
            / (COALESCE(tp.good_count, 0) + COALESCE(tp.bad_count, 0)), 1
        )
    END AS recommendation_accuracy_pct
FROM user_preferences up
LEFT JOIN cook_prefs    cp ON cp.user_id = up.user_id
LEFT JOIN takeout_prefs tp ON tp.user_id = up.user_id
WHERE up.user_id = 'u-001';

-- ============================================================
-- 【全产品】用户周报 — 综合仪表盘
-- ============================================================
-- 场景：每周自动生成使用报告
SELECT
    -- 方向一
    COUNT(DISTINCT cr.id)   AS weekly_cook_count,
    COALESCE(SUM(cr.estimated_cost), 0)  AS weekly_cook_cost,
    ROUND(AVG(cr.cooking_time), 0)       AS avg_cooking_minutes,
    COUNT(DISTINCT cr.id) FILTER (WHERE cr.mood = '超好吃') AS great_meals,
    -- 方向二
    COUNT(DISTINCT tr.id)   AS weekly_takeout_decisions,
    COUNT(DISTINCT tr.id) FILTER (WHERE tr.satisfaction = '好吃') AS good_decisions,
    COUNT(DISTINCT tr.id) FILTER (WHERE tr.satisfaction = '踩雷') AS bad_decisions,
    -- 综合
    COUNT(DISTINCT cr.id) * 35 - COALESCE(SUM(cr.estimated_cost), 0)
        + COUNT(DISTINCT tr.id) * 5 AS total_saved_estimate   -- 外卖决策省5元(省了比价时间)
FROM generate_series(
    date('now', '-7 days'),
    date('now'),
    '1 day'
) AS d(day)
LEFT JOIN cook_records    cr ON cr.user_id = 'u-001' AND date(cr.created_at) = d.day
LEFT JOIN takeout_records tr ON tr.user_id = 'u-001' AND date(tr.created_at) = d.day;

-- ============================================================
-- 【维护】数据清理 — 删除过期图片释放空间
-- ============================================================
-- 场景：localStorage > 4MB 时触发，清理30天前的照片
-- (仅清理photo_data/photo_url，保留文字数据)
UPDATE ingredients
SET photo_data = NULL
WHERE user_id   = 'u-001'
  AND created_at < date('now', '-30 days')
  AND photo_data IS NOT NULL;

UPDATE cook_records
SET photo_url = NULL
WHERE user_id   = 'u-001'
  AND created_at < date('now', '-30 days')
  AND photo_url IS NOT NULL;

-- 统计清理后释放的空间
SELECT
    'ingredients'  AS table_name,
    COUNT(*)       AS cleaned_rows
FROM ingredients
WHERE user_id   = 'u-001'
  AND photo_data IS NULL
  AND created_at >= date('now', '-30 days')
UNION ALL
SELECT
    'cook_records' AS table_name,
    COUNT(*)       AS cleaned_rows
FROM cook_records
WHERE user_id   = 'u-001'
  AND photo_url IS NULL
  AND created_at >= date('now', '-30 days');

-- ============================================================
-- 查询索引使用建议（PostgreSQL EXPLAIN ANALYZE）
-- ============================================================
-- 以下查询会用到对应索引，可用 EXPLAIN ANALYZE 验证执行计划：
--
-- SELECT * FROM ingredients WHERE user_id = 'u-001' AND status = 'available';
-- → 使用 idx_ingredients_status
--
-- SELECT * FROM cook_records WHERE user_id = 'u-001' ORDER BY created_at DESC LIMIT 20;
-- → 使用 idx_cook_user_date
--
-- SELECT * FROM daily_fortunes WHERE user_id = 'u-002' AND date = date('now');
-- → 使用 UNIQUE(user_id, date) 约束索引
--
-- SELECT * FROM shopping_items WHERE user_id = 'u-001' AND checked = FALSE;
-- → 使用 idx_shopping_user

-- ============================================================
-- 完成
-- ============================================================
SELECT '✅ Practical queries ready!' AS status;
