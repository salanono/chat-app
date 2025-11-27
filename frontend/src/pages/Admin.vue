<!-- frontend/src/pages/Admin.vue -->
<template>
  <div class="admin-page">
    <div class="admin-shell">
      <!-- ヘッダー -->
      <header class="admin-header">
        <div class="admin-header-left">
          <div class="admin-logo">
            <span>CS</span>
          </div>
          <div>
            <h1 class="admin-title">サポート管理画面</h1>
            <p class="admin-subtitle">
              訪問者とのチャットをリアルタイムに確認・返信できます
            </p>
          </div>
        </div>

        <button class="logout-btn" @click="logout">ログアウト</button>
      </header>

      <!-- メイン 2カラム -->
      <main class="admin-main">
        <p v-if="error" class="admin-error">{{ error }}</p>

        <div class="admin-layout">
          <!-- 左カラム：セッション一覧 -->
          <aside class="sessions-pane">
            <div class="sessions-header">
              <div>
                <h2 class="sessions-title">セッション一覧</h2>
                <p class="sessions-subtitle">
                  現在 {{ sessions.length }} 件のセッションがあります
                </p>
              </div>
              <button
                class="refresh-btn"
                @click="fetchSessions"
                :disabled="loading"
              >
                {{ loading ? "更新中..." : "再読込" }}
              </button>
            </div>

            <div v-if="sessions.length === 0" class="sessions-empty">
              <p>まだセッションがありません。</p>
              <p>ウィジェットからメッセージが来ると、ここに表示されます。</p>
            </div>

            <ul v-else class="session-list">
              <li
                v-for="s in sessions"
                :key="s.id"
                class="session-item"
                :class="{ 'session-item--active': s.id === selectedSessionId }"
                @click="selectSession(s)"
              >
                <div class="session-main-row">
                  <div class="session-visitor">
                    <div class="session-avatar">
                      <span>{{ (s.visitor_name || "名無し")[0] }}</span>
                    </div>
                    <div>
                      <div class="session-name">
                        {{ s.visitor_name || "名無しのお客さま" }}
                      </div>
                      <div class="session-id">
                        ID: {{ s.visitor_identifier }}
                      </div>
                    </div>
                  </div>

                  <span
                    class="session-status"
                    :class="
                      s.status === 'OPEN'
                        ? 'session-status--open'
                        : 'session-status--closed'
                    "
                  >
                    {{ s.status === "OPEN" ? "対応中" : "クローズ" }}
                  </span>
                </div>

                <div class="session-meta-row">
                  <span class="session-time">
                    最終: {{ formatTime(s.last_active_at) }}
                  </span>
                </div>
              </li>
            </ul>
          </aside>

          <!-- 右カラム：チャット詳細 -->
          <section class="chat-pane">
            <div v-if="!selectedSessionId" class="chat-empty">
              <p class="chat-empty-title">セッションを選択してください</p>
              <p class="chat-empty-text">
                左の一覧からセッションを選ぶと、ここにメッセージが表示されます。
              </p>
            </div>

            <div v-else class="chat-panel">
              <!-- チャットヘッダー（ウィジェット風） -->
              <header class="chat-header">
                <div class="chat-header-left">
                  <div class="chat-avatar">
                    <span>CS</span>
                  </div>
                  <div>
                    <h2 class="chat-title">
                      {{ currentSessionName }}
                    </h2>
                    <p class="chat-subtitle">
                      訪問者ID: {{ currentSessionIdText }}
                    </p>
                  </div>
                </div>

                <div
                  class="chat-status"
                  :class="{ 'chat-status--online': isSocketConnected }"
                >
                  <span class="chat-status-dot" />
                  <span class="chat-status-text">
                    {{
                      isSocketConnected
                        ? "リアルタイム接続中"
                        : "再接続しています…"
                    }}
                  </span>
                </div>
              </header>

              <!-- メッセージ一覧 -->
              <main class="chat-messages" ref="messagesContainerRef">
                <transition-group name="msg" tag="div">
                  <div
                    v-for="m in messages"
                    :key="m.id"
                    class="msg"
                    :class="
                      m.sender_type === 'operator' ? 'msg--me' : 'msg--other'
                    "
                  >
                    <div class="msg__inner">
                      <div class="msg__bubble">
                        <p class="msg__text">{{ m.content }}</p>
                      </div>
                      <div class="msg__time">
                        {{ formatTime(m.created_at) }}
                      </div>
                    </div>
                  </div>
                </transition-group>

                <div v-if="messages.length === 0" class="chat-messages-empty">
                  <p>まだメッセージはありません。</p>
                  <p>訪問者からの最初のメッセージをお待ちください。</p>
                </div>
              </main>

              <!-- 入力エリア -->
              <footer class="chat-footer">
                <input
                  v-model="chatInput"
                  type="text"
                  class="chat-input"
                  placeholder="メッセージを入力して Enter で送信"
                  @keyup.enter="sendMessage"
                />
                <button
                  class="chat-send-btn"
                  @click="sendMessage"
                  :disabled="!isSocketConnected || !chatInput.trim()"
                >
                  送信
                </button>
              </footer>
            </div>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";

const router = useRouter();

const sessions = ref([]);
const loading = ref(false);
const error = ref("");

const selectedSessionId = ref(null);
const messages = ref([]);
const chatInput = ref("");

// socket 関連
const socket = ref(null);
const isSocketConnected = ref(false);

// メッセージエリア参照
const messagesContainerRef = ref(null);

const currentSession = computed(
  () => sessions.value.find((s) => s.id === selectedSessionId.value) || null
);

const currentSessionName = computed(() =>
  currentSession.value
    ? currentSession.value.visitor_name || "名無しのお客さま"
    : ""
);

const currentSessionIdText = computed(() =>
  currentSession.value ? currentSession.value.visitor_identifier : ""
);

// 時刻整形（セッション一覧とチャットの両方で使う）
const formatTime = (isoString) => {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;

  return d.toLocaleString("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const scrollMessagesToBottom = () => {
  requestAnimationFrame(() => {
    const el = messagesContainerRef.value;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });
};

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

const fetchMessages = async (sessionId) => {
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
    error.value = "メッセージ取得に失敗しました";
    return;
  }

  messages.value = await res.json();
  scrollMessagesToBottom();
};

// セッション選択
const selectSession = async (session) => {
  if (!session || session.id === selectedSessionId.value) return;

  selectedSessionId.value = session.id;
  await fetchMessages(session.id);

  // 選択したセッションの room に join
  if (socket.value && isSocketConnected.value) {
    socket.value.emit("join_session", {
      session_id: session.id,
      role: "operator",
    });
  }
};

// メッセージ送信（オペレーター → ビジター）
const sendMessage = () => {
  const text = chatInput.value.trim();
  if (
    !text ||
    !selectedSessionId.value ||
    !socket.value ||
    !isSocketConnected.value
  ) {
    return;
  }

  socket.value.emit("operator_message", {
    session_id: selectedSessionId.value,
    content: text,
  });

  chatInput.value = "";
};

// Socket.IO 接続
const connectSocket = () => {
  socket.value = io(API_BASE, {
    path: "/ws/socket.io",
    withCredentials: false,
  });

  socket.value.on("connect", () => {
    isSocketConnected.value = true;
    console.log("[admin] socket connected", socket.value.id);

    // すでに選択中のセッションがあれば join
    if (selectedSessionId.value) {
      socket.value.emit("join_session", {
        session_id: selectedSessionId.value,
        role: "operator",
      });
    }
  });

  socket.value.on("disconnect", () => {
    isSocketConnected.value = false;
    console.log("[admin] socket disconnected");
  });

  socket.value.on("new_message", (msg) => {
    // 現在見ているセッションのメッセージなら追加
    if (msg.session_id === selectedSessionId.value) {
      messages.value.push(msg);
      scrollMessagesToBottom();
    }

    // 対応するセッションの last_active_at も軽く更新
    const idx = sessions.value.findIndex((s) => s.id === msg.session_id);
    if (idx !== -1) {
      sessions.value[idx] = {
        ...sessions.value[idx],
        last_active_at: msg.created_at,
      };
    }
  });
};

// ログアウト
const logout = () => {
  localStorage.removeItem("admin_token");
  router.push("/admin/login");
};

onMounted(async () => {
  await fetchSessions();
  connectSocket();
});

onBeforeUnmount(() => {
  if (socket.value) {
    socket.value.disconnect();
  }
});
</script>

<style>
.admin-page {
  min-height: 100vh;
  margin: 0;
  padding: 24px;
  background: #f3f4f6;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  box-sizing: border-box;
}

.admin-shell {
  width: 1160px;
  max-width: 100%;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.15);
  border: 1px solid #e2e8f0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ヘッダー：ウィジェット系 */
.admin-header {
  padding: 14px 18px;
  border-bottom: 1px solid #bae6fd;
  background: #e0f7fa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.admin-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-logo {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: #4fc3f7;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
}

.admin-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #0284c7;
}

.admin-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #64748b;
}

/* ログアウトボタン */
.logout-btn {
  background: #f97373;
  color: white;
  padding: 8px 14px;
  border: none;
  cursor: pointer;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 6px 14px rgba(248, 113, 113, 0.35);
}

.logout-btn:hover {
  background: #ef4444;
}

/* メイン */
.admin-main {
  padding: 12px 16px 16px;
}

.admin-error {
  padding: 8px 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 13px;
  margin-bottom: 10px;
}

/* 2カラムレイアウト */
.admin-layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: 12px;
  height: 640px;
}

/* 左：セッション一覧 */
.sessions-pane {
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px 10px 12px;
  display: flex;
  flex-direction: column;
}

.sessions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sessions-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}

.sessions-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.refresh-btn {
  border: none;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  background: #e0f7fa;
  color: #0284c7;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.sessions-empty {
  padding: 18px 12px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.session-list {
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-item {
  padding: 8px 9px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: background 0.12s ease, box-shadow 0.12s ease,
    border-color 0.12s ease;
}

.session-item:hover {
  background: #f1f5f9;
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04);
}

.session-item--active {
  border-color: #4fc3f7;
  background: #e0f7fa;
  box-shadow: 0 6px 16px rgba(56, 189, 248, 0.25);
}

.session-main-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.session-visitor {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-avatar {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: #e0f7fa;
  color: #0284c7;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.session-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.session-id {
  font-size: 11px;
  color: #9ca3af;
}

.session-status {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
  white-space: nowrap;
}

.session-status--open {
  border-color: #4fc3f7;
  background: #e0f7fa;
  color: #0284c7;
}

.session-status--closed {
  border-color: #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
}

.session-meta-row {
  display: flex;
  justify-content: flex-end;
  font-size: 11px;
  color: #94a3b8;
}

.session-time {
  white-space: nowrap;
}

/* 右：チャット詳細 */
.chat-pane {
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  flex-direction: column;
}

.chat-empty {
  margin: auto;
  text-align: center;
  padding: 24px;
  color: #94a3b8;
}

.chat-empty-title {
  font-size: 16px;
  margin-bottom: 8px;
  color: #0f172a;
}

.chat-empty-text {
  font-size: 13px;
}

/* チャットパネル（ウィジェットっぽい） */
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* チャットヘッダー */
.chat-header {
  padding: 10px 12px;
  border-bottom: 1px solid #bae6fd;
  background: #e0f7fa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: #4fc3f7;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.chat-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0284c7;
}

.chat-subtitle {
  margin: 2px 0 0;
  font-size: 11px;
  color: #64748b;
}

.chat-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid #94a3b8;
  background: #f8fafc;
  font-size: 11px;
  color: #475569;
}

.chat-status--online {
  border-color: #4fc3f7;
  color: #0284c7;
}

.chat-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
}

.chat-status--online .chat-status-dot {
  background: #4fc3f7;
}

/* メッセージ一覧 */
.chat-messages {
  flex: 1;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  background: #f8fafc;
}

/* メッセージコンテナ */
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
  max-width: 75%;
  margin: 2px 0;
}

.msg--me .msg__inner {
  margin-left: auto;
  align-items: flex-end;
}

.msg--other .msg__inner {
  align-items: flex-start;
}

/* 吹き出し */
.msg__bubble {
  max-width: 100%;
  padding: 6px 10px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.4;
}

/* 管理者（オペレーター）= 右 */
.msg--me .msg__bubble {
  background: #e0f7fa;
  border: 1px solid #bae6fd;
  color: #0369a1;
}

/* 訪問者 = 左 */
.msg--other .msg__bubble {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #1e293b;
}

.msg__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.4;
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

.chat-messages-empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

/* 入力エリア */
.chat-footer {
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  background: #ffffff;
}

.chat-input {
  flex: 1;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: white;
  color: #1e293b;
  font-size: 13px;
}

.chat-input:focus {
  outline: none;
  border-color: #4fc3f7;
}

.chat-send-btn {
  padding: 7px 14px;
  border-radius: 999px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  background: #4fc3f7;
  color: white;
  cursor: pointer;
}

.chat-send-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

/* メッセージ追加アニメーション */
.msg-enter-active {
  transition: all 0.16s ease-out;
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

/* スクロールバー */
.session-list::-webkit-scrollbar,
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-thumb,
.chat-messages::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 999px;
}

@media (max-width: 960px) {
  .admin-layout {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-pane {
    margin-top: 12px;
    min-height: 420px;
  }
}
</style>
