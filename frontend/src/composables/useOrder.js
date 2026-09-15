import { ref, nextTick, reactive } from 'vue'
import { api } from './useApi'
import { me } from './useAuth'
import { showToast } from './useToast'

const fortune = ref(null)
const chatSession = ref(null)
const chatRound = ref(0)
const chatMsgs = ref([])
const lastQuestion = ref(null)
const finalRecommend = ref(null)
const loading = reactive({ fortune: false, chatStart: false, chatTurn: false })
const chatBox = ref(null)

function scrollChat() { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight }

async function drawFortune() {
  if (!me.value) return
  loading.fortune = true
  try {
    const uid = me.value.user_id || me.value.id
    fortune.value = await api(`/fortune/today/${uid}`)
  } catch (e) { showToast('运势获取失败：' + e.message, 'error') }
  finally { loading.fortune = false }
}

async function startChat() {
  if (!me.value) return
  loading.chatStart = true
  try {
    const uid = me.value.user_id || me.value.id
    const r = await api('/chat/session', { method: 'POST', body: { user_id: uid } })
    chatSession.value = r.session_id
    chatRound.value = r.current_round || 1
    chatMsgs.value = [{ id: Date.now(), role: 'ai', text: r.question }]
    lastQuestion.value = { dimension: r.dimension, question: r.question, options: r.options }
    finalRecommend.value = null
  } catch (e) { showToast('创建会话失败：' + e.message, 'error') }
  finally { loading.chatStart = false; await nextTick(scrollChat) }
}

async function sendAnswer(opt) {
  if (!chatSession.value) return
  chatMsgs.value.push({ id: Date.now() + Math.random(), role: 'user', text: opt })
  lastQuestion.value = null
  loading.chatTurn = true
  try {
    const uid = me.value.user_id || me.value.id
    const r = await api('/chat/turn', {
      method: 'POST',
      body: { session_id: chatSession.value, user_id: uid, answer: opt }
    })
    if (r.final_recommend) {
      finalRecommend.value = r
      chatMsgs.value.push({ id: Date.now() + 2, role: 'ai', text: '🎯 最终推荐：' + r.final_recommend + '\n理由：' + r.recommend_reason })
    } else {
      chatRound.value = r.current_round
      chatMsgs.value.push({ id: Date.now() + 1, role: 'ai', text: r.question })
      lastQuestion.value = { dimension: r.dimension, question: r.question, options: r.options }
    }
  } catch (e) { showToast('对话失败：' + e.message, 'error'); chatMsgs.value.pop() }
  finally { loading.chatTurn = false; await nextTick(scrollChat) }
}

function resetChat() {
  chatSession.value = null; chatRound.value = 0; chatMsgs.value = []; lastQuestion.value = null; finalRecommend.value = null
}

async function saveTakeout(r, fb) {
  try {
    const uid = me.value.user_id || me.value.id
    await api('/diary/takeout', {
      method: 'POST',
      body: {
        user_id: uid,
        session_id: chatSession.value || '',
        final_choice: r.final_recommend || '',
        choice_reason: r.recommend_reason || '',
        satisfaction: fb === '不好吃' ? '踩雷' : fb,
        conversation_rounds: chatRound.value || 0,
      }
    })
    showToast(`反馈「${fb}」已记录，偏好模型已更新 ✓`)
  } catch (e) { showToast('记录失败：' + e.message, 'error') }
}

export { fortune, chatSession, chatRound, chatMsgs, lastQuestion, finalRecommend, loading, chatBox,
  drawFortune, startChat, sendAnswer, resetChat, saveTakeout, scrollChat }
