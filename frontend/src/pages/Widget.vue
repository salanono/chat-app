<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { io } from "socket.io-client";

const API_BASE = "http://localhost:8000";

const messages = ref([]);
const inputText = ref("");
const socket = ref(null);
const sessionId = ref(null);
const isConnected = ref(false);
const isOpen = ref(true);

// URL から owner_id / api_key を取得
const url = new URL(window.location.href);
const ownerId = url.searchParams.get("owner_id");
const apiKey = url.searchParams.get("api_key");

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

  const payload = { visitor_identifier };
  if (apiKey) payload.api_key = apiKey;
  else if (ownerId) payload.owner_id = ownerId;

  if (!payload.api_key && !payload.owner_id) {
    console.error(
      "[widget] URL に owner_id も api_key もありません。?api_key=... か ?owner_id=... を付けてください"
    );
    return;
  }

  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    console.error("[widget] セッション作成に失敗:", data);
    return;
  }
  sessionId.value = data.id;
};

// ---- 過去メッセージ取得 ----
const loadHistory = async () => {
  if (!sessionId.value) return;

  const res = await fetch(
    `${API_BASE}/api/widget/sessions/${sessionId.value}/messages`
  );
  const data = await res.json();

  messages.value = (data || []).map((m) => ({
    ...m,
    sender_type: normalizeSenderType(m.sender_type),
  }));

  scrollToBottom();
};

// ---- メッセージエリアを一番下までスクロール ----
const scrollToBottom = () => {
  requestAnimationFrame(() => {
    const container = document.querySelector(".widget__messages");
    if (container) container.scrollTop = container.scrollHeight;
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

    if (sessionId.value) {
      socket.value.emit("join_session", {
        session_id: sessionId.value,
        role: "visitor",
      });
    }
  });

  socket.value.on("disconnect", () => {
    isConnected.value = false;
  });

  socket.value.on("new_message", (msg) => {
    if (msg.session_id === sessionId.value) {
      messages.value.push({
        ...msg,
        sender_type: normalizeSenderType(msg.sender_type),
      });
      scrollToBottom();
    }
  });
};

// ---- メッセージ送信（テキスト） ----
const sendMessage = () => {
  const text = inputText.value.trim();
  if (!text || !socket.value || !isConnected.value || !sessionId.value) return;

  // UI 先出し（体感を良くする）
  pushLocalMessage({
    sender_type: "visitor",
    content: text,
    attachment_url: null,
  });

  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    content: text,
    attachment_url: null,
  });

  inputText.value = "";
};

const pushLocalMessage = ({ sender_type, content, attachment_url }) => {
  messages.value.push({
    id: `tmp_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    session_id: sessionId.value,
    sender_type,
    sender_id: null,
    content,
    attachment_url,
    created_at: new Date().toISOString(),
  });
  scrollToBottom();
};

// --------------------
// 画像アップロード
// --------------------
const fileInput = ref(null);
const previewImageUrl = ref(null);

const openFilePicker = () => {
  fileInput.value?.click();
};

const onFileChange = async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;

  try {
    await uploadImage(file);
  } catch (err) {
    console.error("[widget] uploadImage error:", err);
  } finally {
    e.target.value = "";
  }
};

const uploadImage = async (file) => {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    console.error("[widget] upload failed:", await res.text());
    return;
  }

  const data = await res.json().catch(() => ({}));
  if (!data.url) {
    console.error("[widget] upload: no url in response", data);
    return;
  }

  if (!socket.value || !isConnected.value || !sessionId.value) {
    console.error("[widget] socket/session not ready");
    return;
  }

  // UI先出し（画像も即表示）
  pushLocalMessage({
    sender_type: "visitor",
    content: "",
    attachment_url: data.url,
  });

  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    content: "",
    attachment_url: data.url,
  });
};

const openImagePreview = (url) => (previewImageUrl.value = url);
const closeImagePreview = () => (previewImageUrl.value = null);

// ---- 開閉 ----
const toggleOpen = () => {
  isOpen.value = !isOpen.value;
};

// --------------------
// Bot 設定取得（widget側反映）
// --------------------
const botEnabled = ref(false);
const botWelcome = ref("");
const botOptions = ref([]);

const canUseBot = computed(() => !!apiKey); // bot設定APIは api_key 前提

const fetchBotConfig = async () => {
  if (!apiKey) {
    botEnabled.value = false;
    botWelcome.value = "";
    botOptions.value = [];
    return;
  }

  const res = await fetch(
    `${API_BASE}/api/widget/bot?api_key=${encodeURIComponent(apiKey)}`
  );
  if (!res.ok) {
    console.error("[widget] bot config fetch failed:", await res.text());
    return;
  }

  const data = await res.json().catch(() => ({}));

  botEnabled.value = !!data.enabled;
  botWelcome.value = data.welcome_message || "";
  botOptions.value = data.options || [];
};

const onBotOptionClick = (opt) => {
  if (!socket.value || !isConnected.value || !sessionId.value) return;

  // クリックした選択肢は「自分の発言」として即表示
  pushLocalMessage({
    sender_type: "visitor",
    content: opt.label || "",
    attachment_url: null,
  });

  // backendが bot_option_id を見て処理する想定（未知フィールドでも害はない）
  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    bot_option_id: opt.id,
    content: opt.label || "",
    attachment_url: null,
  });

  // もしリンク型なら（任意）別タブで開く
  if (opt.link_url) {
    window.open(opt.link_url, "_blank", "noopener,noreferrer");
  }
};

// ---- 時刻表示 ----
const formatTime = (isoString) => {
  if (!isoString) return "";

  const fixed = String(isoString).match(/(Z|[+-]\d\d:\d\d)$/)
    ? isoString
    : isoString + "Z";

  const d = new Date(fixed);

  return d.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
};

const normalizeSenderType = (raw) => {
  if (!raw) return "visitor";
  const upper = String(raw).toUpperCase();
  if (upper === "VISITOR") return "visitor";
  if (upper === "OPERATOR") return "operator";
  if (upper === "SYSTEM") return "system";
  return String(raw).toLowerCase();
};

// ---- 初期化 ----
let botTimer = null;

onMounted(async () => {
  await fetchOrCreateSession();
  await loadHistory();

  // bot設定取得（最初に必ず1回）
  await fetchBotConfig();

  // botの即時反映をしたいならポーリング（15秒）
  if (canUseBot.value) {
    botTimer = window.setInterval(fetchBotConfig, 15000);
  }

  connectSocket();
});

onBeforeUnmount(() => {
  if (socket.value) socket.value.disconnect();
  if (botTimer) clearInterval(botTimer);
});
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
                  <!-- ⭐ 画像メッセージ（枠なし・クリックで拡大） -->
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

                  <!-- ⭐ テキストメッセージ -->
                  <div v-else class="msg__bubble">
                    <p class="msg__text">{{ m.content }}</p>
                  </div>

                  <!-- 時刻 -->
                  <div class="msg__time">
                    {{ formatTime(m.created_at) }}
                  </div>
                </div>
              </div>
            </transition-group>

            <div v-if="messages.length === 0" class="widget__empty">
              <p v-if="botEnabled">{{ botWelcome }}</p>
              <p v-else>こんにちは 👋</p>

              <div v-if="botEnabled && botOptions.length" class="bot-options">
                <button
                  v-for="opt in botOptions"
                  :key="opt.id"
                  class="bot-option-btn"
                  @click="onBotOptionClick(opt)"
                >
                  {{ opt.label }}
                </button>
              </div>

              <p v-else>
                ご質問やお困りごとがあれば、下の入力欄からメッセージを送ってください。
              </p>
            </div>
          </main>
          <!-- Bot クイック返信（常に表示） -->
          <div
            v-if="botEnabled && botOptions.length"
            class="bot-options bot-options--inline"
          >
            <button
              v-for="opt in botOptions"
              :key="opt.id"
              class="bot-option-btn"
              @click="onBotOptionClick(opt)"
            >
              {{ opt.label }}
            </button>
          </div>
          <!-- 入力エリア -->
          <footer class="widget__footer">
            <!-- 📷 画像アップロード用の隠し input（これだけでOK） -->
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              style="display: none"
              @change="onFileChange"
            />

            <!-- 📷 画像ボタン -->
            <button class="widget__button" @click="openFilePicker">📷</button>

            <!-- テキスト入力 -->
            <input
              v-model="inputText"
              type="text"
              class="widget__input"
              placeholder="メッセージを入力して Enter で送信"
              @keyup.enter="sendMessage"
            />

            <!-- 送信ボタン -->
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
    <!-- 🔍 画像プレビュー（モーダル） -->
    <div
      v-if="previewImageUrl"
      class="image-preview"
      @click.self="closeImagePreview"
    >
      <div class="image-preview__inner">
        <img :src="previewImageUrl" alt="拡大画像" class="image-preview__img" />
        <button class="image-preview__close" @click="closeImagePreview">
          ✕
        </button>
      </div>
    </div>
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
  max-height: calc(100vh - 80px);
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

/* 画像バブル内 */
.msg__image-wrapper {
  margin-top: 4px;
}

.msg__image {
  max-width: 180px;
  max-height: 180px;
  border-radius: 10px;
  display: block;
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
  align-items: center;
}

/* 隠しファイル入力 */
.widget__file-input {
  display: none;
}

/* 画像ボタン */
.widget__icon-button {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: none;
  background: #e0f2fe;
  font-size: 16px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.widget__icon-button:disabled {
  opacity: 0.6;
  cursor: default;
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

.msg-image {
  max-width: 180px;
  border-radius: 8px;
}

/* 画像バブル少し調整（角丸を少しだけ小さくしても良い） */
.msg__bubble--image {
  padding: 4px;
}

/* 画面全体のオーバーレイ */
.image-preview {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999; /* iframe内で最前面に */
}

/* 中央のボックス */
.image-preview__inner {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

/* 拡大画像 */
.image-preview__img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 14px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
}

/* 閉じるボタン */
.image-preview__close {
  position: absolute;
  top: -10px;
  right: -10px;
  border: none;
  border-radius: 999px;
  width: 28px;
  height: 28px;
  cursor: pointer;
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  font-size: 16px;
  line-height: 1;
}

/* 画像メッセージ用（枠なし・影なし） */
.msg__image-wrapper {
  max-width: 70%;
  cursor: pointer;
}

.msg-image {
  width: 100%;
  height: auto;
  border-radius: 12px;
  display: block;
  border: none !important;
  background: none !important;
  box-shadow: none !important;
}

/* 画像は右/左寄せになるようにコンテナも追従 */
.msg--me .msg__image-wrapper {
  margin-left: auto;
}

.msg--other .msg__image-wrapper {
  margin-right: auto;
}

.bot-options {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
}

.bot-option-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  cursor: pointer;
}

.bot-option-btn:hover {
  background: #f1f5f9;
}

.bot-options--inline {
  padding: 8px 12px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  gap: 8px;
  overflow-x: auto;
}

.bot-options--inline .bot-option-btn {
  white-space: nowrap;
  flex: 0 0 auto;
}
</style>
