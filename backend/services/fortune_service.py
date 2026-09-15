import json
from datetime import date

from sqlalchemy.orm import Session
from lunar_python import Solar

from models import DailyFortune, UserPreference
from schemas import FortuneResponse
from services.llm_service import llm_service

ZODIAC_BOUNDARIES = [
    (1, 20, "水瓶座"), (2, 19, "双鱼座"), (3, 21, "白羊座"),
    (4, 20, "金牛座"), (5, 21, "双子座"), (6, 22, "巨蟹座"),
    (7, 23, "狮子座"), (8, 23, "处女座"), (9, 23, "天秤座"),
    (10, 24, "天蝎座"), (11, 23, "射手座"), (12, 22, "摩羯座"),
]

CHINESE_ZODIAC = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]


def calc_zodiac(birth_date: date) -> tuple[str, str]:
    m, d = birth_date.month, birth_date.day
    zodiac = "摩羯座"
    for bm, bd, name in ZODIAC_BOUNDARIES:
        if (m > bm) or (m == bm and d >= bd):
            zodiac = name
    chinese_zodiac = CHINESE_ZODIAC[(birth_date.year - 4) % 12]
    return zodiac, chinese_zodiac


WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def build_almanac(d: date) -> dict:
    """用 lunar_python 构建真实历法数据：农历、节气时段、黄历宜忌。"""
    try:
        lunar = Solar.fromYmd(d.year, d.month, d.day).getLunar()
        prev_jq = lunar.getPrevJieQi()
        solar_term = prev_jq.getName() if prev_jq else ""
        yi = list(lunar.getDayYi() or [])
        ji = list(lunar.getDayJi() or [])
        if ji == ["无"]:
            ji = []
        return {
            "lunar_date": lunar.toString(),
            "solar_term": solar_term,
            "yi": yi[:6],
            "ji": ji[:6],
            "weekday": f"星期{WEEKDAY_CN[d.weekday()]}",
            "season": {3: "春", 4: "春", 5: "春", 6: "夏", 7: "夏", 8: "夏",
                       9: "秋", 10: "秋", 11: "秋", 12: "冬", 1: "冬", 2: "冬"}[d.month],
        }
    except Exception:
        return {
            "lunar_date": "", "solar_term": "", "yi": [], "ji": [],
            "weekday": f"星期{WEEKDAY_CN[d.weekday()]}", "season": "",
        }


class FortuneService:

    async def get_today_fortune(self, user_id: str, db: Session) -> FortuneResponse:
        today = date.today()
        existing = (
            db.query(DailyFortune)
            .filter(DailyFortune.user_id == user_id, DailyFortune.date == today)
            .first()
        )
        if existing:
            return self._to_response(existing, cached=True)

        prefs = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .first()
        )
        zodiac = prefs.zodiac if prefs and prefs.zodiac else "处女座"
        chinese_zodiac = (
            prefs.chinese_zodiac if prefs and prefs.chinese_zodiac else "蛇"
        )
        mbti = prefs.mbti if prefs and prefs.mbti else "INFP"

        fortune = await self._generate_fortune(user_id, zodiac, chinese_zodiac, mbti, db)
        return self._to_response(fortune, cached=False)

    async def _generate_fortune(
        self,
        user_id: str,
        zodiac: str,
        chinese_zodiac: str,
        mbti: str,
        db: Session,
    ) -> DailyFortune:
        alm = build_almanac(date.today())
        alm_desc = (
            f"今天是 {date.today()}（{alm['weekday']}·{alm['season']}季），"
            f"农历 {alm['lunar_date'] or '未知'}，"
            f"当前节气: {alm['solar_term'] or '无'}，"
            f"黄历宜: {'、'.join(alm['yi']) if alm['yi'] else '无特殊宜事'}，"
            f"黄历忌: {'、'.join(alm['ji']) if alm['ji'] else '无特殊禁忌'}"
        )
        prompt = (
            f"你是一个美食运势分析师。为以下用户生成今日美食运势。\n\n"
            f"星座: {zodiac}\n属相: {chinese_zodiac}\nMBTI: {mbti}\n{alm_desc}\n\n"
            f"要求：运势内容必须紧扣今天的农历日期、节气、季节和黄历宜忌，"
            f"体现'今日'的独特性（例如节气对应的时令食材、宜忌对应的饮食注意事项），"
            f"不要给出适用于任何一天的泛泛内容。\n\n"
            f"请返回JSON，格式如下：\n"
            f'{{"zodiac_fortune":"星座运势摘要","chinese_zodiac_fortune":"属相运势",'
            f'"mbti_energy":"MBTI能量关键词","food_keywords":["关键词1","关键词2","关键词3"],'
            f'"lucky_color":"幸运色","lucky_number":7,"lucky_food":"幸运食物",'
            f'"suggestion":"综合饮食建议(200字内)"}}'
        )
        messages = [
            {"role": "system", "content": "你是一个美食运势分析师，返回JSON格式数据。"},
            {"role": "user", "content": prompt},
        ]
        result = await llm_service.chat_completion(
            messages, temperature=0.8, response_format_json=True
        )

        try:
            data = json.loads(result["content"])
        except (json.JSONDecodeError, TypeError):
            data = self._fallback_fortune(zodiac, chinese_zodiac, mbti)

        fortune = DailyFortune(
            user_id=user_id,
            date=date.today(),
            zodiac=zodiac,
            chinese_zodiac=chinese_zodiac,
            mbti=mbti,
            zodiac_fortune=data.get("zodiac_fortune", ""),
            chinese_zodiac_fortune=data.get("chinese_zodiac_fortune", ""),
            mbti_energy=data.get("mbti_energy", ""),
            food_keywords=data.get("food_keywords", []),
            lucky_color=data.get("lucky_color", ""),
            lucky_number=data.get("lucky_number"),
            suggestion=data.get("suggestion", ""),
            lunar_date=alm["lunar_date"],
            solar_term=alm["solar_term"],
            yi=alm["yi"],
            ji=alm["ji"],
        )
        db.add(fortune)
        db.commit()
        db.refresh(fortune)
        return fortune

    def _fallback_fortune(self, zodiac: str, chinese_zodiac: str, mbti: str) -> dict:
        return {
            "zodiac_fortune": f"{zodiac}今日运势平稳，适合温暖的食物",
            "chinese_zodiac_fortune": f"属{chinese_zodiac}人今日宜静养，饮食以温热为主",
            "mbti_energy": f"{mbti}今日能量关键词：内省",
            "food_keywords": ["温暖", "热食", "暖胃"],
            "lucky_color": "暖橙",
            "lucky_number": 7,
            "lucky_food": "牛肉面",
            "suggestion": "今日运势建议选择温热暖胃的食物，避免生冷。",
        }

    def _to_response(self, fortune: DailyFortune, cached: bool) -> FortuneResponse:
        return FortuneResponse(
            id=fortune.id,
            date=fortune.date,
            zodiac=fortune.zodiac,
            chinese_zodiac=fortune.chinese_zodiac,
            mbti=fortune.mbti,
            food_keywords=fortune.food_keywords or [],
            lucky_color=fortune.lucky_color,
            lucky_number=fortune.lucky_number,
            lucky_food=self._extract_lucky_food(fortune),
            suggestion=fortune.suggestion,
            lunar_date=getattr(fortune, "lunar_date", "") or "",
            solar_term=getattr(fortune, "solar_term", "") or "",
            yi=getattr(fortune, "yi", None) or [],
            ji=getattr(fortune, "ji", None) or [],
            cached=cached,
        )

    def _extract_lucky_food(self, fortune: DailyFortune) -> str:
        keywords = fortune.food_keywords or []
        for kw in keywords:
            if any(c in kw for c in ["面", "饭", "菜", "汤", "粥", "鸡", "鱼", "肉"]):
                return kw
        return keywords[0] if keywords else "牛肉面"


fortune_service = FortuneService()
