<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";

// --- チャット用状態 ---
const sessions = ref([]);
const selectedSessionId = ref(null);
const messages = ref([]);
const inputText = ref("");

const socket = ref(null);
const isConnected = ref(false);

// --- ログイン状態 ---
const TOKEN_KEY = "chat_admin_token";

const email = ref("admin@example.com");
const password = ref("password");
const token = ref(localStorage.getItem(TOKEN_KEY) || "");
const isLoggedIn = ref(!!token.value);
const loginError = ref("");

// 共通ヘッダー（認証付き）
const authHeaders = () => {
  const headers = {};
  if (token.value) {
    headers["Authorization"] = `Bearer ${token.value}`;
  }
  return headers;
};

// --------- 認証処理 ---------
const login = async () => {
  loginError.value = "";
  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email.value,
        password: password.value,
      }),
    });

    if (!res.ok) {
      loginError.value = "メールアドレスまたはパスワードが違います";
      return;
    }

    const data = await res.json();
    token.value = data.access_token;
    localStorage.setItem(TOKEN_KEY, token.value);
    isLoggedIn.value = true;

    // ログインに成功したらセッション一覧取得
    await fetchSessions();
  } catch (e) {
    console.error(e);
    loginError.value = "ログインに失敗しました";
  }
};

// --------- REST API ---------
const fetchSessions = async () => {
  if (!isLoggedIn.value || !token.value) return;

  try {
    const res = await fetch(`${API_BASE}/api/sessions`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      console.error("failed to fetch sessions", res.status);
      return;
    }
    sessions.value = await res.json();
  } catch (e) {
    console.error("failed to fetch sessions", e);
  }
};

const loadMessages = async (sessionId) => {
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`);
    if (!res.ok) {
      console.error("failed to fetch messages", res.status);
      return;
    }
    messages.value = await res.json();
  } catch (e) {
    console.error("failed to fetch messages", e);
  }
};

// --------- UI 操作 ---------
const selectSession = async (sessionId) => {
  selectedSessionId.value = sessionId;
  await loadMessages(sessionId);

  if (socket.value && isConnected.value) {
    socket.value.emit("join_session", {
      session_id: sessionId,
      role: "operator",
    });
  }
};

// --------- Socket.IO ---------
const connectSocket = () => {
  socket.value = io("http://localhost:8000", {
    path: "/ws/socket.io",
    withCredentials: false,
  });

  socket.value.on("connect", () => {
    isConnected.value = true;
    console.log("[admin] socket connected", socket.value.id);

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

  socket.value.on("new_message", (msg) => {
    if (msg.session_id === selectedSessionId.value) {
      messages.value.push(msg);
    }
  });
};

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

onMounted(async () => {
  connectSocket();
  if (isLoggedIn.value) {
    await fetchSessions();
  }
});

onBeforeUnmount(() => {
  if (socket.value) socket.value.disconnect();
});
</script>

<template>
  <div class="admin">
    <!-- ログイン前 -->
    <div v-if="!isLoggedIn" class="admin__login">
      <div class="admin__login-card">
        <h2>管理者ログイン</h2>
        <div class="admin__login-form">
          <label>
            メールアドレス
            <input v-model="email" type="email" />
          </label>
          <label>
            パスワード
            <input v-model="password" type="password" />
          </label>
          <button @click="login">ログイン</button>
          <p v-if="loginError" class="admin__login-error">{{ loginError }}</p>
          <p class="admin__hint">
            デフォルト: <code>admin@example.com</code> / <code>password</code>
          </p>
        </div>
      </div>
    </div>

    <!-- ログイン後の管理画面 -->
    <template v-else>
      <aside class="admin__sidebar">
        <h2 class="admin__sidebar-title">セッション一覧</h2>
        <ul class="admin__session-list">
          <li
            v-for="s in sessions"
            :key="s.id"
            class="admin__session-item"
            :class="{
              'admin__session-item--active': s.id === selectedSessionId,
            }"
            @click="selectSession(s.id)"
          >
            <div class="admin__session-main">
              <span class="admin__session-visitor">
                {{ s.visitor_identifier }}
              </span>
            </div>
            <small class="admin__session-status">
              {{ s.status }} / 最終更新:
              {{ new Date(s.last_active_at).toLocaleString() }}
            </small>
          </li>
        </ul>
      </aside>

      <main class="admin__main">
        <div v-if="!selectedSessionId" class="admin__placeholder">
          左のリストからセッションを選択してください
        </div>

        <div v-else class="admin__chat">
          <header class="admin__chat-header">
            <h2>Session: {{ selectedSessionId }}</h2>
          </header>

          <section class="admin__messages">
            <div
              v-for="m in messages"
              :key="m.id"
              class="msg"
              :class="m.sender_type === 'operator' ? 'msg--me' : 'msg--other'"
            >
              <div class="msg__bubble">
                <p>{{ m.content }}</p>
              </div>
            </div>
          </section>

          <footer class="admin__footer">
            <input
              v-model="inputText"
              type="text"
              placeholder="メッセージを入力..."
              @keyup.enter="sendMessage"
            />
            <button
              @click="sendMessage"
              :disabled="!inputText.trim() || !isConnected"
            >
              送信
            </button>
          </footer>
        </div>
      </main>
    </template>
  </div>
</template>

<style scoped>
.admin {
  display: flex;
  height: 100%;
  min-height: 540px;
  background: #020617;
  color: #e5e7eb;
  border-radius: 16px;
  border: 1px solid #1f2937;
  overflow: hidden;
  box-shadow: 0 18px 35px rgba(0, 0, 0, 0.45);
}

/* --- ログイン画面 --- */
.admin__login {
  margin: auto;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.admin__login-card {
  background: #020617;
  border-radius: 16px;
  border: 1px solid #1f2937;
  padding: 24px 28px;
  max-width: 420px;
  width: 100%;
  box-shadow: 0 18px 35px rgba(0, 0, 0, 0.45);
}

.admin__login-card h2 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 600;
}

.admin__login-form label {
  display: block;
  font-size: 13px;
  margin-bottom: 10px;
}

.admin__login-form input {
  width: 100%;
  margin-top: 4px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid #374151;
  background: #020617;
  color: #e5e7eb;
  font-size: 13px;
}

.admin__login-form input:focus {
  outline: none;
  border-color: #22c55e;
}

.admin__login-form button {
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  border: none;
  background: #22c55e;
  color: #022c22;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.admin__login-error {
  margin-top: 8px;
  color: #f97373;
  font-size: 12px;
}

.admin__hint {
  margin-top: 8px;
  font-size: 11px;
  color: #9ca3af;
}

.admin__hint code {
  background: #020617;
  padding: 2px 4px;
  border-radius: 4px;
}

/* --- 管理画面 --- */
.admin__sidebar {
  width: 260px;
  border-right: 1px solid #1f2937;
  padding: 12px 10px;
  background: #020617;
}

.admin__sidebar-title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 600;
}

.admin__session-list {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 100%;
  overflow-y: auto;
}

.admin__session-item {
  padding: 8px 8px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 4px;
  background: transparent;
  transition: background 0.15s ease;
}

.admin__session-item:hover {
  background: #0b1120;
}

.admin__session-item--active {
  background: #1f2937;
}

.admin__session-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.admin__session-visitor {
  font-size: 13px;
  font-weight: 500;
}

.admin__session-status {
  font-size: 11px;
  color: #9ca3af;
}

.admin__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #020617;
}

.admin__placeholder {
  margin: auto;
  font-size: 14px;
  color: #9ca3af;
}

.admin__chat-header {
  padding: 10px 14px;
  border-bottom: 1px solid #1f2937;
}

.admin__messages {
  flex: 1;
  padding: 10px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
.msg__bubble {
  max-width: 75%;
  padding: 6px 10px;
  border-radius: 12px;
  background: #1f2937;
  font-size: 13px;
}
.msg--me .msg__bubble {
  background: #22c55e;
  color: #064e3b;
}

.admin__footer {
  padding: 8px 10px;
  border-top: 1px solid #1f2937;
  display: flex;
  gap: 6px;
}

.admin__footer input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid #374151;
  background: #020617;
  color: #e5e7eb;
}

.admin__footer input:focus {
  outline: none;
  border-color: #22c55e;
}

.admin__footer button {
  padding: 6px 14px;
  border-radius: 999px;
  border: none;
  background: #22c55e;
  color: #022c22;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.admin__footer button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
