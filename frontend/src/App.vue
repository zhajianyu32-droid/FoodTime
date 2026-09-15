<script setup>
import { RouterView } from 'vue-router'
import { Toaster } from '@/components/ui/sonner'
</script>

<template>
  <RouterView />
  <Toaster
    rich-colors
    position="top-center"
    :duration="2500"
    :visible-toasts="3"
    :offset="80"
    close-button
  />
</template>
