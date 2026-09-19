import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/index.css'
import safeEnter from './directives/safeEnter'

const app = createApp(App)
app.use(router)
app.directive('safe-enter', safeEnter)
app.mount('#app')
