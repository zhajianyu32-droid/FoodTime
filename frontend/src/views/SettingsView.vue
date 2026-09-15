<script setup>
import { onMounted } from 'vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectGroup, SelectLabel } from '@/components/ui/select'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Separator } from '@/components/ui/separator'
import { me, logout } from '@/composables/useAuth'
import { pwdForm, changePassword, onboarding, onboardingLoading, onboardingSaving, liveZodiac, liveChinese, mbtiSelect, loadOnboarding, saveOnboarding, dislikeTreePathKey, countDislikedInL1, countDislikedInL2, addCustomDisliked, removeCustomDisliked, addCustomCuisine, toggleArr, removeArr } from '@/composables/useSettings'
import { showToast } from '@/composables/useToast'
import { TASTE_OPTIONS, COOKWARE_OPTIONS, BUDGET_OPTIONS, COOKING_SKILL_OPTIONS, CUISINE_OPTIONS, MBTI_GROUPS, DISLIKED_TREE } from '@/lib/constants'
import { useRouter } from 'vue-router'

const router = useRouter()
// Local ref for custom disliked input per L1/L2
import { ref, reactive } from 'vue'
const customInputs = ref({})

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
  <div class="min-h-screen bg-background p-4 md:p-8">
    <div class="max-w-3xl mx-auto space-y-6">
      <!-- Page header -->
      <div>
        <h1 class="text-2xl font-bold">⚙️ 个人设置</h1>
        <p class="text-sm text-muted-foreground">管理账户、密码与个人饮食偏好档案</p>
      </div>

      <!-- Account info card -->
      <Card>
        <CardHeader>
          <div class="flex items-center justify-between gap-2">
            <div>
              <CardTitle class="text-lg">账户信息</CardTitle>
              <CardDescription>你的账户基本资料</CardDescription>
            </div>
            <div class="flex items-center gap-2">
              <Button v-if="!profileEditing" variant="outline" size="sm" @click="startProfileEdit">编辑资料</Button>
              <Button variant="outline" size="sm" @click="doLogout">退出登录</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <!-- 编辑模式 -->
          <div v-if="profileEditing" class="space-y-3">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="space-y-1.5">
                <Label for="pf-nickname">昵称</Label>
                <Input id="pf-nickname" v-model="profileForm.nickname" maxlength="30" placeholder="输入昵称" />
              </div>
              <div class="space-y-1.5">
                <Label for="pf-phone">手机号</Label>
                <Input id="pf-phone" v-model="profileForm.phone" maxlength="20" placeholder="留空表示解绑" />
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
          <div v-else class="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
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
      <Card>
        <CardHeader>
          <CardTitle class="text-lg">修改密码</CardTitle>
          <CardDescription>修改成功后会立即失效所有现有 Token，需要重新登录</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <Label for="pwd-old">原密码</Label>
            <Input
              id="pwd-old"
              type="password"
              v-model="pwdForm.old"
              autocomplete="current-password"
              placeholder="请输入当前密码"
            />
          </div>
          <div class="space-y-2">
            <Label for="pwd-new">新密码</Label>
            <Input
              id="pwd-new"
              type="password"
              v-model="pwdForm.pwd"
              autocomplete="new-password"
              placeholder="至少 6 位"
            />
          </div>
          <div class="space-y-2">
            <Label for="pwd-new2">确认新密码</Label>
            <Input
              id="pwd-new2"
              type="password"
              v-model="pwdForm.pwd2"
              autocomplete="new-password"
              placeholder="再次输入新密码"
              v-safe-enter="submitChangePassword"
            />
          </div>
          <p v-if="pwdForm.error" class="text-sm text-destructive">{{ pwdForm.error }}</p>
          <p v-if="pwdForm.success" class="text-sm text-green-600">{{ pwdForm.success }}</p>
          <div class="flex justify-end">
            <Button :disabled="pwdForm.loading || pwdForm.changed" @click="submitChangePassword">
              {{ pwdForm.loading ? '提交中…' : (pwdForm.changed ? '已修改，请重新登录' : '修改密码') }}
            </Button>
          </div>
        </CardContent>
      </Card>

      <!-- Onboarding card (the big one) -->
      <Card>
        <CardHeader>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle class="text-lg">偏好档案 (Onboarding)</CardTitle>
              <CardDescription>记录口味偏好、烹饪条件与忌口，让 AI 更懂你</CardDescription>
            </div>
            <div class="flex flex-wrap items-center gap-1.5">
              <Badge v-if="onboarding.completed" variant="default">已完善</Badge>
              <Badge v-else variant="secondary">未完善</Badge>
              <Badge v-if="onboarding.zodiac" variant="outline">{{ onboarding.zodiac }}</Badge>
              <Badge v-if="onboarding.chinese_zodiac" variant="outline">属{{ onboarding.chinese_zodiac }}</Badge>
              <Badge v-if="onboarding.mbti" variant="outline">{{ onboarding.mbti }}</Badge>
              <Badge v-if="onboarding.cuisines && onboarding.cuisines.length" variant="outline">
                {{ onboarding.cuisines.length }} 菜系
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent v-if="onboardingLoading" class="text-center text-sm text-muted-foreground py-8">
          加载偏好档案中…
        </CardContent>

        <CardContent v-else class="space-y-6">
          <!-- Birth date -->
          <div class="space-y-2">
            <Label for="ob-birth">出生日期</Label>
            <Input id="ob-birth" type="date" v-model="onboarding.birth_date" />
            <div class="flex items-center gap-1.5">
              <Badge v-if="liveZodiac" variant="secondary">{{ liveZodiac }}</Badge>
              <Badge v-if="liveChinese" variant="secondary">属{{ liveChinese }}</Badge>
              <span v-if="!liveZodiac && !liveChinese" class="text-xs text-muted-foreground">选择出生日期后自动推算星座与属相</span>
            </div>
          </div>

          <Separator />

          <!-- MBTI select -->
          <div class="space-y-2">
            <Label>MBTI 性格类型（选填）</Label>
            <Select v-model="mbtiSelect">
              <SelectTrigger class="w-full"><SelectValue placeholder="选择 MBTI 或不填" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">不填</SelectItem>
                <SelectGroup v-for="g in MBTI_GROUPS" :key="g.label">
                  <SelectLabel>{{ g.label }}</SelectLabel>
                  <SelectItem v-for="m in g.items" :key="m" :value="m">{{ m }}</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <!-- Budget select -->
          <div class="space-y-2">
            <Label>每餐预算区间（元）</Label>
            <Select v-model="onboarding.budget_level">
              <SelectTrigger class="w-full"><SelectValue placeholder="选择预算区间" /></SelectTrigger>
              <SelectContent>
                <SelectItem v-for="b in BUDGET_OPTIONS" :key="b" :value="b">{{ b }} 元</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <!-- Cooking skill select -->
          <div class="space-y-2">
            <Label>烹饪水平</Label>
            <Select v-model="onboarding.cooking_skill">
              <SelectTrigger class="w-full"><SelectValue placeholder="选择烹饪水平" /></SelectTrigger>
              <SelectContent>
                <SelectItem
                  v-for="(s, i) in COOKING_SKILL_OPTIONS"
                  :key="i"
                  :value="s"
                >{{ s }}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          <!-- Taste preference chips -->
          <div class="space-y-2">
            <Label>口味偏好</Label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="t in TASTE_OPTIONS"
                :key="t"
                type="button"
                :class="[
                  'inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                  onboarding.taste_preference === t
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                ]"
                @click="onboarding.taste_preference = t"
              >{{ t }}</button>
            </div>
          </div>

          <Separator />

          <!-- Cuisine multi-select chips + custom input -->
          <div class="space-y-2">
            <Label>偏好菜系（可多选）</Label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="c in CUISINE_OPTIONS"
                :key="c"
                type="button"
                :class="[
                  'inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                  onboarding.cuisines.includes(c)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                ]"
                @click="toggleArr(onboarding.cuisines, c)"
              >{{ c }}</button>
            </div>
            <!-- 其他菜系自定义输入 -->
            <div class="flex gap-2 pt-1">
              <Input
                v-model="onboarding._cuisine_other_input"
                placeholder="输入其他菜系，回车添加"
                v-safe-enter="addCustomCuisine"
              />
              <Button variant="outline" size="sm" @click="addCustomCuisine">添加</Button>
            </div>
            <!-- 自定义菜系列表 -->
            <div
              v-if="onboarding.cuisines.filter(c => !CUISINE_OPTIONS.includes(c)).length"
              class="flex flex-wrap gap-1.5 pt-1"
            >
              <Badge
                v-for="c in onboarding.cuisines.filter(c => !CUISINE_OPTIONS.includes(c))"
                :key="c"
                variant="destructive"
                class="cursor-pointer"
                @click="removeArr(onboarding.cuisines, c)"
              >{{ c }} ✕</Badge>
            </div>
          </div>

          <Separator />

          <!-- Cookware chips -->
          <div class="space-y-2">
            <Label>可用厨具</Label>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="w in COOKWARE_OPTIONS"
                :key="w"
                type="button"
                :class="[
                  'inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
                  onboarding.cookware.includes(w)
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                ]"
                @click="toggleArr(onboarding.cookware, w)"
              >{{ w }}</button>
            </div>
          </div>

          <Separator />

          <!-- Disliked ingredients tree -->
          <div class="space-y-2">
            <Label>忌口食材</Label>
            <p class="text-xs text-muted-foreground">
              展开分类后，点选你不吃的食材（红色为已忌口）；每个分类下有「其他」可自定义。
            </p>
            <Accordion type="multiple" class="w-full rounded-lg border px-2">
              <AccordionItem
                v-for="(L1, i1) in DISLIKED_TREE"
                :key="i1"
                :value="'L1-' + i1"
              >
                <AccordionTrigger>
                  <span class="flex items-center gap-2">
                    <span class="font-medium">{{ L1.name }}</span>
                    <Badge variant="secondary" class="text-xs">{{ countDislikedInL1(L1) }} 项</Badge>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <Accordion type="multiple" class="w-full pl-2">
                    <AccordionItem
                      v-for="(L2, i2) in L1.children"
                      :key="i2"
                      :value="`L1-${i1}-L2-${i2}`"
                    >
                      <AccordionTrigger>
                        <span class="flex items-center gap-2">
                          <span>{{ L2.name }}</span>
                          <Badge variant="secondary" class="text-xs">{{ countDislikedInL2(L2) }} 项</Badge>
                        </span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <!-- 自定义输入 + 已添加项列表 -->
                        <div v-if="L2.__custom" class="space-y-2">
                          <div class="flex gap-2">
                            <Input
                              v-model="customInputs[dislikeTreePathKey(L1.name, L2.name)]"
                              placeholder="输入其他忌口食材，回车添加"
                              v-safe-enter="() => handleAddCustom(L1, L2)"
                            />
                            <Button variant="outline" size="sm" @click="handleAddCustom(L1, L2)">添加</Button>
                          </div>
                          <div
                            v-if="(onboarding._custom_disliked[dislikeTreePathKey(L1.name, L2.name)] || []).length"
                            class="flex flex-wrap gap-1.5"
                          >
                            <Badge
                              v-for="(item, idx) in onboarding._custom_disliked[dislikeTreePathKey(L1.name, L2.name)]"
                              :key="idx"
                              variant="destructive"
                              class="cursor-pointer"
                              @click="removeCustomDisliked(L1.name, L2.name, idx, item)"
                            >{{ item }} ✕</Badge>
                          </div>
                          <p v-else class="text-xs text-muted-foreground">尚未添加自定义忌口</p>
                        </div>
                        <!-- 预置食材 chips -->
                        <div v-else class="flex flex-wrap gap-1.5">
                          <button
                            v-for="it in (L2.children || [])"
                            :key="it"
                            type="button"
                            :class="[
                              'inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-medium transition-colors',
                              onboarding.disliked_ingredients.includes(it)
                                ? 'bg-destructive text-destructive-foreground border-destructive'
                                : 'bg-background hover:bg-accent hover:text-accent-foreground border-input'
                            ]"
                            @click="toggleArr(onboarding.disliked_ingredients, it)"
                          >{{ it }}</button>
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
            <p class="text-xs text-muted-foreground pt-2">
              当前已忌口 {{ onboarding.disliked_ingredients.length }} 项
            </p>
          </div>

          <!-- Save button -->
          <div class="flex justify-end pt-2">
            <Button :disabled="onboardingSaving" @click="saveOnboarding">
              {{ onboardingSaving ? '保存中…' : (onboarding.completed ? '更新偏好档案' : '完成并保存') }}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
