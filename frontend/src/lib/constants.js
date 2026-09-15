// Onboarding 枚举常量 — 与后端 schemas.py 保持一致

export const TASTE_OPTIONS = ['辣','甜','酸','咸','清淡','油腻','清爽','都行']
export const COOKWARE_OPTIONS = ['炒锅','蒸锅','电饭煲','微波炉','烤箱','空气炸锅','电煮锅','高压锅','平底锅','汤锅']
export const MBTI_GROUPS = [
  { label: '分析家 NT', items: ['INTJ','INTP','ENTJ','ENTP'] },
  { label: '外交家 NF', items: ['INFJ','INFP','ENFJ','ENFP'] },
  { label: '守护者 SJ', items: ['ISTJ','ISFJ','ESTJ','ESFJ'] },
  { label: '探险家 SP', items: ['ISTP','ISFP','ESTP','ESFP'] },
]
export const BUDGET_OPTIONS = ['0~15','16~25','26~50','51~100','101~150','151~200','201及以上']
export const COOKING_SKILL_OPTIONS = [
  '完全不会','会烧水/泡面','会煮面条/粥','一般会做点（炒简单菜）',
  '熟练（能做一桌家常菜）','精通（会做复杂硬菜）','专业水平（可媲美厨师）','厨师/餐饮从业者',
]
export const CUISINE_OPTIONS = [
  '川菜','粤菜','鲁菜','苏菜','浙菜','闽菜','湘菜','徽菜',
  '东北菜','西北菜','云南菜','贵州菜','新疆菜','西藏菜','北京菜','上海菜',
  '广东早茶','港式茶餐','日式','韩式','东南亚','意式','法式','美式','墨西哥','中东','其他菜系',
]
export const CATEGORIES = ['蔬菜','肉蛋','水产','主食','调料','乳制品','其他']
export const CATEGORY_ICONS = { '蔬菜':'🥬','肉蛋':'🥩','水产':'🐟','主食':'🍚','调料':'🧂','乳制品':'🥛','其他':'📦' }
// 分类默认保质期（天）— 常识值，用户可自定义覆盖
export const CATEGORY_SHELF_DAYS = {
  '蔬菜': 5,     // 叶菜类3-7天，根茎类7-14天，平均取5
  '肉蛋': 14,    // 鸡蛋30天，鲜肉3天，平均取14（兼顾）
  '水产': 2,     // 新鲜鱼1-3天，平均2
  '主食': 120,   // 米面90-180天
  '调料': 180,   // 6-12个月
  '乳制品': 10,  // 牛奶7天，酸奶14天，平均10
  '其他': 14,
}
export function getShelfDays(category) {
  return CATEGORY_SHELF_DAYS[category] ?? 14
}

// 食材名→分类 关键词映射（用于自动推断分类）
// 按类别分组，匹配时优先长词（避免"牛肉"被"牛"误匹配）
const _INGREDIENT_CATEGORY_KEYWORDS = [
  { cat: '肉蛋', words: ['牛肉','猪肉','羊肉','鸡肉','鸭肉','鹅肉','兔肉','马肉','牛腩','里脊','五花肉','排骨','猪蹄','鸡爪','鸡翅','鸡腿','鸡胸','鹅肝','羊排','牛排','牛腱','肥牛','肥羊','培根','香肠','腊肉','火腿','午餐肉','鸭血','毛肚','百叶','黄喉','肥肠','肘子','鸡蛋','鸭蛋','鹌鹑蛋','皮蛋','咸蛋','松花蛋','牛肉丸','鱼丸','虾丸','猪肝','猪心','猪脑','猪肚'] },
  { cat: '水产', words: ['鱼','虾','蟹','贝','牡蛎','生蚝','花蛤','蛏子','鲍鱼','鱿鱼','章鱼','墨鱼','海螺','海参','海蜇','带鱼','鲈鱼','三文鱼','金枪鱼','鳕鱼','黄花鱼','鳗鱼','秋刀鱼','沙丁鱼','河豚','鲫鱼','草鱼','鲤鱼','基围虾','小龙虾','皮皮虾','螃蟹','梭子蟹','帝王蟹','河虾','对虾','明虾','干贝','瑶柱','鱼肉','鱼片'] },
  { cat: '蔬菜', words: ['番茄','西红柿','黄瓜','茄子','苦瓜','冬瓜','南瓜','丝瓜','西葫芦','青椒','彩椒','菠菜','油麦菜','生菜','白菜','娃娃菜','空心菜','韭菜','芹菜','香菜','茼蒿','上海青','芥蓝','土豆','胡萝卜','白萝卜','红薯','山药','藕','芋头','洋葱','生姜','大蒜','菌菇','香菇','平菇','金针菇','杏鲍菇','木耳','银耳','口蘑','茶树菇','草菇','鸡腿菇','豌豆','豆角','四季豆','荷兰豆','毛豆','蚕豆','扁豆','西兰花','菜花','卷心菜','甘蓝','苦菊','菜心','芥兰','茭白','竹笋'] },
  { cat: '主食', words: ['米饭','糯米','黑米','糙米','小米','面条','馒头','包子','饺子','烙饼','手抓饼','面包','吐司','米粉','米线','方便面','挂面','馄饨','烧卖','粽子','汤圆','年糕','燕麦','玉米','藜麦','绿豆','红豆','黑豆','黄豆','花生','芝麻','腰果','核桃','杏仁','开心果','巴旦木','栗子','榛子','松子','板栗','面粉'] },
  { cat: '调料', words: ['盐','酱油','醋','糖','味精','鸡精','蚝油','生抽','老抽','料酒','橄榄油','香油','花生油','菜籽油','食用油','豆瓣酱','黄豆酱','甜面酱','辣椒酱','番茄酱','辣椒粉','花椒','胡椒','芥末','咖喱','麻椒','八角','桂皮','孜然','陈皮','小茴香','香叶','丁香','肉蔻','草果','白芷','干姜','干辣椒','花椒粉','胡椒粉','淀粉','生粉'] },
  { cat: '乳制品', words: ['牛奶','羊奶','酸奶','奶酪','黄油','芝士','炼乳','奶油','奶粉','舒化奶','高钙奶','脱脂奶','全脂奶','奶酪片','奶酪块','马苏里拉','帕玛森'] },
]

// 根据食材名推断分类，返回分类名；无法推断时返回 null
export function guessCategory(name) {
  if (!name) return null
  const n = name.trim()
  // 按关键词长度降序匹配，优先匹配长词（如"牛肉"先于"牛"）
  let bestMatch = { len: 0, cat: null }
  for (const group of _INGREDIENT_CATEGORY_KEYWORDS) {
    for (const w of group.words) {
      if (n.includes(w) && w.length > bestMatch.len) {
        bestMatch = { len: w.length, cat: group.cat }
      }
    }
  }
  return bestMatch.cat
}
export const CAT_CLASS = {
  '蔬菜':'veg','肉蛋':'meat','水产':'seafood','主食':'staple','调料':'condiment','乳制品':'dairy','其他':'other',
}

export const DISLIKED_TREE = [
  { name:'蔬菜', children:[
    { name:'叶菜类', children:['菠菜','油麦菜','生菜','白菜','娃娃菜','空心菜','韭菜','芹菜','香菜','茼蒿','上海青','芥蓝'] },
    { name:'根茎类', children:['土豆','胡萝卜','白萝卜','红薯','山药','藕','芋头','洋葱','生姜','大蒜'] },
    { name:'瓜茄类', children:['西红柿','黄瓜','茄子','苦瓜','冬瓜','南瓜','丝瓜','西葫芦','青椒','彩椒'] },
    { name:'菌菇类', children:['香菇','平菇','金针菇','杏鲍菇','木耳','银耳','口蘑','茶树菇','草菇','鸡腿菇'] },
    { name:'豆荚类', children:['豌豆','豆角','四季豆','荷兰豆','毛豆','蚕豆','扁豆'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'肉蛋', children:[
    { name:'畜肉', children:['猪肉','牛肉','羊肉','驴肉','马肉','培根','香肠','腊肉','火腿','午餐肉'] },
    { name:'禽肉', children:['鸡肉','鸭肉','鹅肉','鸽子肉','鸡翅','鸡爪','鸭脖','内脏类'] },
    { name:'内脏/加工', children:['猪肝','猪心','猪脑','鸭血','毛肚','百叶','黄喉','肥肠','肘子','猪蹄'] },
    { name:'蛋/奶', children:['鸡蛋','鸭蛋','鹌鹑蛋','皮蛋','咸蛋','牛奶','羊奶','酸奶','奶酪','黄油'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'水产海鲜', children:[
    { name:'鱼类', children:['草鱼','鲤鱼','鲫鱼','带鱼','鲈鱼','三文鱼','金枪鱼','鳕鱼','黄花鱼','鳗鱼','秋刀鱼','沙丁鱼','河豚'] },
    { name:'虾蟹', children:['大虾','基围虾','小龙虾','皮皮虾','螃蟹','梭子蟹','帝王蟹','河虾'] },
    { name:'贝类/软体', children:['扇贝','生蚝','花蛤','蛏子','鲍鱼','鱿鱼','章鱼','墨鱼','海螺','海参','海蜇'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'主食/谷物', children:[
    { name:'米类', children:['米饭','糯米','黑米','糙米','小米'] },
    { name:'面类', children:['面条','馒头','包子','饺子','烙饼','手抓饼','面包','吐司','米粉','米线','方便面'] },
    { name:'杂粮/豆', children:['燕麦','玉米','藜麦','绿豆','红豆','黑豆','黄豆','花生','芝麻'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'调料/辛香', children:[
    { name:'基础调味', children:['盐','酱油','醋','糖','味精','鸡精','蚝油','生抽','老抽','料酒','豆瓣酱'] },
    { name:'辛辣刺激', children:['辣椒','花椒','胡椒','芥末','咖喱','麻椒','八角','桂皮','孜然','香菜','大蒜','韭菜','葱'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'水果/坚果', children:[
    { name:'水果', children:['苹果','香蕉','橙子','橘子','葡萄','西瓜','桃子','草莓','芒果','菠萝','柠檬','猕猴桃','榴莲','火龙果','梨','柿子'] },
    { name:'坚果', children:['核桃','杏仁','腰果','开心果','夏威夷果','巴旦木','栗子','榛子','松子'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'饮品/甜品', children:[
    { name:'饮品', children:['奶茶','咖啡','可乐','碳酸饮料','豆浆','果汁','啤酒','白酒','红酒','茶'] },
    { name:'甜食', children:['蛋糕','巧克力','冰淇淋','糖果','布丁','蛋挞','饼干','月饼','汤圆','年糕'] },
    { name:'其他', __custom:true, children:[] },
  ]},
  { name:'其他', children:[
    { name:'过敏原', children:['花生','坚果','海鲜','牛奶','鸡蛋','麸质/小麦','大豆','芒果','菠萝','猕猴桃'] },
    { name:'宗教/习俗', children:['猪肉','牛肉','羊肉','五辛','动物血','酒精','所有肉类（素食）'] },
    { name:'其他', __custom:true, children:[] },
  ]},
]

// 星座/属相计算 — 与后端 calc_zodiac 边界递进法一致
const _ZODIAC_BOUNDARIES = [
  [1,20,'水瓶座'], [2,19,'双鱼座'], [3,21,'白羊座'],
  [4,20,'金牛座'], [5,21,'双子座'], [6,22,'巨蟹座'],
  [7,23,'狮子座'], [8,23,'处女座'], [9,23,'天秤座'],
  [10,24,'天蝎座'], [11,23,'射手座'], [12,22,'摩羯座'],
]
const _CHINESE_ZODIAC = ['鼠','牛','虎','兔','龙','蛇','马','羊','猴','鸡','狗','猪']

export function calcZodiacFromBirth(dateStr) {
  if (!dateStr) return { zodiac: '', chinese: '' }
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(dateStr)
  if (!m) return { zodiac: '', chinese: '' }
  const y = +m[1], mo = +m[2], d = +m[3]
  let zodiac = '摩羯座'
  for (const [bm, bd, name] of _ZODIAC_BOUNDARIES) {
    if ((mo > bm) || (mo === bm && d >= bd)) zodiac = name
  }
  const chiIdx = ((y - 4) % 12 + 12) % 12
  return { zodiac, chinese: _CHINESE_ZODIAC[chiIdx] }
}

// 计算食材的实际过期日期：优先用显式 expiry_date，否则用 created_at + shelf_days（或分类默认）
export function computeExpiryDate(ing) {
  if (ing.expiry_date) return ing.expiry_date
  const days = ing.shelf_days || getShelfDays(ing.category)
  if (!days || !ing.created_at) return null
  const created = new Date(ing.created_at)
  created.setDate(created.getDate() + days)
  return created.toISOString().slice(0, 10)
}

export function isExpiring(ing) {
  const exp = computeExpiryDate(ing)
  if (!exp) return false
  const d = new Date(exp + 'T00:00:00')
  const now = new Date(); now.setHours(0, 0, 0, 0)
  const diff = Math.ceil((d - now) / 86400000)
  return diff >= 0 && diff <= 3
}

export function daysLeft(ing) {
  const exp = computeExpiryDate(ing)
  if (!exp) return '-'
  const d = new Date(exp + 'T00:00:00')
  const now = new Date(); now.setHours(0, 0, 0, 0)
  return Math.ceil((d - now) / 86400000)
}

export function formatDate(s) {
  return s ? String(s).replace('T', ' ').slice(0, 16) : '-'
}

export function parseCost(s) {
  if (!s) return 0
  const m = String(s).match(/[\d.]+/)
  return m ? parseFloat(m[0]) : 0
}

export function toggleArr(arr, v) {
  const i = arr.indexOf(v)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(v)
}

export function removeArr(arr, v) {
  const i = arr.indexOf(v)
  if (i >= 0) arr.splice(i, 1)
}
