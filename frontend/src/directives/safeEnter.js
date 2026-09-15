/**
 * v-safe-enter 指令：处理 IME 输入法下的回车事件
 *
 * 中文输入法选词时按回车不会误触发，仅当非 IME 组合状态下的回车才执行回调。
 * 用法: <input v-safe-enter="handler" />
 */
export default {
  mounted(el, binding) {
    let composing = false
    el.addEventListener('compositionstart', () => { composing = true })
    el.addEventListener('compositionend', () => { composing = false })
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !composing && !e.isComposing) {
        e.preventDefault()
        binding.value?.()
      }
    })
  },
}
