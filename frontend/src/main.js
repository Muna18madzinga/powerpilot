import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@fontsource-variable/archivo/wdth.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles.css'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
