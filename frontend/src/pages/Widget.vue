<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";

const messages = ref([]);
const inputText = ref("");
const socket = ref(null);
const sessionId = ref(null);
const isConnected = ref(false);
const isOpen = ref(true); // ウィジェットの開閉

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
  scrollToBottom();
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

// ---- Socket.IO 接続 ----
const connectSocket = () => {
  socket.value = io(API_BASE, {
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

// ---- 開閉 ----
const toggleOpen = () => {
  isOpen.value = !isOpen.value;
};

onMounted(async () => {
  await fetchOrCreateSession();
  await loadHistory();
  connectSocket();
});

onBeforeUnmount(() => {
  if (socket.value) socket.value.disconnect();
});

const formatTime = (isoString) => {
  if (!isoString) return "";

  // サーバから来る "2025-11-26T06:20:00" みたいな文字列を
  // 「UTCとして解釈 → ローカル時刻(JST)表示」に補正
  const fixed = isoString.endsWith("Z") ? isoString : isoString + "Z";
  const d = new Date(fixed);

  return d.toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });
};
</script>

<template>
  <div class="widget-page">
    <!-- ランチャーボタン（常に右下に表示） -->
    <button class="widget-launcher" @click="toggleOpen">
      <span v-if="!isOpen">💬 チャットで相談</span>
      <span v-else>✕ 閉じる</span>
    </button>

    <!-- 開いているときだけチャット本体を表示 -->
    <transition name="widget-panel">
      <div v-if="isOpen" class="widget-container">
        <div class="widget">
          <!-- ヘッダー -->
          <header class="widget__header">
            <div class="widget__header-left">
              <div class="widget__avatar">
                <span>CS</span>
              </div>
              <div>
                <h1 class="widget__title">サポートチャット</h1>
                <p class="widget__subtitle">数分以内に担当者が返信します</p>
              </div>
            </div>
            <div
              class="widget__status"
              :class="{ 'widget__status--online': isConnected }"
            >
              <span class="widget__status-dot" />
              <span class="widget__status-text">
                {{ isConnected ? "オンライン" : "接続中…" }}
              </span>
            </div>
          </header>

          <!-- メッセージ一覧 -->
          <main class="widget__messages">
            <transition-group name="msg" tag="div">
              <div
                v-for="m in messages"
                :key="m.id"
                class="msg"
                :class="m.sender_type === 'visitor' ? 'msg--me' : 'msg--other'"
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

            <div v-if="messages.length === 0" class="widget__empty">
              <p>こんにちは 👋</p>
              <p>
                ご質問やお困りごとがあれば、下の入力欄からメッセージを送ってください。
              </p>
            </div>
          </main>

          <!-- 入力エリア -->
          <footer class="widget__footer">
            <input
              v-model="inputText"
              type="text"
              class="widget__input"
              placeholder="メッセージを入力して Enter で送信"
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
    </transition>
  </div>
</template>

<style>
/* iframe 内のルート要素 */
.widget-page {
  position: relative;
  width: 100%;
  height: 100%;
  background: transparent;
}

/* 右下ランチャー */
.widget-launcher {
  position: absolute;
  right: 16px;
  bottom: 16px;
  z-index: 40;
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  background: #4fc3f7;
  color: white;
  cursor: pointer;
  box-shadow: 0 12px 25px rgba(0, 0, 0, 0.25);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* ウィジェット本体 */
.widget-container {
  position: absolute;
  right: 0;
  bottom: 60px;
  z-index: 30;
}

.widget {
  width: 360px;
  height: 480px;
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  color: #1e293b;
  overflow: hidden;
}

/* ヘッダー */
.widget__header {
  padding: 12px 14px 10px;
  border-bottom: 1px solid #bae6fd;
  background: #e0f7fa;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.widget__header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.widget__avatar {
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

.widget__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0284c7;
}

.widget__subtitle {
  margin: 2px 0 0;
  font-size: 11px;
  color: #64748b;
}

.widget__status {
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

.widget__status--online {
  border-color: #4fc3f7;
  color: #0284c7;
}

.widget__status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
}

.widget__status--online .widget__status-dot {
  background: #4fc3f7;
}

/* メッセージ一覧 */
.widget__messages {
  flex: 1;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

/* メッセージコンテナ（左右寄せ用） */
.msg {
  display: flex;
}

/* 自分（訪問者）=右寄せ */
.msg--me {
  justify-content: flex-end;
}

/* 相手=左寄せ */
.msg--other {
  justify-content: flex-start;
}

/* バブル + 時刻を縦に並べるコンテナ */
.msg__inner {
  display: flex;
  flex-direction: column;
  max-width: 75%;
  margin: 2px 0;
}

/* 自分側はコンテナごと右に寄せる & 右端に揃える */
.msg--me .msg__inner {
  margin-left: auto;
  align-items: flex-end;
}

/* 相手側は左に寄せる */
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

/* 自分（訪問者） */
.msg--me .msg__bubble {
  background: #e0f7fa;
  border: 1px solid #bae6fd;
  color: #0369a1;
}

/* オペレーター */
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

/* 時刻：バブルの外・下側に表示 */
.msg__time {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1;
  color: #94a3b8;
}

/* 時刻の左右寄せ */
.msg--me .msg__time {
  text-align: right;
}

.msg--other .msg__time {
  text-align: left;
}

/* 空状態 */
.widget__empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

/* 入力エリア */
.widget__footer {
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  background: #ffffff;
}

.widget__input {
  flex: 1;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: white;
  color: #1e293b;
}

.widget__input:focus {
  outline: none;
  border-color: #4fc3f7;
}

.widget__button {
  padding: 7px 14px;
  border-radius: 999px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  background: #4fc3f7;
  color: white;
}

/* ウィジェット開閉アニメーション */
.widget-panel-enter-active,
.widget-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.widget-panel-enter-from,
.widget-panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}

/* メッセージが追加されたときのふわっとアニメーション */
.msg-enter-active {
  transition: all 0.16s ease-out;
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}
</style>
