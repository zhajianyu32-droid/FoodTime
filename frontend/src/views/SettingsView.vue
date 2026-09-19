<script setup>
import { computed, onMounted, ref, reactive, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectGroup, SelectLabel } from '@/components/ui/select'
import { me, logout } from '@/composables/useAuth'
import { pwdForm, changePassword, onboarding, onboardingLoading, onboardingSaving, liveZodiac, liveChinese, mbtiSelect, loadOnboarding, saveOnboarding, dislikeTreePathKey, countDislikedInL1, countDislikedInL2, addCustomDisliked, removeCustomDisliked, addCustomCuisine, toggleArr, removeArr } from '@/composables/useSettings'
import { showToast } from '@/composables/useToast'
import { TASTE_OPTIONS, COOKWARE_OPTIONS, BUDGET_OPTIONS, COOKING_SKILL_OPTIONS, CUISINE_OPTIONS, MBTI_GROUPS, DISLIKED_TREE } from '@/lib/constants'
import { useRouter } from 'vue-router'

const router = useRouter()
const customInputs = ref({})
const dislikedTreeReady = computed(() => !onboardingLoading.value)

// ---- 忌口树展开状态（Q13-a：紧凑分类网格）----
// 用单个 activeDislikeL1 记录当前展开的一级分类索引；null 表示全部收起。
// 默认自动选中「首个已有忌口的分类」，让用户一眼看到自己设过的忌口（Q8-c 意图）。
const defaultActiveL1 = computed(() => {
  for (let i = 0; i < DISLIKED_TREE.length; i++) {
    if (countDislikedInL1(DISLIKED_TREE[i]) > 0) return i
  }
  return null
})
const activeDislikeL1 = ref(null)
const activeDislikeL2 = ref(null)
// 数据加载完成后同步一次默认选中（避免在数据未到达时算错）
watch(dislikedTreeReady, (ready) => {
  if (ready) activeDislikeL1.value = defaultActiveL1.value
})
// 切换一级分类时重置二级选中，避免残留旧索引导致渲染错位
watch(activeDislikeL1, () => { activeDislikeL2.value = null })
function toggleDislikeL1(i) {
  activeDislikeL1.value = activeDislikeL1.value === i ? null : i
}

function handleAddCustom(L1, L2) {
  const key = dislikeTreePathKey(L1.name, L2.name)
  const val = customInputs.value[key] || ''
  // 注意：useSettings.addCustomDisliked 内部用 dislikeTreePathKey(L1, L2) 拼接键，
  // 因此此处传入字符串名而非对象，确保键与 count/remove 一致。
  addCustomDisliked(L1.name, L2.name, val)
  customInputs.value[key] = ''
}

function doLogout() {
  logout()
  showToast('已退出登录')
  router.push('/login')
}

// ---- 账户资料编辑 ----
const profileEditing = ref(false)
const profileForm = reactive({ nickname: '', phone: '', saving: false, error: '' })

function startProfileEdit() {
  profileForm.nickname = me.value?.nickname || ''
  profileForm.phone = me.value?.phone || ''
  profileForm.error = ''
  profileEditing.value = true
}

function cancelProfileEdit() { profileEditing.value = false }

async function saveProfile() {
  profileForm.error = ''
  const phone = profileForm.phone.trim()
  if (phone && !/^1[3-9]\d{9}$/.test(phone)) { profileForm.error = '手机号格式不正确'; return }
  profileForm.saving = true
  try {
    await api('/auth/profile', {
      method: 'PATCH',
      body: { nickname: profileForm.nickname.trim(), phone: phone },
    })
    await reloadMe()
    profileEditing.value = false
    showToast('资料已更新 ✓')
  } catch (e) { profileForm.error = e.message }
  finally { profileForm.saving = false }
}

async function submitChangePassword() {
  const ok = await changePassword()
  if (ok) {
    // changePassword 内部已安排 1.8s 后清 Token + 清 me.value，这里仅做兜底路由
    setTimeout(() => router.push('/login'), 2200)
  }
}

onMounted(() => { if (me.value) loadOnboarding() })
</script>

<template>
  <!--
    1080p 一屏布局策略（Q1/Q2/Q4/Q5/Q10 共识）：
    - md 及以上：外层 main 自带 md:overflow-hidden，页面若不自带滚动能力，溢出内容会被静默裁掉。
      故此处给页面自身 md:overflow-y-auto，并用 [&::-webkit-scrollbar]:hidden + scrollbar-width:none
      隐藏滚动条，做到「视觉无滚动条、内容仍可达」（Q2-a 的技术落点）。
    - 视口高 ≥960px（1080p 主场景）：改为 overflow-hidden，严格无滚动（Q10-b）；
      实测 1920×1080 下三卡总高约 893px，可完整容纳并留余量。
    - 视口高 <960px（1600×900、1366×768 等笔记本）：保留 auto，允许滚动兜底，避免内容被裁且无法滚动。
      阈值取 960 而非 900：实测内容高 893px，若阈值 900 则 1600×900 恰好命中 hidden 却装不下，
      会形成「被裁且不可滚动」的最差中间态。
    - md 以下：交回文档流，正常纵向滚动。
    注：这里要按「高度」做媒体查询，必须用任意变体 [@media(min-height:960px)]:；
    min-[900px]: 是按宽度，min-h-[900px]: 会被解析成 min-height 工具类，两者都不对。
    另：滚动容器必须用 max-h-full（而非 h-full）—— 用 h-full 会把高度锁死，
    scrollHeight 恒等于 clientHeight，overflow-y-auto 就永远不会滚动。
  -->
  <div class="bg-background p-3 md:p-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] md:max-h-full md:overflow-y-auto [@media(min-height:960px)]:md:overflow-hidden">
    <div class="w-full max-w-[1180px] mx-auto md:flex md:flex-col md:gap-3">
      <!-- Page header（Q9-a：压缩为单行） -->
      <div class="md:shrink-0 flex items-baseline gap-3">
        <h1 class="text-xl md:text-2xl font-bold">⚙️ 个人设置</h1>
        <span class="text-xs md:text-sm text-muted-foreground">管理账户、密码与个人饮食偏好档案</span>
      </div>

      <!-- 账户信息 + 修改密码 并排（Q6-a） -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 md:shrink-0 items-start">
        <!-- Account info card -->
        <Card class="gap-3 py-4">
          <CardHeader class="px-4">
            <div class="flex items-center justify-between gap-2">
              <div>
                <CardTitle class="text-base">账户信息</CardTitle>
                <CardDescription class="text-xs">你的账户基本资料</CardDescription>
              </div>
              <div class="flex items-center gap-1.5">
                <Button v-if="!profileEditing" variant="outline" size="sm" @click="startProfileEdit">编辑资料</Button>
                <Button variant="outline" size="sm" @click="doLogout">退出登录</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent class="px-4">
            <!-- 编辑模式 -->
            <div v-if="profileEditing" class="space-y-3">
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div class="space-y-1.5">
                  <Label for="pf-nickname">昵称</Label>
                  <Input id="pf-nickname" v-model="profileForm.nickname" maxlength="30" placeholder="输入昵称" class="h-8" />
                </div>
                <div class="space-y-1.5">
                  <Label for="pf-phone">手机号</Label>
                  <Input id="pf-phone" v-model="profileForm.phone" maxlength="20" placeholder="留空表示解绑" class="h-8" />
                </div>
              </div>
              <p v-if="profileForm.error" class="text-sm text-destructive">{{ profileForm.error }}</p>
              <div class="flex justify-end gap-2">
                <Button variant="ghost" size="sm" :disabled="profileForm.saving" @click="cancelProfileEdit">取消</Button>
                <Button size="sm" :disabled="profileForm.saving" @click="saveProfile">
                  {{ profileForm.saving ? '保存中…' : '保存' }}
                </Button>
              </div>
            </div>
            <!-- 展示模式 -->
            <div v-else class="grid grid-cols-2 gap-y-2.5 gap-x-4 text-sm">
              <div>
                <p class="text-xs text-muted-foreground">用户名</p>
                <p class="font-medium">{{ me?.username || '-' }}</p>
              </div>
              <div>
                <p class="text-xs text-muted-foreground">用户 ID</p>
                <p class="font-mono text-xs break-all">{{ me?.user_id || me?.id || '-' }}</p>
              </div>
              <div>
                <p class="text-xs text-muted-foreground">手机号</p>
                <p class="font-medium">{{ me?.phone || '未绑定' }}</p>
              </div>
              <div>
                <p class="text-xs text-muted-foreground">注册时间</p>
                <p class="font-medium">{{ me?.created_at ? String(me.created_at).slice(0, 16).replace('T', ' ') : '-' }}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Change password card -->
        <Card class="gap-3 py-4">
          <CardHeader class="px-4">
            <CardTitle class="text-base">修改密码</CardTitle>
            <CardDescription class="text-xs">修改成功后立即失效所有现有 Token，需重新登录</CardDescription>
          </CardHeader>
          <CardContent class="px-4 space-y-2.5">
            <div class="space-y-1">
              <Label for="pwd-old" class="text-xs">原密码</Label>
              <Input
                id="pwd-old"
                type="password"
                v-model="pwdForm.old"
                autocomplete="current-password"
                placeholder="请输入当前密码"
                class="h-8"
              />
            </div>
            <div class="space-y-1">
              <Label for="pwd-new" class="text-xs">新密码</Label>
              <Input
                id="pwd-new"
                type="password"
                v-model="pwdForm.pwd"
                autocomplete="new-password"
                placeholder="至少 6 位"
                class="h-8"
              />
            </div>
            <div class="space-y-1">
              <Label for="pwd-new2" class="text-xs">确认新密码</Label>
              <Input
                id="pwd-new2"
                type="password"
                v-model="pwdForm.pwd2"
                autocomplete="new-password"
                placeholder="再次输入新密码"
                class="h-8"
                v-safe-enter="submitChangePassword"
              />
            </div>
            <p v-if="pwdForm.error" class="text-xs text-destructive">{{ pwdForm.error }}</p>
            <p v-if="pwdForm.success" class="text-xs text-green-600">{{ pwdForm.success }}</p>
            <div class="flex justify-end">
              <Button size="sm" :disabled="pwdForm.loading || pwdForm.changed" @click="submitChangePassword">
                {{ pwdForm.loading ? '提交中…' : (pwdForm.changed ? '已修改，请重新登录' : '修改密码') }}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Onboarding card（Q7-a：字段多列网格 + chips 紧凑 + 去分隔线） -->
      <Card class="gap-3 py-4 md:shrink-0">
        <CardHeader class="px-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle class="text-base">偏好档案</CardTitle>
              <CardDescription class="text-xs">记录口味偏好、烹饪条件与忌口，让 AI 更懂你</CardDescription>
            </div>
            <div class="flex flex-wrap items-center gap-1.5">
              <Badge v-if="onboarding.completed" variant="default">已完善</Badge>
              <Badge v-else variant="secondary">未完善</Badge>
              <Badge v-if="liveZodiac" variant="outline">{{ liveZodiac }}</Badge>
              <Badge v-if="liveChinese" variant="outline">属{{ liveChinese }}</Badge>
              <Badge v-if="onboarding.mbti" variant="outline">{{ onboarding.mbti }}</Badge>
              <Badge v-if="onboarding.cuisines && onboarding.cuisines.length" variant="outline">
                {{ onboarding.cuisines.length }} 菜系
              </Badge>
              <Badge variant="outline">忌口 {{ onboarding.disliked_ingredients.length }}</Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent v-if="onboardingLoading" class="text-center text-sm text-muted-foreground py-6">
          加载偏好档案中…
        </CardContent>

        <CardContent v-else class="px-4 space-y-3">
          <!-- 短字段 4 列网格：出生日期 / MBTI / 预算 / 烹饪水平 -->
          <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div class="space-y-1">
              <Label for="ob-birth" class="text-xs">出生日期</Label>
              <Input id="ob-birth" type="date" v-model="onboarding.birth_date" class="h-8 text-xs" />
              <div class="flex items-center gap-1">
                <Badge v-if="liveZodiac" variant="secondary" class="text-[10px]">{{ liveZodiac }}</Badge>
                <Badge v-if="liveChinese" variant="secondary" class="text-[10px]">属{{ liveChinese }}</Badge>
              </div>
            </div>

            <div class="space-y-1">
              <Label class="text-xs">MBTI 性格类型</Label>
              <Select v-model="mbtiSelect">
                <SelectTrigger size="sm" class="w-full"><SelectValue placeholder="选填" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不填</SelectItem>
                  <SelectGroup v-for="g in MBTI_GROUPS" :key="g.label">
                    <SelectLabel>{{ g.label }}</SelectLabel>
                    <SelectItem v-for="m in g.items" :key="m" :value="m">{{ m }}</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-1">
              <Label class="text-xs">每餐预算（元）</Label>
              <Select v-model="onboarding.budget_level">
                <SelectTrigger size="sm" class="w-full"><SelectValue placeholder="选择预算" /></SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="b in BUDGET_OPTIONS" :key="b" :value="b">{{ b }} 元</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-1">
              <Label class="text-xs">烹饪水平</Label>
              <Select v-model="onboarding.cooking_skill">
                <SelectTrigger size="sm" class="w-full"><SelectValue placeholder="选择水平" /></SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="(s, i) in COOKING_SKILL_OPTIONS"
                    :key="i"
                    :value="s"
                  >{{ s }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <!-- 口味 + 厨具同一行并排；菜系独占下一行以便铺开（减少行数） -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <!-- Taste preference chips -->
            <div class="space-y-1">
              <Label class="text-xs">口味偏好</Label>
              <div class="flex flex-wrap gap-1">
                <button
                  v-for="t in TASTE_OPTIONS"
                  :key="t"
                  type="button"
                  :class="[
                    'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
                    onboarding.taste_preference === t
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                  ]"
                  @click="onboarding.taste_preference = t"
                >{{ t }}</button>
              </div>
            </div>

            <!-- Cookware chips -->
            <div class="space-y-1">
              <Label class="text-xs">可用厨具</Label>
              <div class="flex flex-wrap gap-1">
                <button
                  v-for="w in COOKWARE_OPTIONS"
                  :key="w"
                  type="button"
                  :class="[
                    'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
                    onboarding.cookware.includes(w)
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                  ]"
                  @click="toggleArr(onboarding.cookware, w)"
                >{{ w }}</button>
              </div>
            </div>
          </div>

          <!-- Cuisine multi-select chips（通栏，chips 用多列流式布局摊开） -->
          <div class="space-y-1">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <Label class="text-xs">偏好菜系（可多选）</Label>
              <div class="flex items-center gap-1.5">
                <Input
                  v-model="onboarding._cuisine_other_input"
                  placeholder="其他菜系，回车添加"
                  class="h-7 w-44 text-xs"
                  v-safe-enter="addCustomCuisine"
                />
                <Button variant="outline" size="xs" @click="addCustomCuisine">添加</Button>
                <Badge
                  v-for="c in onboarding.cuisines.filter(x => !CUISINE_OPTIONS.includes(x))"
                  :key="c"
                  variant="destructive"
                  class="cursor-pointer text-[10px]"
                  @click="removeArr(onboarding.cuisines, c)"
                >{{ c }} ✕</Badge>
              </div>
            </div>
            <div class="flex flex-wrap gap-1">
              <button
                v-for="c in CUISINE_OPTIONS"
                :key="c"
                type="button"
                :class="[
                  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
                  onboarding.cuisines.includes(c)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                ]"
                @click="toggleArr(onboarding.cuisines, c)"
              >{{ c }}</button>
            </div>
          </div>

          <!-- 忌口食材（Q13-a：紧凑分类网格，点分类后在网格下方展开该分类的二级选择区） -->
          <div class="space-y-1.5">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <Label class="text-xs">忌口食材</Label>
              <span class="text-xs text-muted-foreground">
                点分类后选食材（红色为已忌口）；当前已忌口 {{ onboarding.disliked_ingredients.length }} 项
              </span>
            </div>

            <!-- L1 分类网格：2 行 × 4 列紧凑卡片，折叠态仅约 80px -->
            <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-1.5">
              <div
                v-for="(L1, i1) in DISLIKED_TREE"
                :key="i1"
                class="relative"
              >
                <button
                  type="button"
                  :title="L1.name + (countDislikedInL1(L1) > 0 ? '（已忌口 ' + countDislikedInL1(L1) + ' 项）' : '')"
                  :class="[
                    'flex w-full items-center justify-center gap-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors',
                    activeDislikeL1 === i1
                      ? 'bg-primary text-primary-foreground border-primary'
                      : (countDislikedInL1(L1) > 0
                          ? 'bg-destructive/10 border-destructive/40 text-foreground hover:bg-destructive/15'
                          : 'bg-background hover:bg-accent hover:text-accent-foreground border-input')
                  ]"
                  @click="toggleDislikeL1(i1)"
                >
                  <span class="truncate">{{ L1.name }}</span>
                </button>
                <!-- 角标独立于按钮态：无论选中与否都显示已忌口数，避免选中时信息被吞掉 -->
                <span
                  v-if="countDislikedInL1(L1) > 0"
                  class="pointer-events-none absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium leading-none text-white"
                >{{ countDislikedInL1(L1) }}</span>
              </div>
            </div>

            <!-- 展开区：先选二级子类（紧凑 chips 行），再只展开该子类的食材 -->
            <div
              v-if="activeDislikeL1 !== null"
              class="rounded-lg border p-2 space-y-2"
            >
              <!-- L2 子类选择行 -->
              <div class="flex flex-wrap gap-1">
                <button
                  v-for="(L2, i2) in DISLIKED_TREE[activeDislikeL1].children"
                  :key="i2"
                  type="button"
                  :class="[
                    'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
                    activeDislikeL2 === i2
                      ? 'bg-secondary text-secondary-foreground border-secondary'
                      : (countDislikedInL2(L2) > 0
                          ? 'bg-destructive/10 border-destructive/40 text-foreground hover:bg-destructive/15'
                          : 'bg-background hover:bg-accent hover:text-accent-foreground border-input')
                  ]"
                  @click="activeDislikeL2 = activeDislikeL2 === i2 ? null : i2"
                >
                  <span>{{ L2.name }}</span>
                  <span v-if="countDislikedInL2(L2) > 0" class="text-[10px]">({{ countDislikedInL2(L2) }})</span>
                </button>
              </div>

              <!-- 仅渲染当前选中的二级子类的食材 -->
              <template v-if="activeDislikeL2 !== null">
                <div
                  v-for="(L2, i2) in DISLIKED_TREE[activeDislikeL1].children"
                  v-show="i2 === activeDislikeL2"
                  :key="i2"
                  class="space-y-1"
                >
                  <!-- 自定义输入 + 已添加项列表 -->
                  <div v-if="L2.__custom" class="space-y-1.5">
                    <div class="flex gap-1.5">
                      <Input
                        v-model="customInputs[dislikeTreePathKey(DISLIKED_TREE[activeDislikeL1].name, L2.name)]"
                        placeholder="输入其他忌口食材，回车添加"
                        class="h-7 text-xs"
                        v-safe-enter="() => handleAddCustom(DISLIKED_TREE[activeDislikeL1], L2)"
                      />
                      <Button variant="outline" size="xs" @click="handleAddCustom(DISLIKED_TREE[activeDislikeL1], L2)">添加</Button>
                    </div>
                    <div
                      v-if="(onboarding._custom_disliked[dislikeTreePathKey(DISLIKED_TREE[activeDislikeL1].name, L2.name)] || []).length"
                      class="flex flex-wrap gap-1"
                    >
                      <Badge
                        v-for="(item, idx) in onboarding._custom_disliked[dislikeTreePathKey(DISLIKED_TREE[activeDislikeL1].name, L2.name)]"
                        :key="idx"
                        variant="destructive"
                        class="cursor-pointer text-[10px]"
                        @click="removeCustomDisliked(DISLIKED_TREE[activeDislikeL1].name, L2.name, idx, item)"
                      >{{ item }} ✕</Badge>
                    </div>
                    <p v-else class="text-xs text-muted-foreground">尚未添加自定义忌口</p>
                  </div>
                  <!-- 预置食材 chips -->
                  <div v-else class="flex flex-wrap gap-1">
                    <button
                      v-for="it in (L2.children || [])"
                      :key="it"
                      type="button"
                      :class="[
                        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors',
                        onboarding.disliked_ingredients.includes(it)
                          ? 'bg-destructive text-destructive-foreground border-destructive'
                          : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                      ]"
                      @click="toggleArr(onboarding.disliked_ingredients, it)"
                    >{{ it }}</button>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <!-- Save button -->
          <div class="flex justify-end">
            <Button size="sm" :disabled="onboardingSaving" @click="saveOnboarding">
              {{ onboardingSaving ? '保存中…' : (onboarding.completed ? '更新偏好档案' : '完成并保存') }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
