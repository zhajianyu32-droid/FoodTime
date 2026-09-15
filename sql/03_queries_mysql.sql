-- ============================================================
-- 美味出租屋 — 实用查询集（MySQL版）
-- 版本：v1.0 | 日期：2026-08-05
-- 转换自：04_practical_queries.sql
-- 兼容：MySQL 8.4+
-- ============================================================
USE meiweichuzuwu;

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
        WHEN expiry_date <= CURDATE()                        THEN 'expired'
        WHEN expiry_date <= DATE_ADD(CURDATE(), INTERVAL 2 DAY) THEN 'expiring_soon'
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
    DATEDIFF(expiry_date, CURDATE()) AS days_left
FROM ingredients
WHERE user_id = 'u-001'
  AND status  = 'available'
  AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 2 DAY)   -- 2天内过期
  AND expiry_date >= CURDATE()                             -- 尚未过期
ORDER BY expiry_date;

-- ============================================================
-- 【方向一】购物清单按品类分组
-- ============================================================
-- 场景：AI推荐菜谱后生成的购物清单，按品类分组展示
SELECT
    category,
    COUNT(*)                                          AS item_count,
    SUM(CASE WHEN checked THEN 1 ELSE 0 END)          AS checked_count,
    GROUP_CONCAT(name ORDER BY name SEPARATOR '、')   AS items
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
    DATE(created_at)               AS cook_date,
    COUNT(*)                       AS cook_count,
    GROUP_CONCAT(dish_name SEPARATOR '、') AS dishes,
    AVG(estimated_cost)            AS avg_cost,
    MAX(mood)                      AS best_mood    -- 粗略取当天最好心情
FROM cook_records
WHERE user_id      = 'u-001'
  AND created_at  >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY cook_date DESC;

-- ============================================================
-- 【方向一】统计面板 — 省钱 & 成就
-- ============================================================
-- 场景：本月做饭次数、省钱金额、最常做菜品
SELECT
    COUNT(*)                                          AS this_month_cook_count,
    COALESCE(SUM(estimated_cost), 0)                  AS this_month_total_cost,
    COUNT(*) * 35 - COALESCE(SUM(estimated_cost), 0)  AS saved_vs_takeout,
    ROUND(AVG(cooking_time), 0)                       AS avg_cooking_minutes,
    COUNT(CASE WHEN mood = '超好吃' THEN 1 END)       AS great_cook_count
FROM cook_records
WHERE user_id     = 'u-001'
  AND created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01');

-- 本月最常做的菜 TOP5
SELECT
    dish_name,
    COUNT(*)             AS times_cooked,
    AVG(estimated_cost)  AS avg_cost,
    MAX(created_at)      AS last_cooked
FROM cook_records
WHERE user_id     = 'u-001'
  AND created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
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
  AND date   = CURDATE()   -- 当天运势
LIMIT 1;

-- ============================================================
-- 【方向二】最近外卖决策 — 满意度趋势
-- ============================================================
-- 场景：分析用户外卖满意度，判断推荐质量
SELECT
    DATE(created_at)    AS decision_date,
    mood,
    final_choice,
    satisfaction,
    conversation_rounds,
    fortune_summary
FROM takeout_records
WHERE user_id    = 'u-002'
  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
ORDER BY created_at DESC;

-- 满意度统计（用于偏好学习权重调整）
SELECT
    satisfaction,
    COUNT(*) AS cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM takeout_records
WHERE user_id     = 'u-002'
  AND satisfaction != ''
GROUP BY satisfaction
ORDER BY cnt DESC;

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
        SUM(CASE WHEN dish_name LIKE '%辣%'
                 OR CAST(tags AS CHAR) LIKE '%辣%'
                 OR mood = '超好吃' THEN 1 ELSE 0 END) AS spicy_preference_score,
        -- 喜欢快手菜（标签含"快手菜" 或 cooking_time < 15）
        SUM(CASE WHEN CAST(tags AS CHAR) LIKE '%快手菜%'
                 OR cooking_time <= 15 THEN 1 ELSE 0 END) AS quick_meal_score,
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
        SUM(CASE WHEN satisfaction = '好吃' THEN 1 ELSE 0 END)       AS good_count,
        SUM(CASE WHEN satisfaction = '踩雷' THEN 1 ELSE 0 END)       AS bad_count,
        ROUND(AVG(conversation_rounds), 1)                           AS avg_rounds,
        SUM(CASE WHEN mood IN ('郁闷','焦虑','疲惫') THEN 1 ELSE 0 END) AS negative_mood_count
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
WITH RECURSIVE dates AS (
    SELECT DATE_SUB(CURDATE(), INTERVAL 7 DAY) AS d
    UNION ALL
    SELECT DATE_ADD(d, INTERVAL 1 DAY)
    FROM dates
    WHERE d < CURDATE()
)
SELECT
    -- 方向一
    COUNT(DISTINCT cr.id)                                 AS weekly_cook_count,
    COALESCE(SUM(cr.estimated_cost), 0)                   AS weekly_cook_cost,
    ROUND(AVG(cr.cooking_time), 0)                        AS avg_cooking_minutes,
    COUNT(DISTINCT CASE WHEN cr.mood = '超好吃' THEN cr.id END) AS great_meals,
    -- 方向二
    COUNT(DISTINCT tr.id)                                 AS weekly_takeout_decisions,
    COUNT(DISTINCT CASE WHEN tr.satisfaction = '好吃' THEN tr.id END)   AS good_decisions,
    COUNT(DISTINCT CASE WHEN tr.satisfaction = '踩雷' THEN tr.id END)   AS bad_decisions,
    -- 综合
    COUNT(DISTINCT cr.id) * 35 - COALESCE(SUM(cr.estimated_cost), 0)
        + COUNT(DISTINCT tr.id) * 5 AS total_saved_estimate   -- 外卖决策省5元(省了比价时间)
FROM dates d
LEFT JOIN cook_records    cr ON cr.user_id = 'u-001' AND DATE(cr.created_at) = d.d
LEFT JOIN takeout_records tr ON tr.user_id = 'u-001' AND DATE(tr.created_at) = d.d;

-- ============================================================
-- 【维护】数据清理 — 删除过期图片释放空间
-- ============================================================
-- 场景：清理30天前的照片（仅清理图片数据，保留文字记录）
UPDATE ingredients
SET photo_data = NULL
WHERE user_id   = 'u-001'
  AND created_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
  AND photo_data IS NOT NULL;

UPDATE cook_records
SET photo_url = NULL
WHERE user_id   = 'u-001'
  AND created_at < DATE_SUB(CURDATE(), INTERVAL 30 DAY)
  AND photo_url IS NOT NULL;

-- 统计清理后释放的行数
SELECT
    'ingredients'  AS table_name,
    COUNT(*)       AS cleaned_rows
FROM ingredients
WHERE user_id   = 'u-001'
  AND photo_data IS NULL
  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
UNION ALL
SELECT
    'cook_records' AS table_name,
    COUNT(*)       AS cleaned_rows
FROM cook_records
WHERE user_id   = 'u-001'
  AND photo_url IS NULL
  AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);

-- ============================================================
-- 查询索引使用建议（MySQL EXPLAIN ANALYZE）
-- ============================================================
-- 以下查询会用到对应索引，可用 EXPLAIN ANALYZE 验证执行计划：
--
-- SELECT * FROM ingredients WHERE user_id = 'u-001' AND status = 'available';
-- → 使用 idx_ingredients_status
--
-- SELECT * FROM cook_records WHERE user_id = 'u-001' ORDER BY created_at DESC LIMIT 20;
-- → 使用 idx_cook_user_date
--
-- SELECT * FROM daily_fortunes WHERE user_id = 'u-002' AND date = CURDATE();
-- → 使用 UNIQUE(user_id, date) 约束索引
--
-- SELECT * FROM shopping_items WHERE user_id = 'u-001' AND checked = FALSE;
-- → 使用 idx_shopping_user

-- ============================================================
-- 完成
-- ============================================================
SELECT '✅ MySQL practical queries ready!' AS status;
