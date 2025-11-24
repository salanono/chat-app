<!-- frontend/src/App.vue -->
<template>
  <div class="app-root">
    <header class="app-header">
      <h1 class="app-title">チャットサポート デモ</h1>
      <p class="app-subtitle">
        上のタブで「訪問者用ウィジェット」と「管理画面」を切り替えられます。
      </p>

      <div class="app-tabs">
        <button
          class="app-tab"
          :class="{ 'app-tab--active': currentView === 'widget' }"
          @click="currentView = 'widget'"
        >
          🧑‍💻 訪問者ウィジェット
        </button>
        <button
          class="app-tab"
          :class="{ 'app-tab--active': currentView === 'admin' }"
          @click="currentView = 'admin'"
        >
          🎧 管理画面（オペレーター）
        </button>
      </div>
    </header>

    <main class="app-main">
      <Widget v-if="currentView === 'widget'" />
      <Admin v-else />
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue";
import Widget from "./pages/Widget.vue";
import Admin from "./pages/Admin.vue";

const currentView = ref("widget"); // 'widget' or 'admin'
</script>

<style scoped>
.app-root {
  min-height: 100vh;
  background: #020617;
  color: #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.app-header {
  padding: 16px 20px;
  border-bottom: 1px solid #1f2937;
}

.app-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.app-subtitle {
  margin: 4px 0 10px;
  font-size: 13px;
  color: #9ca3af;
}

.app-tabs {
  display: inline-flex;
  padding: 3px;
  background: #020617;
  border-radius: 999px;
  border: 1px solid #1f2937;
}

.app-tab {
  border: none;
  background: transparent;
  color: #9ca3af;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
}

.app-tab--active {
  background: #22c55e;
  color: #022c22;
  font-weight: 600;
}

.app-main {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: stretch;
  padding: 20px;
}

/* 中身のコンポーネントが小さめなら中央に寄せたい場合はこんな感じでもOK
.app-main > * {
  max-width: 1200px;
  width: 100%;
}
*/
</style>
