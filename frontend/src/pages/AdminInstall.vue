<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";

const API_BASE = "http://localhost:8000";
const TOKEN_KEY = "admin_token";

const router = useRouter();

const loading = ref(true);
const error = ref("");
const apiKey = ref("");

const embedIframe = computed(() => {
  if (!apiKey.value) return "";
  return `<iframe
  src="http://localhost:5173/widget?api_key=${apiKey.value}"
  style="position:fixed;right:20px;bottom:20px;width:360px;height:520px;border:none;z-index:999999;border-radius:16px;box-shadow:0 10px 30px rgba(15,23,42,.25);"
  allow="clipboard-read; clipboard-write"
></iframe>`;
});

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    alert("コピーしました！");
  } catch {
    alert("コピーに失敗しました（ブラウザ権限/HTTPS確認）");
  }
};

const fetchApiKey = async () => {
  loading.value = true;
  error.value = "";

  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    loading.value = false;
    error.value = "ログイン情報が見つかりません。";
    router.push("/admin/login");
    return;
  }

  try {
    // ✅ バックエンドに合わせてここは変更してOK
    // 例: /api/widget/api-key とか /api/companies/me/api-key とか
    const res = await fetch(`${API_BASE}/api/embed-key`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);

    apiKey.value = data.api_key; // { api_key: "..." }想定
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
};

const embedScript = computed(() => {
  if (!apiKey.value) return "";
  const open = `<script src="http://localhost:8000/api/embed.js?api_key=${apiKey.value}" async>`;
  const close = `</` + `script>`;
  return open + close;
});

onMounted(fetchApiKey);
</script>

<template>
  <div class="page">
    <div class="top">
      <h1 class="title">設置コード</h1>
      <div class="actions">
        <button class="btn ghost" @click="router.push('/admin')">
          管理画面
        </button>
        <button
          class="btn"
          @click="copy(embedIframe.value)"
          :disabled="!apiKey"
        >
          iframeをコピー
        </button>
      </div>
    </div>

    <p class="desc">
      まずは最短で動く <b>iframe版</b> を貼り付けてください。（script
      1行版は次に作る）
    </p>

    <div v-if="loading" class="card">読み込み中…</div>

    <div v-else-if="error" class="card error">
      {{ error }}
      <div style="margin-top: 10px">
        <button class="btn" @click="fetchApiKey">再試行</button>
      </div>
    </div>

    <div v-else class="card">
      <div class="row">
        <h2 class="subtitle">1行スクリプト（おすすめ）</h2>
        <button class="btn" @click="copy(embedScript)">コピー</button>
      </div>
      <pre class="code">{{ embedScript }}</pre>
    </div>

    <div v-if="!loading && !error" class="card" style="margin-top: 16px">
      <div class="row">
        <h2 class="subtitle">iframe設置コード（デバッグ用）</h2>
        <button class="btn" @click="copy(embedIframe)">コピー</button>
      </div>
      <pre class="code">{{ embedIframe }}</pre>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 0 auto;
  padding: 22px;
  color: #0f172a;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.title {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
}
.actions {
  display: flex;
  gap: 8px;
}
.desc {
  margin: 10px 0 14px;
  color: #475569;
  font-size: 14px;
}
.card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}
.error {
  border-color: #fecaca;
  background: #fff1f2;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.subtitle {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
}
.code {
  margin: 0;
  padding: 12px;
  border-radius: 12px;
  background: #0b1220;
  color: #e2e8f0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
}
.btn {
  border: none;
  border-radius: 999px;
  padding: 8px 12px;
  font-weight: 800;
  background: #4fc3f7;
  color: #fff;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.btn.ghost {
  background: #e2e8f0;
  color: #0f172a;
}
</style>
