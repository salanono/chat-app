<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";

const API_BASE = "http://localhost:8000";
const TOKEN_KEY = "admin_token";
const router = useRouter();

const loading = ref(false);
const error = ref("");

const keys = ref([]);
const newKeyName = ref("");
const newlyCreatedKey = ref(""); // 作成直後だけ表示＆コピー用

const authHeaders = () => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  return { Authorization: `Bearer ${token}` };
};

const copy = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    alert("コピーしました！");
  } catch {
    alert("コピーに失敗しました（ブラウザ権限/HTTPS確認）");
  }
};

const fetchKeys = async () => {
  error.value = "";
  loading.value = true;

  const headers = authHeaders();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/api-keys`, { headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);
    keys.value = data;
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
};

const createKey = async () => {
  error.value = "";
  newlyCreatedKey.value = "";

  const headers = authHeaders();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/api-keys`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ name: newKeyName.value?.trim() || null }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);

    newlyCreatedKey.value = data.api_key || "";
    newKeyName.value = "";
    await fetchKeys();
  } catch (e) {
    error.value = String(e?.message || e);
  }
};

const disableKey = async (id) => {
  if (!confirm("このAPIキーを無効化しますか？")) return;

  error.value = "";
  const headers = authHeaders();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/api-keys/${id}/disable`, {
      method: "POST",
      headers,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);
    await fetchKeys();
  } catch (e) {
    error.value = String(e?.message || e);
  }
};

const rotateKey = async (id) => {
  if (!confirm("APIキーを再発行しますか？（古いキーは無効化されます）")) return;

  error.value = "";
  newlyCreatedKey.value = "";

  const headers = authHeaders();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/api-keys/${id}/rotate`, {
      method: "POST",
      headers,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);

    newlyCreatedKey.value = data.api_key || "";
    await fetchKeys();
  } catch (e) {
    error.value = String(e?.message || e);
  }
};

const deleteKey = async (id) => {
  if (!confirm("この無効化されたAPIキーを削除しますか？（元に戻せません）"))
    return;

  error.value = "";
  const headers = authHeaders();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/api-keys/${id}`, {
      method: "DELETE",
      headers,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `failed: ${res.status}`);
    await fetchKeys();
  } catch (e) {
    error.value = String(e?.message || e);
  }
};

onMounted(fetchKeys);
</script>

<template>
  <div class="page">
    <div class="top">
      <h1 class="title">APIキー管理</h1>
      <div class="actions">
        <button class="btn ghost" @click="router.push('/admin')">
          管理画面
        </button>
      </div>
    </div>

    <p class="desc">
      APIキーは
      <b>作成時/再発行時だけ</b> フル表示されます（一覧はマスク表示）。
    </p>

    <div v-if="error" class="card error">{{ error }}</div>

    <div class="card">
      <div class="row">
        <h2 class="subtitle">新規発行</h2>
      </div>
      <div class="create">
        <input
          v-model="newKeyName"
          class="input"
          placeholder="名前（例：本番サイト / LP / staging）任意"
        />
        <button class="btn" @click="createKey">発行</button>
      </div>

      <div v-if="newlyCreatedKey" class="newkey">
        <div class="newkey-head">
          <div class="newkey-title">発行されたAPIキー（今だけ表示）</div>
          <button class="btn" @click="copy(newlyCreatedKey)">コピー</button>
        </div>
        <pre class="code">{{ newlyCreatedKey }}</pre>
      </div>
    </div>

    <div class="card">
      <div class="row">
        <h2 class="subtitle">一覧</h2>
        <button class="btn ghost" @click="fetchKeys" :disabled="loading">
          更新
        </button>
      </div>

      <div v-if="loading">読み込み中…</div>

      <table v-else class="table">
        <thead>
          <tr>
            <th>名前</th>
            <th>キー</th>
            <th>状態</th>
            <th>作成日</th>
            <th style="width: 220px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in keys" :key="k.id">
            <td>{{ k.name || "-" }}</td>
            <td>
              <code>{{ k.key_masked }}</code>
            </td>
            <td>
              <span class="badge" :class="k.is_active ? 'ok' : 'ng'">
                {{ k.is_active ? "有効" : "無効" }}
              </span>
            </td>
            <td>{{ k.created_at ? k.created_at.slice(0, 10) : "-" }}</td>
            <td class="ops">
              <button
                class="btn small"
                @click="rotateKey(k.id)"
                :disabled="!k.is_active"
              >
                再発行
              </button>
              <button
                class="btn small danger"
                @click="disableKey(k.id)"
                :disabled="!k.is_active"
              >
                無効化
              </button>
              <button
                v-if="!k.is_active"
                class="btn small danger"
                @click="deleteKey(k.id)"
              >
                削除
              </button>
            </td>
          </tr>
          <tr v-if="keys.length === 0">
            <td colspan="5" style="color: #64748b">まだAPIキーがありません</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 980px;
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
  margin-bottom: 12px;
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
.create {
  display: flex;
  gap: 10px;
  align-items: center;
}
.input {
  flex: 1;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
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
.btn.ghost {
  background: #e2e8f0;
  color: #0f172a;
}
.btn.small {
  padding: 6px 10px;
  font-size: 12px;
}
.btn.danger {
  background: #ef5350;
}
.btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.newkey {
  margin-top: 12px;
}
.newkey-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.newkey-title {
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
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
.table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  border-top: 1px solid #e2e8f0;
  padding: 10px 8px;
  font-size: 13px;
  text-align: left;
}
th {
  color: #475569;
  font-size: 12px;
}
.ops {
  display: flex;
  gap: 8px;
}
.badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
}
.badge.ok {
  background: #e0f7fa;
  color: #0369a1;
  border: 1px solid #bae6fd;
}
.badge.ng {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
</style>
