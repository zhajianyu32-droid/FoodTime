import { toast } from 'vue-sonner'

export function showToast(message, type = 'info') {
  if (type === 'success') toast.success(message)
  else if (type === 'error') toast.error(message)
  else toast(message)
}

export { toast }
