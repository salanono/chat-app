<!-- frontend/src/pages/Admin.vue -->
<template>
  <div class="admin-layout">
    <header class="admin-header">
      <h1>
        管理画面
        <span v-if="companyName">{{ companyName }}</span>
      </h1>

      <div class="header-actions">
        <button
          class="menu-btn"
          type="button"
          @click.stop="toggleMenu"
          aria-label="メニュー"
        >
          ☰
        </button>

        <div v-if="menuOpen" class="menu-panel" @click.stop>
          <button
            class="menu-item"
            type="button"
            @click="
              router.push('/admin/api-keys');
              closeMenu();
            "
          >
            APIキー
          </button>

          <button
            class="menu-item"
            type="button"
            @click="
              router.push('/admin/install');
              closeMenu();
            "
          >
            設置コード
          </button>

          <button
            class="menu-item"
            type="button"
            @click="
              router.push('/admin/bot');
              closeMenu();
            "
          >
            Bot設定
          </button>

          <div class="menu-sep"></div>

          <button class="menu-item danger" type="button" @click="logout">
            ログアウト
          </button>
        </div>
      </div>
    </header>

    <div class="admin-body">
      <!-- 左側：セッション一覧 -->
      <aside class="session-list">
        <h2>セッション一覧</h2>

        <div class="session-filters">
          <label class="filter-toggle">
            <input type="checkbox" v-model="hideClosed" />
            クローズを非表示
          </label>
        </div>

        <div v-if="loading" class="loading">読み込み中…</div>
        <p v-if="error" class="error">{{ error }}</p>

        <ul v-if="!loading" class="session-items">
          <li
            v-for="s in filteredSessions"
            :key="s.id"
            class="session-item"
            @click="selectSession(s)"
          >
            <span v-if="s.unread_count > 0" class="session-item__unread-dot" />
            <div class="session-main">
              <div class="session-title">
                {{ displaySessionTitle(s) }}
              </div>

              <div class="session-meta">
                <span
                  class="session-status"
                  :class="`session-status--${s.status}`"
                >
                  {{ s.status === "OPEN" ? "対応中" : "クローズ" }}
                </span>
                <span class="session-time">
                  {{ formatTime(s.last_active_at) }}
                </span>
              </div>
            </div>

            <button
              v-if="s.status === 'OPEN'"
              class="close-btn"
              @click.stop="closeSession(s.id)"
            >
              対応済み
            </button>
          </li>
        </ul>
      </aside>

      <!-- 右側：チャット詳細 -->
      <main class="chat-detail">
        <div v-if="!selectedSessionId" class="empty-chat">
          左のセッションを選択してください
        </div>

        <div v-else class="chat-panel">
          <header class="chat-panel__header">
            <div class="chat-panel__header-left">
              <div class="chat-panel__avatar">
                <span>CS</span>
              </div>
              <div>
                <h2 class="chat-panel__title">サポートチャット</h2>
                <p class="chat-panel__subtitle">
                  {{ selectedSessionName || "訪問者" }} さんとの会話
                </p>
              </div>
            </div>
            <div
              class="chat-panel__status"
              :class="{ 'chat-panel__status--online': isConnected }"
            >
              <span class="chat-panel__status-dot" />
              <span class="chat-panel__status-text">
                {{ isConnected ? "オンライン" : "接続中…" }}
              </span>
            </div>
          </header>

          <!-- メッセージ一覧 -->
          <main class="chat-panel__messages">
            <transition-group name="msg" tag="div">
              <div
                v-for="m in messages"
                :key="m.id"
                class="msg"
                :class="m.sender_type === 'OPERATOR' ? 'msg--me' : 'msg--other'"
              >
                <div class="msg__inner">
                  <!-- 画像付きメッセージ -->
                  <div
                    v-if="m.attachment_url"
                    class="msg__image-wrapper"
                    @click="openImagePreview(API_BASE + m.attachment_url)"
                  >
                    <img
                      :src="API_BASE + m.attachment_url"
                      alt="添付画像"
                      class="msg-image"
                    />
                  </div>

                  <!-- 通常テキストメッセージ -->
                  <div v-else class="msg__bubble">
                    <p class="msg__text">{{ m.content }}</p>
                  </div>

                  <div class="msg__time">
                    {{ formatTime(m.created_at) }}
                  </div>
                </div>
              </div>
            </transition-group>

            <div v-if="messages.length === 0" class="chat-panel__empty">
              <p>まだメッセージはありません。</p>
              <p>右下の入力欄からメッセージを送信してみましょう。</p>
            </div>
          </main>

          <!-- 入力エリア -->
          <footer class="chat-panel__footer">
            <button
              type="button"
              class="chat-panel__button chat-panel__button--icon"
              @click="openFilePicker"
            >
              ＋
            </button>

            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              style="display: none"
              @change="handleFileChange"
            />

            <input
              v-model="inputText"
              type="text"
              class="chat-panel__input"
              placeholder="メッセージを入力して Enter で送信"
              @keyup.enter="sendMessage"
            />

            <button
              class="chat-panel__button"
              @click="sendMessage"
              :disabled="!isConnected || !inputText.trim()"
            >
              送信
            </button>
          </footer>
        </div>
      </main>
    </div>
  </div>

  <div
    v-if="previewImageUrl"
    class="image-preview"
    @click.self="closeImagePreview"
  >
    <div class="image-preview__inner">
      <img :src="previewImageUrl" alt="preview" class="image-preview__img" />
      <button class="image-preview__close" @click="closeImagePreview">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from "vue";
import { useRouter } from "vue-router";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";
const router = useRouter();

const sessions = ref([]);
const loading = ref(false);
const error = ref("");

const selectedSessionId = ref(null);
const selectedSessionName = ref("");

const messages = ref([]);
const inputText = ref("");
const companyName = ref("");
const socket = ref(null);
const isConnected = ref(false);

const hideClosed = ref(false);
const currentUser = ref(null);

const menuOpen = ref(false);
const toggleMenu = () => (menuOpen.value = !menuOpen.value);
const closeMenu = () => (menuOpen.value = false);

const onDocClick = (e) => {
  if (!menuOpen.value) return;
  const btn = document.querySelector(".menu-btn");
  const panel = document.querySelector(".menu-panel");
  if (!btn || !panel) return;
  if (btn.contains(e.target) || panel.contains(e.target)) return;
  closeMenu();
};
document.addEventListener("click", onDocClick);

// 画像プレビュー用
const previewImageUrl = ref(null);
const openImagePreview = (url) => (previewImageUrl.value = url);
const closeImagePreview = () => (previewImageUrl.value = null);

const fileInput = ref(null);
const openFilePicker = () => fileInput.value?.click();

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  await uploadImage(file);
  event.target.value = "";
};

const uploadImage = async (file) => {
  if (!selectedSessionId.value) {
    alert("先に左側でセッションを選択してください");
    return;
  }
  if (!socket.value || !isConnected.value) {
    alert("接続中ではありません");
    return;
  }

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: form,
    });
    const data = await res.json();

    if (!res.ok || !data.url) {
      console.error("upload error:", data);
      alert("画像アップロードに失敗しました");
      return;
    }

    socket.value.emit("operator_message", {
      session_id: selectedSessionId.value,
      content: "",
      attachment_url: data.url,
    });
  } catch (e) {
    console.error(e);
    alert("画像アップロードでエラーが発生しました");
  }
};

const fetchMe = async () => {
  const token = localStorage.getItem("admin_token");
  if (!token) return;

  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return;
  currentUser.value = await res.json();
};

// ---- 共通の時刻フォーマット（JST） ----
const formatTime = (isoString) => {
  if (!isoString) return "";
  const fixed = isoString.endsWith("Z") ? isoString : isoString + "Z";
  return new Date(fixed).toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const scrollMessagesToBottom = () => {
  requestAnimationFrame(() => {
    const container = document.querySelector(".chat-panel__messages");
    if (container) container.scrollTop = container.scrollHeight;
  });
};

// クローズ非表示用のフィルタ済みセッション＋ソート
const filteredSessions = computed(() => {
  let list = sessions.value;
  if (hideClosed.value) list = list.filter((s) => s.status !== "CLOSED");

  return [...list].sort((a, b) => {
    const unreadA = (a.unread_count || 0) > 0;
    const unreadB = (b.unread_count || 0) > 0;
    if (unreadA !== unreadB) return unreadA ? -1 : 1;

    const openA = a.status === "OPEN";
    const openB = b.status === "OPEN";
    if (openA !== openB) return openA ? -1 : 1;

    const tA = a.last_active_at ? new Date(a.last_active_at).getTime() : 0;
    const tB = b.last_active_at ? new Date(b.last_active_at).getTime() : 0;
    return tB - tA;
  });
});

// ---- 会社情報取得 ----
const fetchCompany = async () => {
  const token = localStorage.getItem("admin_token");
  if (!token) {
    router.push("/admin/login");
    return;
  }

  const res = await fetch(`${API_BASE}/api/company/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    router.push("/admin/login");
    return;
  }

  if (!res.ok) {
    console.error("会社情報の取得に失敗しました");
    return;
  }

  const data = await res.json();
  companyName.value = data.name || "";
};

// ---- セッション一覧取得 ----
const fetchSessions = async () => {
  loading.value = true;
  error.value = "";

  const token = localStorage.getItem("admin_token");
  if (!token) {
    loading.value = false;
    router.push("/admin/login");
    return;
  }

  const res = await fetch(`${API_BASE}/api/sessions`, {
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

// ---- 指定セッションのメッセージ履歴取得 ----
const fetchMessages = async (sessionId) => {
  if (!sessionId) return;

  const token = localStorage.getItem("admin_token");
  if (!token) {
    router.push("/admin/login");
    return;
  }

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401) {
    localStorage.removeItem("admin_token");
    router.push("/admin/login");
    return;
  }

  if (!res.ok) {
    error.value = "メッセージの取得に失敗しました";
    return;
  }

  messages.value = await res.json();
  messages.value = messages.value.map((m) => ({
    ...m,
    sender_type: m.sender_type ? m.sender_type.toUpperCase() : m.sender_type,
  }));
  scrollMessagesToBottom();
};

// ---- セッション選択 ----
const selectSession = (session) => {
  selectedSessionId.value = session.id;
  selectedSessionName.value = session.visitor_name || "ゲスト";
};

// ---- Socket.IO 接続 ----
const connectSocket = () => {
  if (socket.value) return;

  socket.value = io(API_BASE, {
    path: "/ws/socket.io",
    withCredentials: false,
  });

  socket.value.on("connect", () => {
    isConnected.value = true;
    console.log("[admin] socket connected", socket.value.id);

    socket.value.emit("join_session", {
      session_id: null,
      role: "operator",
    });

    if (selectedSessionId.value) {
      socket.value.emit("join_session", {
        session_id: selectedSessionId.value,
        role: "operator",
      });
    }
  });

  socket.value.on("disconnect", () => {
    isConnected.value = false;
    console.log("[admin] socket disconnected");
  });

  socket.value.on("new_message", async (msg) => {
    if (msg.sender_type) msg.sender_type = msg.sender_type.toUpperCase();

    if (msg.sender_type === "VISITOR") {
      const target = sessions.value.find((s) => s.id === msg.session_id);

      if (target) {
        if (target.status === "CLOSED") target.status = "OPEN";
        if (msg.session_id !== selectedSessionId.value) {
          target.unread_count = (target.unread_count || 0) + 1;
        }
        target.last_active_at = msg.created_at || new Date().toISOString();
      } else {
        await fetchSessions();
      }
    }

    if (msg.session_id === selectedSessionId.value) {
      await fetchMessages(selectedSessionId.value);
    }
  });

  socket.value.on("session_created", async ({ session_id }) => {
    console.log("[admin] new session detected:", session_id);
    await fetchSessions();
  });
};

// 選択されたセッションが変わったら履歴取得＋ルーム join
watch(selectedSessionId, async (newId) => {
  messages.value = [];
  if (!newId) return;

  await fetchMessages(newId);

  const target = sessions.value.find((s) => s.id === newId);
  if (target) target.unread_count = 0;

  if (socket.value && isConnected.value) {
    socket.value.emit("join_session", { session_id: newId, role: "operator" });
  }
});

// ---- メッセージ送信（オペレーター側） ----
const sendMessage = () => {
  const text = inputText.value.trim();
  if (!text || !socket.value || !isConnected.value || !selectedSessionId.value)
    return;

  socket.value.emit("operator_message", {
    session_id: selectedSessionId.value,
    content: text,
  });

  inputText.value = "";
};

// ---- ログアウト ----
const logout = () => {
  localStorage.removeItem("admin_token");
  closeMenu();
  router.push("/admin/login");
};

onMounted(() => {
  connectSocket();
  fetchSessions();
  fetchCompany();
  fetchMe();
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
  if (socket.value) socket.value.disconnect();
});

const closeSession = async (sessionId) => {
  const token = localStorage.getItem("admin_token");
  if (!token) return;

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/close`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.ok) {
    fetchSessions();

    if (sessionId === selectedSessionId.value) {
      selectedSessionId.value = null;
      messages.value = [];
    }
  } else {
    alert("ステータス変更に失敗しました");
  }
};

const displaySessionTitle = (s) => {
  const shortId = s.id ? s.id.slice(0, 4) : "----";
  return shortId;
};
</script>

<style>
.admin-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8fafc;
  font-family: sans-serif;
}

/* ヘッダー */
.admin-header {
  padding: 12px 20px;
  background: #e0f7fa;
  border-bottom: 1px solid #bae6fd;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.admin-header h1 {
  margin: 0;
  font-size: 18px;
  color: #0284c7;
  font-weight: 600;
}

.header-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}

.menu-btn {
  border: none;
  border-radius: 999px;
  width: 40px;
  height: 40px;
  font-size: 18px;
  font-weight: 900;
  background: #e2e8f0;
  color: #0f172a;
  cursor: pointer;
}

.menu-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 180px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
  padding: 8px;
  z-index: 1000;
}

.menu-item {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 10px 10px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  cursor: pointer;
}

.menu-item:hover {
  background: #f1f5f9;
}

.menu-sep {
  height: 1px;
  background: #e2e8f0;
  margin: 6px 0;
}

.menu-item.danger {
  color: #b91c1c;
}
.menu-item.danger:hover {
  background: #fff1f2;
}

.admin-body {
  flex: 1;
  display: flex;
}

.session-list {
  width: 280px;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  padding: 16px;
  overflow-y: auto;
}

.session-list h2 {
  margin: 0 0 8px;
  font-size: 15px;
  color: #0f172a;
}

.session-filters {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.filter-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
}

.filter-toggle input[type="checkbox"] {
  accent-color: #4fc3f7;
  width: 13px;
  height: 13px;
  cursor: pointer;
}

.session-items {
  padding: 0;
  list-style: none;
  margin: 0;
}

.session-item {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  background: #f1f5f9;
  margin-bottom: 8px;
  transition: background 0.15s ease, transform 0.1s ease;
  position: relative;
}

.session-item:hover {
  background: #e0f2fe;
  transform: translateY(-1px);
}

.session-item.active {
  background: #bae6fd;
}

.session-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}

.session-meta {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #64748b;
}

.session-status {
  text-transform: uppercase;
}

.session-time {
  font-variant-numeric: tabular-nums;
}

.loading {
  font-size: 13px;
  color: #64748b;
}

.error {
  color: #ef5350;
  font-size: 13px;
  margin-bottom: 8px;
}

.chat-detail {
  flex: 1;
  padding: 16px 24px;
  display: flex;
  align-items: stretch;
}

.empty-chat {
  margin: auto;
  text-align: center;
  color: #94a3b8;
}

.chat-panel {
  margin: 0;
  width: 100%;
  max-width: none;
  height: 100%;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
  display: flex;
  flex-direction: column;
  color: #1e293b;
  overflow: hidden;
}

.chat-panel__header {
  padding: 12px 16px;
  border-bottom: 1px solid #bae6fd;
  background: #e0f7fa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-panel__header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-panel__avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: #4fc3f7;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
}

.chat-panel__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0284c7;
}

.chat-panel__subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #64748b;
}

.chat-panel__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #94a3b8;
  background: #f8fafc;
  font-size: 11px;
  color: #475569;
}

.chat-panel__status--online {
  border-color: #4fc3f7;
  color: #0284c7;
}

.chat-panel__status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
}

.chat-panel__status--online .chat-panel__status-dot {
  background: #4fc3f7;
}

.chat-panel__messages {
  flex: 1;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  background: #f8fafc;
}

.msg {
  display: flex;
}

.msg--me {
  justify-content: flex-end;
}

.msg--other {
  justify-content: flex-start;
}

.msg__inner {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  margin: 2px 0;
}

.msg--me .msg__inner {
  margin-left: auto;
  align-items: flex-end;
}

.msg--other .msg__inner {
  align-items: flex-start;
}

.msg__bubble {
  max-width: 100%;
  padding: 7px 11px;
  border-radius: 16px;
  font-size: 13px;
  line-height: 1.4;
}

.msg--me .msg__bubble {
  background: #e0f7fa;
  border: 1px solid #bae6fd;
  color: #0369a1;
}

.msg--other .msg__bubble {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #1e293b;
}

.msg__text {
  margin: 0;
}

.msg__time {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1;
  color: #94a3b8;
}

.msg--me .msg__time {
  text-align: right;
}

.msg--other .msg__time {
  text-align: left;
}

.chat-panel__empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.chat-panel__footer {
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  background: #ffffff;
}

.chat-panel__input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: white;
  color: #1e293b;
  font-size: 13px;
}

.chat-panel__input:focus {
  outline: none;
  border-color: #4fc3f7;
}

.chat-panel__button {
  padding: 8px 16px;
  border-radius: 999px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  background: #4fc3f7;
  color: white;
  cursor: pointer;
}

.chat-panel__button:disabled {
  opacity: 0.6;
  cursor: default;
}

.msg-enter-active {
  transition: all 0.16s ease-out;
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

.session-item__unread-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #4fc3f7;
  position: absolute;
  top: 6px;
  right: 8px;
}

.close-btn {
  margin-top: 6px;
  padding: 3px 8px;
  font-size: 11px;
  border: none;
  background: #60a5fa;
  color: white;
  border-radius: 999px;
  cursor: pointer;
}

.close-btn:hover {
  background: #3b82f6;
}

.msg__image-wrapper {
  max-width: 70%;
  cursor: pointer;
}

.msg-image {
  width: 100%;
  height: auto;
  border-radius: 12px;
  display: block;
}

.msg--me .msg__image-wrapper {
  margin-left: auto;
}

.msg--other .msg__image-wrapper {
  margin-right: auto;
}

.chat-panel__button--icon {
  padding-inline: 10px;
}

.image-preview {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.image-preview__inner {
  position: relative;
  max-width: 80%;
  max-height: 80%;
}

.image-preview__img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 10px;
  display: block;
}

.image-preview__close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: none;
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
