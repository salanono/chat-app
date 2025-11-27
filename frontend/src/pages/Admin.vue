<!-- frontend/src/pages/Admin.vue -->
<template>
  <div class="admin">
    <div class="top-bar">
      <h1>管理画面</h1>
      <button class="logout-btn" @click="logout">ログアウト</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">読み込み中...</p>

    <div v-if="!loading">
      <h2>セッション一覧</h2>
      <ul>
        <li v-for="s in sessions" :key="s.id">
          {{ s.visitor_name || "名無し" }} ({{ s.status }}) -
          {{ s.last_active_at }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const sessions = ref([]);
const loading = ref(false);
const error = ref("");

const fetchSessions = async () => {
  loading.value = true;
  error.value = "";

  const token = localStorage.getItem("admin_token");

  if (!token) {
    loading.value = false;
    router.push("/admin/login");
    return;
  }

  const res = await fetch("http://localhost:8000/api/sessions", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    loading.value = false;
    router.push("/admin/login");
    return;
  }

  if (!res.ok) {
    error.value = "セッション一覧の取得に失敗しました";
    loading.value = false;
    return;
  }

  sessions.value = await res.json();
  loading.value = false;
};

// ★ ログアウト処理
const logout = () => {
  localStorage.removeItem("admin_token");
  router.push("/admin/login");
};

onMounted(fetchSessions);
</script>

<style>
.admin {
  padding: 2rem;
  font-family: sans-serif;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logout-btn {
  background: #e33;
  color: white;
  padding: 8px 12px;
  border: none;
  cursor: pointer;
  border-radius: 4px;
}

.logout-btn:hover {
  background: #c22;
}

.error {
  color: red;
  margin-bottom: 1rem;
}
</style>
