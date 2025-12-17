<!-- frontend/src/pages/AdminBotSettings.vue -->
<template>
  <div class="page">
    <header class="top">
      <div>
        <h1 class="title">Bot設定</h1>
        <p class="sub">
          ウィジェットの選択肢（ボタン）と返信内容を編集できます。
        </p>
      </div>

      <div class="top-actions">
        <button class="btn btn--ghost" @click="goBack">← 戻る</button>
        <button class="btn" :disabled="saving" @click="saveSetting">
          {{ saving ? "保存中…" : "設定保存" }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">読み込み中…</div>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="!loading" class="grid">
      <section class="card">
        <h2 class="card-title">基本設定</h2>

        <div class="row">
          <label class="switch">
            <input type="checkbox" v-model="form.enabled" />
            <span class="switch-ui" />
            <span class="switch-text">Botを有効にする</span>
          </label>
        </div>

        <div class="row">
          <label class="label">ウェルカムメッセージ</label>
          <textarea
            v-model="form.welcome_message"
            class="textarea"
            rows="4"
            placeholder="例）こんにちは！ご用件を選んでください。"
          />
          <div class="hint">※ ウィジェットの「最初の案内文」に表示されます</div>
        </div>
      </section>

      <section class="card">
        <div class="card-head">
          <h2 class="card-title">選択肢（ボタン）</h2>
          <button class="btn" @click="openCreate">＋ 追加</button>
        </div>

        <div v-if="options.length === 0" class="empty">
          まだ選択肢がありません。「追加」から作ってください。
        </div>

        <ul class="list" v-else>
          <li v-for="(opt, idx) in optionsSorted" :key="opt.id" class="item">
            <div class="item-main">
              <div class="item-title">
                <span class="badge" :class="`badge--${opt.action}`">{{
                  actionLabel(opt.action)
                }}</span>
                <span class="label-text">{{ opt.label }}</span>
                <span v-if="!opt.is_active" class="inactive">（無効）</span>
              </div>

              <div class="item-sub">
                <span class="mono">id: {{ opt.id }}</span>
                <span class="dot">•</span>
                <span class="mono">order: {{ opt.sort_order }}</span>
                <span class="dot">•</span>
                <span v-if="opt.action === 'link' && opt.link_url" class="mono">
                  link: {{ opt.link_url }}
                </span>
                <span
                  v-if="opt.action !== 'link' && opt.reply_text"
                  class="preview"
                >
                  {{ opt.reply_text }}
                </span>
              </div>
            </div>

            <div class="item-actions">
              <button
                class="btn btn--ghost"
                :disabled="idx === 0"
                @click="moveUp(opt)"
              >
                ↑
              </button>
              <button
                class="btn btn--ghost"
                :disabled="idx === optionsSorted.length - 1"
                @click="moveDown(opt)"
              >
                ↓
              </button>
              <button class="btn btn--ghost" @click="openEdit(opt)">
                編集
              </button>
              <button class="btn btn--danger" @click="removeOption(opt)">
                削除
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <div v-if="modal.open" class="modal" @click.self="closeModal">
      <div class="modal__card">
        <div class="modal__head">
          <h3 class="modal__title">
            {{ modal.mode === "create" ? "選択肢を追加" : "選択肢を編集" }}
          </h3>
          <button class="x" @click="closeModal">✕</button>
        </div>

        <div class="modal__body">
          <div class="field">
            <label class="label">ボタン表示名（label）</label>
            <input
              v-model="modal.form.label"
              class="input"
              placeholder="例）料金について"
            />
          </div>

          <div class="field">
            <label class="label">アクション</label>
            <select v-model="modal.form.action" class="select">
              <option value="reply">返信（reply）</option>
              <option value="handoff">有人対応（handoff）</option>
              <option value="link">リンク案内（link）</option>
            </select>
            <div class="hint">
              reply: Botが文章で返信 / handoff: 「担当者呼びます」など / link:
              URLを案内
            </div>
          </div>

          <div class="field" v-if="modal.form.action === 'link'">
            <label class="label">リンクURL</label>
            <input
              v-model="modal.form.link_url"
              class="input"
              placeholder="https://example.com/help"
            />
          </div>

          <div class="field">
            <label class="label">返信文（reply_text）</label>
            <textarea
              v-model="modal.form.reply_text"
              class="textarea"
              rows="4"
              placeholder="例）料金プランはこちらです。"
            />
          </div>

          <div class="field">
            <label class="switch">
              <input type="checkbox" v-model="modal.form.is_active" />
              <span class="switch-ui" />
              <span class="switch-text">有効にする</span>
            </label>
          </div>
        </div>

        <div class="modal__foot">
          <button class="btn btn--ghost" @click="closeModal">キャンセル</button>
          <button
            class="btn"
            :disabled="modalSaving || !modal.form.label.trim()"
            @click="submitModal"
          >
            {{ modalSaving ? "保存中…" : "保存" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";

const API_BASE = "http://localhost:8000";
const router = useRouter();

const loading = ref(false);
const saving = ref(false);
const modalSaving = ref(false);
const error = ref("");

const form = ref({
  enabled: true,
  welcome_message: "",
});

const options = ref([]);

const optionsSorted = computed(() => {
  return [...options.value].sort(
    (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)
  );
});

const authHeader = () => {
  const token = localStorage.getItem("admin_token");
  if (!token) return null;
  return { Authorization: `Bearer ${token}` };
};

const goBack = () => router.push("/admin");

const fetchBotSettings = async () => {
  loading.value = true;
  error.value = "";

  const headers = authHeader();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/bot/settings`, { headers });
    if (res.status === 401) {
      localStorage.removeItem("admin_token");
      router.push("/admin/login");
      return;
    }
    if (!res.ok) {
      error.value = "Bot設定の取得に失敗しました";
      return;
    }

    const data = await res.json();
    form.value.enabled = !!data.enabled;
    form.value.welcome_message = data.welcome_message || "";
    options.value = data.options || [];
  } catch (e) {
    console.error(e);
    error.value = "Bot設定の取得でエラーが発生しました";
  } finally {
    loading.value = false;
  }
};

const saveSetting = async () => {
  saving.value = true;
  error.value = "";

  const headers = authHeader();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/bot/settings`, {
      method: "PUT",
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        enabled: form.value.enabled,
        welcome_message: form.value.welcome_message,
      }),
    });

    if (res.status === 401) {
      localStorage.removeItem("admin_token");
      router.push("/admin/login");
      return;
    }
    if (!res.ok) {
      error.value = "Bot設定の保存に失敗しました";
      return;
    }

    const data = await res.json();
    form.value.enabled = !!data.enabled;
    form.value.welcome_message = data.welcome_message || "";
    options.value = data.options || options.value;
  } catch (e) {
    console.error(e);
    error.value = "Bot設定の保存でエラーが発生しました";
  } finally {
    saving.value = false;
  }
};

const actionLabel = (action) => {
  if (action === "reply") return "返信";
  if (action === "handoff") return "有人";
  if (action === "link") return "リンク";
  return action || "-";
};

// --- 並び替え（sort_order を入れ替えるだけ） ---
const swapOrder = async (a, b) => {
  const headers = authHeader();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  const aOrder = a.sort_order ?? 0;
  const bOrder = b.sort_order ?? 0;

  a.sort_order = bOrder;
  b.sort_order = aOrder;

  try {
    await Promise.all([
      fetch(`${API_BASE}/api/bot/options/${a.id}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: a.sort_order }),
      }),
      fetch(`${API_BASE}/api/bot/options/${b.id}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: b.sort_order }),
      }),
    ]);
  } catch (e) {
    console.error(e);
    await fetchBotSettings();
  }
};

const moveUp = async (opt) => {
  const list = optionsSorted.value;
  const idx = list.findIndex((o) => o.id === opt.id);
  if (idx <= 0) return;
  await swapOrder(list[idx], list[idx - 1]);
};

const moveDown = async (opt) => {
  const list = optionsSorted.value;
  const idx = list.findIndex((o) => o.id === opt.id);
  if (idx < 0 || idx >= list.length - 1) return;
  await swapOrder(list[idx], list[idx + 1]);
};

// --- モーダル（追加・編集） ---
const modal = ref({
  open: false,
  mode: "create",
  form: {
    id: null,
    label: "",
    action: "reply",
    reply_text: "",
    link_url: "",
    is_active: true,
  },
});

const openCreate = () => {
  modal.value.open = true;
  modal.value.mode = "create";
  modal.value.form = {
    id: null,
    label: "",
    action: "reply",
    reply_text: "",
    link_url: "",
    is_active: true,
  };
};

const openEdit = (opt) => {
  modal.value.open = true;
  modal.value.mode = "edit";
  modal.value.form = {
    id: opt.id,
    label: opt.label || "",
    action: opt.action || "reply",
    reply_text: opt.reply_text || "",
    link_url: opt.link_url || "",
    is_active: opt.is_active !== false,
  };
};

const closeModal = () => {
  modal.value.open = false;
};

const submitModal = async () => {
  modalSaving.value = true;
  error.value = "";

  const headers = authHeader();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  const body = {
    label: modal.value.form.label,
    action: modal.value.form.action,
    reply_text: modal.value.form.reply_text,
    link_url:
      modal.value.form.action === "link" ? modal.value.form.link_url : null,
    is_active: modal.value.form.is_active,
  };

  try {
    if (modal.value.mode === "create") {
      const maxOrder = options.value.reduce(
        (m, o) => Math.max(m, o.sort_order ?? 0),
        0
      );
      body.sort_order = maxOrder + 10;

      const res = await fetch(`${API_BASE}/api/bot/options`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        error.value = "選択肢の追加に失敗しました";
        return;
      }
      const created = await res.json();
      options.value.push(created);
    } else {
      const id = modal.value.form.id;
      const res = await fetch(`${API_BASE}/api/bot/options/${id}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        error.value = "選択肢の更新に失敗しました";
        return;
      }
      const updated = await res.json();
      const idx = options.value.findIndex((o) => o.id === updated.id);
      if (idx >= 0) options.value[idx] = updated;
    }

    closeModal();
  } catch (e) {
    console.error(e);
    error.value = "保存中にエラーが発生しました";
  } finally {
    modalSaving.value = false;
  }
};

const removeOption = async (opt) => {
  if (!confirm(`「${opt.label}」を削除しますか？`)) return;

  const headers = authHeader();
  if (!headers) {
    router.push("/admin/login");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/bot/options/${opt.id}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) {
      error.value = "削除に失敗しました";
      return;
    }
    options.value = options.value.filter((o) => o.id !== opt.id);
  } catch (e) {
    console.error(e);
    error.value = "削除でエラーが発生しました";
  }
};

onMounted(async () => {
  await fetchBotSettings();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f8fafc;
  padding: 16px 20px;
  font-family: sans-serif;
}

.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.title {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
  font-weight: 700;
}

.sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.top-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 14px;
}

.card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  padding: 14px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.card-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.row {
  margin-bottom: 12px;
}

.label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 6px;
}

.hint {
  font-size: 11px;
  color: #64748b;
  margin-top: 6px;
}

.input,
.select,
.textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  background: #fff;
  color: #0f172a;
}
.textarea {
  resize: vertical;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  background: #4fc3f7;
  color: white;
}
.btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.btn--ghost {
  background: #f1f5f9;
  color: #0f172a;
  border: 1px solid #e2e8f0;
}
.btn--danger {
  background: #ef4444;
  color: #fff;
}

.loading {
  color: #64748b;
  font-size: 13px;
}
.error {
  color: #ef5350;
  font-size: 13px;
  margin-bottom: 10px;
}

.list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.item-main {
  min-width: 0;
}
.item-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}
.label-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}
.inactive {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}
.item-sub {
  font-size: 11px;
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", monospace;
}
.dot {
  opacity: 0.6;
}
.preview {
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.badge {
  font-size: 11px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
}
.badge--reply {
  color: #0284c7;
}
.badge--handoff {
  color: #16a34a;
}
.badge--link {
  color: #f97316;
}

.empty {
  color: #64748b;
  font-size: 13px;
  padding: 10px 0;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.switch input {
  display: none;
}
.switch-ui {
  width: 42px;
  height: 24px;
  border-radius: 999px;
  background: #cbd5e1;
  position: relative;
  transition: 0.15s ease;
}
.switch-ui::after {
  content: "";
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #fff;
  position: absolute;
  top: 3px;
  left: 3px;
  transition: 0.15s ease;
}
.switch input:checked + .switch-ui {
  background: #4fc3f7;
}
.switch input:checked + .switch-ui::after {
  transform: translateX(18px);
}
.switch-text {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 9999;
}
.modal__card {
  width: min(680px, 100%);
  background: #fff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.25);
  overflow: hidden;
}
.modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}
.modal__title {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}
.x {
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: #0f172a;
}
.modal__body {
  padding: 14px;
  display: grid;
  gap: 12px;
}
.field {
  display: grid;
  gap: 6px;
}
.modal__foot {
  padding: 12px 14px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  background: #fff;
}

* {
  box-sizing: border-box;
}

textarea,
input,
select {
  max-width: 100%;
}
</style>
