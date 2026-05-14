<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppLayout from './layouts/AppLayout.vue'
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
</style>
