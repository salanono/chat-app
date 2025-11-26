<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";

const messages = ref([]);
const inputText = ref("");
const socket = ref(null);
const sessionId = ref(null);
const isConnected = ref(false);
const isOpen = ref(true); // ← ウィジェットの開閉状態（埋め込むときは false スタートでもOK）

// ---- visitor_identifier を localStorage で管理 ----
const createVisitorIdentifier = () => {
  const key = "chat_visitor_id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = "visitor_" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(key, id);
  }
  return id;
};

// ---- セッション作成 or 取得 ----
const fetchOrCreateSession = async () => {
  const visitor_identifier = createVisitorIdentifier();
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitor_identifier }),
  });
  const data = await res.json();
  sessionId.value = data.id;
};

// ---- 過去メッセージ取得 ----
const loadHistory = async () => {
  if (!sessionId.value) return;
  const res = await fetch(
    `${API_BASE}/api/sessions/${sessionId.value}/messages`
  );
  const data = await res.json();
  messages.value = data;
};

// ---- Socket.IO 接続 ----
const connectSocket = () => {
  socket.value = io("http://localhost:8000", {
    path: "/ws/socket.io",
    withCredentials: false,
  });

  socket.value.on("connect", () => {
    isConnected.value = true;
    console.log("[widget] socket connected", socket.value.id);

    socket.value.emit("join_session", {
      session_id: sessionId.value,
      role: "visitor",
    });
  });

  socket.value.on("disconnect", () => {
    isConnected.value = false;
    console.log("[widget] socket disconnected");
  });

  socket.value.on("new_message", (msg) => {
    if (msg.session_id === sessionId.value) {
      messages.value.push(msg);
      scrollToBottom();
    }
  });
};

// ---- メッセージ送信 ----
const sendMessage = () => {
  const text = inputText.value.trim();
  if (!text || !socket.value || !isConnected.value) return;

  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    content: text,
  });

  inputText.value = "";
};

// ---- メッセージエリアを一番下までスクロール ----
const scrollToBottom = () => {
  requestAnimationFrame(() => {
    const container = document.querySelector(".widget__messages");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  });
};

const toggleOpen = () => {
  isOpen.value = !isOpen.value;
};

onMounted(async () => {
  await fetchOrCreateSession();
  await loadHistory();
  connectSocket();
  scrollToBottom();
});

onBeforeUnmount(() => {
  if (socket.value) socket.value.disconnect();
});
</script>

<template>
  <div class="widget-page">
    <!-- ランチャーボタン（常に右下に表示） -->
    <button class="widget-launcher" @click="toggleOpen">
      <span v-if="!isOpen">💬 チャット</span>
      <span v-else>✕ 閉じる</span>
    </button>

    <!-- 開いているときだけチャット本体を表示 -->
    <div v-if="isOpen" class="widget-container">
      <div class="widget">
        <header class="widget__header">
          <div class="widget__header-main">
            <h1 class="widget__title">サポートチャット</h1>
            <p class="widget__subtitle">ご質問があればこちらからどうぞ</p>
          </div>
          <div
            class="widget__status"
            :class="{ 'widget__status--online': isConnected }"
          >
            <span class="widget__status-dot" />
            <span class="widget__status-text">
              {{ isConnected ? "オペレーターに接続中" : "接続中…" }}
            </span>
          </div>
        </header>

        <main class="widget__messages">
          <div
            v-for="m in messages"
            :key="m.id"
            class="msg"
            :class="m.sender_type === 'visitor' ? 'msg--me' : 'msg--other'"
          >
            <div class="msg__bubble">
              <p>{{ m.content }}</p>
            </div>
          </div>

          <div v-if="messages.length === 0" class="widget__empty">
            はじめてのメッセージを送ってみてください 👋
          </div>
        </main>

        <footer class="widget__footer">
          <input
            v-model="inputText"
            type="text"
            class="widget__input"
            placeholder="メッセージを入力..."
            @keyup.enter="sendMessage"
          />
          <button
            class="widget__button"
            @click="sendMessage"
            :disabled="!isConnected || !inputText.trim()"
          >
            送信
          </button>
        </footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ページ全体（埋め込み用でも、この中が iframe に入るイメージ） */
.widget-page {
  position: relative;
  width: 100%;
  height: 100vh; /* デモ用。実際の埋め込みは iframe の高さ次第 */
  background: #020617;
}

/* 右下のランチャーボタン */
.widget-launcher {
  position: fixed;
  right: 24px;
  bottom: 20px;
  z-index: 40;
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  background: #22c55e;
  color: #022c22;
  cursor: pointer;
  box-shadow: 0 12px 25px rgba(0, 0, 0, 0.35);
}

/* ウィジェット本体（ランチャーの上に出る） */
.widget-container {
  position: fixed;
  right: 24px;
  bottom: 64px;
  z-index: 30;
}

.widget {
  width: 360px;
  height: 540px;
  background: #020617;
  border-radius: 16px;
  box-shadow: 0 18px 35px rgba(0, 0, 0, 0.45);
  border: 1px solid #1f2937;
  display: flex;
  flex-direction: column;
  color: #e5e7eb;
}

.widget__header {
  padding: 12px 14px 10px;
  border-bottom: 1px solid #1f2937;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.widget__header-main {
  display: flex;
  flex-direction: column;
}

.widget__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.widget__subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.widget__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid #374151;
  background: #020617;
  font-size: 11px;
  color: #9ca3af;
}

.widget__status--online {
  border-color: #22c55e;
  color: #bbf7d0;
}

.widget__status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #9ca3af;
}

.widget__status--online .widget__status-dot {
  background: #22c55e;
}

.widget__messages {
  flex: 1;
  padding: 10px 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.widget__empty {
  margin: auto;
  font-size: 13px;
  color: #9ca3af;
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

.widget__footer {
  padding: 8px 10px 11px;
  border-top: 1px solid #1f2937;
  display: flex;
  gap: 8px;
}

.widget__input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid #374151;
  background: #020617;
  color: #e5e7eb;
  font-size: 13px;
}

.widget__input:focus {
  outline: none;
  border-color: #22c55e;
}

.widget__button {
  padding: 6px 16px;
  border-radius: 999px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  background: #22c55e;
  color: #022c22;
  cursor: pointer;
}

.widget__button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
