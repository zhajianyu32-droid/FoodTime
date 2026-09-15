-- ============================================================
-- 美味出租屋 (MeiWeiChuZuWu) — 示例数据脚本（MySQL版）
-- 版本：v1.0 | 日期：2026-08-05
-- 转换自：02_seed_data.sql
-- 用途：开发/演示环境快速填充测试数据
-- 依赖：先执行 01_schema_mysql.sql 建表
-- ============================================================
USE meiweichuzuwu;

-- ============================================================
-- 1. 创建演示用户
-- ============================================================
INSERT INTO users (id, device_id, nickname, total_cook_count, total_takeout_count, streak_days) VALUES
('u-001', 'chrome-win-abc123', '小陈（深圳租房）', 12, 5, 7),
('u-002', 'chrome-mac-def456',  '小王（北京合租）', 0,  18, 5),
('u-003', 'safari-ios-ghi789',  '小李（上海单间）', 4,  8, 3);

-- ============================================================
-- 2. 用户偏好
-- ============================================================
INSERT INTO user_preferences (user_id, zodiac, mbti, chinese_zodiac, taste_preference, budget_level, cooking_skill, cookware, disliked_ingredients, liked_dishes, liked_takeout_categories, disliked_takeout_categories) VALUES
(
    'u-001',
    '天蝎座', 'ENFJ', '虎',
    '辣', '省钱', '一般',
    JSON_ARRAY('电磁炉','空气炸锅','电饭煲'),
    JSON_ARRAY('香菜','苦瓜'),
    JSON_ARRAY('西红柿炒鸡蛋','可乐鸡翅','蒜蓉西兰花','酸辣土豆丝'),
    JSON_ARRAY('川湘菜','麻辣烫','螺蛳粉'),
    JSON_ARRAY('沙拉轻食','日料刺身')
),
(
    'u-002',
    '双子座', 'INTP', '兔',
    '油腻', '正常', '新手',
    JSON_ARRAY(),
    JSON_ARRAY('内脏','臭豆腐'),
    JSON_ARRAY(),
    JSON_ARRAY('汉堡炸鸡','川湘菜','韩式料理','烧烤','麻辣香锅'),
    JSON_ARRAY('粥粉面','素食')
),
(
    'u-003',
    '处女座', 'ISTJ', '龙',
    '清淡', '吃好点', '一般',
    JSON_ARRAY('电磁炉','烤箱','微波炉'),
    JSON_ARRAY('青椒'),
    JSON_ARRAY('清蒸鲈鱼','白灼虾','番茄牛腩'),
    JSON_ARRAY('粤菜','日料','轻食沙拉'),
    JSON_ARRAY('麻辣烫','烧烤','油炸')
);

-- ============================================================
-- 3. 食材库存（小陈的冰箱）
-- ============================================================
INSERT INTO ingredients (user_id, name, category, quantity, expiry_date, confidence, source, status) VALUES
('u-001', '鸡蛋',     '肉蛋', '6个',   '2026-08-12', 1.0,  'photo',  'available'),
('u-001', '西红柿',   '蔬菜', '3个',   '2026-08-08', 0.95, 'photo',  'available'),
('u-001', '青菜',     '蔬菜', '1把',   '2026-08-06', 0.90, 'voice',  'available'),
('u-001', '猪肉',     '肉蛋', '半斤',  '2026-08-07', 0.85, 'photo',  'available'),
('u-001', '大米',     '主食', '5斤',   '2026-10-01', 1.0,  'manual', 'available'),
('u-001', '酱油',     '调料', '1瓶',   '2026-12-31', 1.0,  'manual', 'available'),
('u-001', '青椒',     '蔬菜', '2个',   '2026-08-09', 0.92, 'photo',  'available'),
('u-001', '豆腐',     '其他', '1盒',   '2026-08-06', 0.88, 'voice',  'available');

-- ============================================================
-- 4. 做饭日记（小陈的历史记录）
-- ============================================================
INSERT INTO cook_records (user_id, dish_name, mood, cooking_time, difficulty, estimated_cost, note, tags) VALUES
('u-001', '西红柿炒鸡蛋',   '超好吃', 10, '简单', 4.50,  '今天加班回来10分钟搞定，比外卖强多了',              JSON_ARRAY('快手菜','下饭')),
('u-001', '青椒肉丝',       '满足',   15, '简单', 8.00,  '第一次做，肉丝切得有点粗但味道不错',                JSON_ARRAY('下饭','家常菜')),
('u-001', '蒜蓉炒青菜',     '还行',    8, '简单', 3.00,  '青菜有点老了，下次买嫩一点的',                      JSON_ARRAY('快手菜','减脂')),
('u-001', '可乐鸡翅',       '超好吃', 25, '中等', 18.00, '周末犒劳自己！用空气炸锅做的，外酥里嫩',              JSON_ARRAY('周末大餐','下饭')),
('u-001', '蛋炒饭',         '还行',    5, '简单', 2.00,  '剩饭处理方案，加了火腿肠和葱花',                      JSON_ARRAY('快手菜','打扫冰箱')),
('u-001', '酸辣土豆丝',     '翻车了', 20, '中等', 5.00,  '土豆丝切太粗了像薯条…而且醋放多了好酸',              JSON_ARRAY('翻车记录')),
('u-001', '豆腐青菜汤',     '满足',   12, '简单', 3.50,  '下雨天喝碗热汤太舒服了',                              JSON_ARRAY('汤品','快手菜')),
('u-001', '红烧肉',         '超好吃', 45, '挑战', 25.00, '花了45分钟但值了！肥而不腻，一口气吃了两碗饭',        JSON_ARRAY('周末大餐','下饭','硬菜'));

-- ============================================================
-- 5. 每日运势（供外卖日记引用）
-- ============================================================
INSERT INTO daily_fortunes (id, user_id, date, zodiac, chinese_zodiac, mbti, food_keywords, suggestion, zodiac_fortune, chinese_zodiac_fortune, mbti_energy) VALUES
('f-001', 'u-002', '2026-07-28', '双子座', '兔', 'INTP',
 JSON_ARRAY('温暖治愈','面食','热汤'),
 '今天双子座情绪波动较大，INTP的你习惯用理性压制情绪。属相兔今日宜静不宜动。综合来看，适合一份温暖的面食来安抚内心的躁动。',
 '今日守护星水星逆行，沟通易生误会。饮食建议：避免生冷刺激，选择温和滋补的食物。',
 '属兔人今日运势平稳，宜保持低调，不宜做重大决定。饮食上宜热食忌生冷，肠胃较为敏感。',
 'INTP今日能量关键词：内省。适合独处，给自己一个安静的空间整理思绪。'),

('f-002', 'u-002', '2026-07-29', '双子座', '兔', 'INTP',
 JSON_ARRAY('冒险尝试','辣味','新奇'),
 '水逆结束！今天双子座的能量回升，适合尝试新事物。属相兔宜突破舒适区。INTP的好奇心今天会带你发现惊喜。',
 '水逆正式结束，沟通运回升。宜尝试新菜系、新口味，可能会有意外惊喜。',
 '属兔人今日宜突破常规。尝试一些平时不吃的菜系，味蕾会给你正面的回馈。',
 'INTP今日能量关键词：探索。好奇心爆棚的一天，适合尝试新鲜事物。'),

('f-003', 'u-002', '2026-08-01', '双子座', '兔', 'INTP',
 JSON_ARRAY('犒赏自己','肉食','仪式感'),
 '发薪日！双子座的社交能量满格。属相兔今日财运不错。INTP值得一顿有仪式感的大餐来奖励自己。',
 '今日双子社交运旺盛，适合聚会。饮食上适合分享型美食，和朋友一起会更开心。',
 '属兔人今日财运佳，小有进账。饮食上可以稍微奢侈一把。',
 'INTP今日能量关键词：犒赏。你最近太拼了，今天给自己一顿好吃的。'),

('f-004', 'u-002', '2026-08-03', '双子座', '兔', 'INTP',
 JSON_ARRAY('清爽','轻食','高蛋白'),
 '今天双子座精力充沛但容易浮躁。属相兔宜养心。INTP需要补充蛋白质来支撑高强度思考。',
 '双子今日精力旺盛但易分心。饮食建议清爽不油腻，避免饭后犯困。',
 '属兔人宜养心静气，饮食上以清淡高蛋白为主。',
 'INTP今日能量关键词：专注。需要高蛋白食物支撑大脑运转。');

-- ============================================================
-- 6. 外卖决策记录
-- ============================================================
INSERT INTO takeout_records (user_id, fortune_id, mood, fortune_summary, fortune_keywords, final_choice, choice_reason, conversation_rounds, satisfaction) VALUES
('u-002', 'f-001', '郁闷',
 '今日双子座守护星水逆，情绪波动大，适合温暖的面食安抚内心。',
 JSON_ARRAY('温暖治愈','面食','热汤'),
 '日式豚骨拉面',
 '水逆天就应该来一碗热腾腾的拉面，溏心蛋戳破的瞬间所有烦恼都消失了',
 3, '好吃'),

('u-002', 'f-002', '兴奋',
 '水逆结束！双子座能量回升，适合尝试新事物。',
 JSON_ARRAY('冒险尝试','辣味','新奇'),
 '川渝麻辣香锅',
 'AI说今天适合冒险尝试，果然没错！第一次吃麻辣香锅，辣到流泪但好爽',
 4, '好吃'),

('u-002', 'f-003', '开心',
 '发薪日！双子社交运旺，适合犒赏自己的仪式感大餐。',
 JSON_ARRAY('犒赏自己','肉食','仪式感'),
 '韩式烤肉拌饭',
 '发薪日就该犒劳自己！运势说今天适合仪式感，烤肉拌饭配冰可乐=完美',
 2, '好吃'),

('u-002', 'f-004', '疲惫',
 '双子座精力充沛但易浮躁，需高蛋白支撑高强度思考。',
 JSON_ARRAY('清爽','轻食','高蛋白'),
 '鸡胸肉藜麦沙拉碗',
 '加了一天班脑子要炸了…AI推荐轻食挺靠谱的，吃完不犯困',
 2, '一般'),

('u-002', NULL, '嘴馋',
 '',
 JSON_ARRAY('油炸','快乐'),
 '韩式炸鸡',
 '没什么特别的理由，就是馋了。AI问了一圈最后确认了我就是想吃炸鸡',
 3, '好吃');

-- ============================================================
-- 7. AI 对话记录（关联第一条外卖记录：日式豚骨拉面）
-- ============================================================
INSERT INTO chat_turns (takeout_id, turn, role, content, ai_guess, ai_confidence)
SELECT id, 1, 'ai',
       '你今天心情有点郁闷，运势关键词是"温暖治愈"。我猜你可能想来一碗热腾腾的拉面？',
       '日式拉面', 0.65
FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1;

INSERT INTO chat_turns (takeout_id, turn, role, content, ai_guess, ai_confidence)
SELECT id, 2, 'user',
       '嗯…不太想吃面，还有别的吗？',
       NULL, NULL
FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1;

INSERT INTO chat_turns (takeout_id, turn, role, content, ai_guess, ai_confidence)
SELECT id, 3, 'ai',
       '了解~ 那热乎的米饭类呢？比如一份肥牛饭或者煲仔饭，汤汁拌饭那种满足感？',
       '肥牛饭/煲仔饭', 0.72
FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1;

INSERT INTO chat_turns (takeout_id, turn, role, content, ai_guess, ai_confidence)
SELECT id, 4, 'user',
       '还是想吃汤汤水水的…就拉面吧！',
       NULL, NULL
FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1;

INSERT INTO chat_turns (takeout_id, turn, role, content, ai_guess, ai_confidence)
SELECT id, 5, 'ai',
       '好嘞！🎉 日式豚骨拉面——溏心蛋戳破的瞬间所有烦恼都消失了。打开外卖App搜「日式拉面」或「豚骨拉面」就能找到。水逆天就该对自己好一点~',
       '日式豚骨拉面', 0.92
FROM takeout_records WHERE user_id = 'u-002' ORDER BY created_at LIMIT 1;

-- ============================================================
-- 8. 购物清单（小陈的待购清单）
-- ============================================================
INSERT INTO shopping_items (user_id, name, category, quantity, checked, source_recipe) VALUES
('u-001', '葱花',   '蔬菜', '1小把', 0, '所有需要葱花的菜'),
('u-001', '姜',     '蔬菜', '1块',   0, '红烧肉'),
('u-001', '鸡翅',   '肉蛋', '1斤',   0, '可乐鸡翅'),
('u-001', '可乐',   '其他', '1瓶',   0, '可乐鸡翅'),
('u-001', '土豆',   '蔬菜', '2个',   1, '酸辣土豆丝');

-- ============================================================
-- 9. 验证数据
-- ============================================================
SELECT '========================================' AS '';
SELECT '✅ 示例数据插入完成！' AS '';
SELECT '========================================' AS '';
SELECT CONCAT('  用户：      ', COUNT(*), ' 条') FROM users;
SELECT CONCAT('  用户偏好：  ', COUNT(*), ' 条') FROM user_preferences;
SELECT CONCAT('  食材库存：  ', COUNT(*), ' 条') FROM ingredients;
SELECT CONCAT('  做饭日记：  ', COUNT(*), ' 条') FROM cook_records;
SELECT CONCAT('  外卖日记：  ', COUNT(*), ' 条') FROM takeout_records;
SELECT CONCAT('  每日运势：  ', COUNT(*), ' 条') FROM daily_fortunes;
SELECT CONCAT('  对话记录：  ', COUNT(*), ' 条') FROM chat_turns;
SELECT CONCAT('  购物清单：  ', COUNT(*), ' 条') FROM shopping_items;
SELECT '========================================' AS '';
