<!-- frontend/src/pages/Widget.vue -->
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

// ---- メッセージエリアを一番下までスクロール ----
const scrollToBottom = () => {
  requestAnimationFrame(() => {
    const container = document.querySelector(".widget__messages");
    if (container) container.scrollTop = container.scrollHeight;
  });
};

// ---- sender_type 正規化 ----
const normalizeSenderType = (raw) => {
  if (!raw) return "visitor";
  const upper = String(raw).toUpperCase();
  if (upper === "VISITOR") return "visitor";
  if (upper === "OPERATOR") return "operator";
  if (upper === "SYSTEM") return "system";
  return String(raw).toLowerCase();
};

// ---- ローカル表示用（Botでも使う） ----
const pushLocalMessage = ({
  sender_type,
  content,
  attachment_url = null,
  local_id = null,
  pending = false,
}) => {
  messages.value.push({
    id: local_id || "local_" + Math.random().toString(36).slice(2),
    session_id: sessionId.value || null,
    sender_type,
    sender_id: null,
    content,
    attachment_url,
    created_at: new Date().toISOString(),
    pending,
  });
  scrollToBottom();
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const notifySize = () => {
  const launcherH = 68; // ランチャーの高さ（だいたい）
  const gap = 16; // 余白（お好み）
  const widgetW = 330;
  const widgetH = 465;

  window.parent.postMessage(
    {
      type: "CHAT_WIDGET_RESIZE",
      width: isOpen.value ? widgetW : launcherH,
      height: isOpen.value ? widgetH + launcherH + gap : launcherH,
      open: isOpen.value,
    },
    "*"
  );
};

const toggleOpen = () => {
  isOpen.value = !isOpen.value;
  notifySize();
};

// --------------------
// Bot 設定取得（widget側反映）
// --------------------
const botEnabled = ref(false);
const botWelcome = ref("");
const botOptions = ref([]);

const canUseBot = computed(() => !!apiKey); // bot設定APIは api_key 前提
const mode = ref("bot"); // "bot" | "operator"

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
    botEnabled.value = false;
    botWelcome.value = "";
    botOptions.value = [];
    return;
  }

  const data = await res.json().catch(() => ({}));

  botEnabled.value = !!data.enabled;
  botWelcome.value = data.welcome_message || "";
  // ★ active だけ返すAPIにしてるならここはそのまま
  botOptions.value = Array.isArray(data.options) ? data.options : [];
};

// ---- Bot 選択肢クリック（Adminに送らない） ----
const onBotOptionClick = async (opt) => {
  // ユーザー選択を表示（ローカルのみ）
  pushLocalMessage({ sender_type: "visitor", content: opt.label });

  // handoff だけ Admin へ繋ぐ
  if (opt.action === "handoff") {
    await startOperatorChat();
    return;
  }

  // link
  if (opt.action === "link" && opt.link_url) {
    pushLocalMessage({
      sender_type: "system",
      content: `こちらをご確認ください：${opt.link_url}`,
    });
    return;
  }

  // 通常 reply_text（typing演出）
  if (opt.reply_text) {
    pushLocalMessage({ sender_type: "system", content: "…" });
    await sleep(250);
    messages.value.pop();
    pushLocalMessage({ sender_type: "system", content: opt.reply_text });
  } else {
    pushLocalMessage({ sender_type: "system", content: "承知しました！" });
  }
};

// --------------------
// セッション作成 / 履歴 / Socket（operatorモードだけ）
// --------------------

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
  const data = await res.json().catch(() => []);
  messages.value = (data || []).map((m) => ({
    ...m,
    sender_type: normalizeSenderType(m.sender_type),
  }));
  scrollToBottom();
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
    const sid = String(msg.session_id);
    if (sid !== String(sessionId.value)) return;

    const normalized = {
      ...msg,
      session_id: sid,
      sender_type: normalizeSenderType(msg.sender_type),
    };

    // ★ 自分(visitor)が送ったメッセージのエコーなら pending を探して置換
    if (normalized.sender_type === "visitor") {
      const idx = messages.value.findIndex(
        (m) =>
          m.pending === true &&
          m.sender_type === "visitor" &&
          (m.content || "") === (normalized.content || "") &&
          (m.attachment_url || null) === (normalized.attachment_url || null)
      );
      if (idx !== -1) {
        messages.value[idx] = { ...normalized, pending: false };
        scrollToBottom();
        return;
      }
    }

    // 通常追加
    messages.value.push(normalized);
    scrollToBottom();
  });
};

// ---- handoff: operatorチャット開始（ここで初めてAdminに出る） ----
const startOperatorChat = async () => {
  if (mode.value === "operator") return;

  // 1) セッション作成（ここで初めてDBに触る）
  await fetchOrCreateSession();
  if (!sessionId.value) {
    pushLocalMessage({
      sender_type: "system",
      content: "接続に失敗しました。もう一度お試しください。",
    });
    return;
  }

  // 2) handoff 요청（ここで初めてAdminに出る）
  const res = await fetch(
    `${API_BASE}/api/widget/sessions/${
      sessionId.value
    }/handoff?api_key=${encodeURIComponent(apiKey)}`,
    { method: "POST" }
  );

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    pushLocalMessage({
      sender_type: "system",
      content: "オペレーター接続の開始に失敗しました。",
    });
    return;
  }

  // ★ ここ追加：サーバーが返した最初のメッセージを表示
  if (data?.message?.content) {
    pushLocalMessage({ sender_type: "system", content: data.message.content });
  } else {
    pushLocalMessage({
      sender_type: "system",
      content: "担当者をお呼びします。少々お待ちください。",
    });
  }

  // 3) socket接続 & join
  connectSocket();

  // 4) UI案内（必要なら）
  mode.value = "operator";
  pushLocalMessage({
    sender_type: "system",
    content: "オペレーターに接続しました。少々お待ちください。",
  });

  // 5)（任意）履歴ロード
  await loadHistory();
};

// --------------------
// テキスト送信
// --------------------
const sendMessage = async () => {
  const text = inputText.value.trim();
  if (!text) return;

  if (mode.value === "bot") {
    // ここはそのまま
    pushLocalMessage({ sender_type: "visitor", content: text });
    pushLocalMessage({
      sender_type: "system",
      content:
        "ありがとうございます！オペレーターに相談する場合は「オペレーターに相談」を選んでください。",
    });
    inputText.value = "";
    return;
  }

  if (!socket.value || !isConnected.value || !sessionId.value) return;

  // ★ pending を入れる
  const localId = `pending_${Date.now()}_${Math.random()
    .toString(16)
    .slice(2)}`;
  pushLocalMessage({
    sender_type: "visitor",
    content: text,
    local_id: localId,
    pending: true,
  });

  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    content: text,
    attachment_url: null,
  });

  inputText.value = "";
};
// --------------------
// 画像アップロード（operatorモードのみ）
// --------------------
const fileInput = ref(null);
const previewImageUrl = ref(null);

const openFilePicker = async () => {
  if (mode.value === "bot") {
    pushLocalMessage({
      sender_type: "system",
      content: "画像送信はオペレーター接続後に利用できます。",
    });
    return;
  }
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
  if (mode.value !== "operator") return;
  if (!socket.value || !isConnected.value || !sessionId.value) return;

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

  // UI先出し（画像も即表示）
  const localId = `pending_${Date.now()}_${Math.random()
    .toString(16)
    .slice(2)}`;
  pushLocalMessage({
    sender_type: "visitor",
    content: "",
    attachment_url: data.url,
    local_id: localId,
    pending: true,
  });

  socket.value.emit("visitor_message", {
    session_id: sessionId.value,
    content: "",
    attachment_url: data.url,
  });
};

const openImagePreview = (url) => (previewImageUrl.value = url);
const closeImagePreview = () => (previewImageUrl.value = null);

// ---- 時刻表示 ----
const formatTime = (isoString) => {
  if (!isoString) return "";

  const fixed = String(isoString).match(/(Z|[+-]\d\d:\d\d)$/)
    ? isoString
    : isoString + "Z";

  const d = new Date(fixed);
  return d.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
};

// ---- 初期化 ----

onMounted(async () => {
  console.log("[widget] href:", window.location.href);
  console.log("[widget] apiKey:", apiKey);
  await fetchBotConfig();
  if (botEnabled.value && botWelcome.value && messages.value.length === 0) {
    pushLocalMessage({ sender_type: "system", content: botWelcome.value });
  }
  notifySize(); // ★初期表示で親iframeをサイズ合わせ
});

onBeforeUnmount(() => {
  if (socket.value) socket.value.disconnect();
});
</script>

<template>
  <div class="widget-page">
    <!-- ランチャーボタン -->
    <button
      class="widget-launcher"
      :class="{ closed: !isOpen }"
      @click="toggleOpen"
    >
      <span v-if="!isOpen">💬</span>
      <span v-else>✕ 閉じる</span>
    </button>

    <!-- チャット本体 -->
    <transition name="widget-panel">
      <div v-if="isOpen" class="widget-container">
        <div class="widget">
          <!-- ヘッダー -->
          <header class="widget__header">
            <div class="widget__header-left">
              <div class="widget__avatar"><span>CS</span></div>
              <div>
                <h1 class="widget__title">サポートチャット</h1>
                <p class="widget__subtitle">
                  <span v-if="mode === 'bot' && botEnabled"
                    >Botでご案内します</span
                  >
                  <span v-else>数分以内に担当者が返信します</span>
                </p>
              </div>
            </div>

            <div
              class="widget__status"
              :class="{ 'widget__status--online': isConnected }"
            >
              <span class="widget__status-dot" />
              <span class="widget__status-text">
                {{
                  mode === "bot"
                    ? "Bot"
                    : isConnected
                    ? "オンライン"
                    : "接続中…"
                }}
              </span>
            </div>
          </header>

          <!-- メッセージ -->
          <main class="widget__messages">
            <transition-group name="msg" tag="div">
              <div
                v-for="m in messages"
                :key="m.id"
                class="msg"
                :class="m.sender_type === 'visitor' ? 'msg--me' : 'msg--other'"
              >
                <div class="msg__inner">
                  <!-- 画像 -->
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

                  <!-- テキスト -->
                  <div v-else class="msg__bubble">
                    <p class="msg__text">{{ m.content }}</p>
                  </div>

                  <div class="msg__time">{{ formatTime(m.created_at) }}</div>
                </div>
              </div>
            </transition-group>

            <!-- 何もないときの空状態 -->
            <div v-if="messages.length === 0" class="widget__empty">
              <p v-if="botEnabled && canUseBot">
                {{ botWelcome || "こんにちは 👋" }}
              </p>
              <p v-else>こんにちは 👋</p>

              <p style="margin-top: 8px">
                <span v-if="mode === 'bot' && botEnabled">
                  下のボタンから選んでください。
                </span>
                <span v-else> ご質問は下の入力欄から送信してください。 </span>
              </p>
            </div>
          </main>

          <!-- Botクイック選択肢（Botモードのみ / 1箇所だけ表示） -->
          <div
            v-if="mode === 'bot' && botEnabled && botOptions.length"
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
          <footer v-if="mode === 'operator'" class="widget__footer">
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              style="display: none"
              @change="onFileChange"
            />

            <button class="widget__button" @click="openFilePicker">＋</button>

            <input
              v-model="inputText"
              type="text"
              class="widget__input"
              :placeholder="
                mode === 'bot'
                  ? '（Bot）まずは下の選択肢がおすすめ'
                  : 'メッセージを入力して Enter で送信'
              "
              @keyup.enter="sendMessage"
            />

            <button
              class="widget__button"
              @click="sendMessage"
              :disabled="
                mode === 'operator' && (!isConnected || !inputText.trim())
              "
            >
              送信
            </button>
          </footer>
        </div>
      </div>
    </transition>

    <!-- 画像プレビュー -->
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

<style scoped>
.widget-page {
  position: relative;
  width: 100%;
  height: 100%;
  background: transparent;
}

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

.widget-launcher.closed {
  right: 0;
  bottom: 0;
  width: 64px;
  height: 64px;
  padding: 0;

  display: flex; /* ★これ */
  align-items: center; /* ★縦中央 */
  justify-content: center; /* ★横中央 */

  font-size: 24px; /* アイコン少し大きく */
  line-height: 1; /* 文字のズレ防止 */
}

.widget-container {
  position: absolute;
  right: 0;
  bottom: 72px; /* ランチャー(56) + 余白(16) */
  z-index: 30;
}

.widget {
  width: 327px;
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

.widget__messages {
  flex: 1;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  background: #ffffff;
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

.msg__bubble {
  max-width: 100%;
  padding: 6px 10px;
  border-radius: 14px;
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

/* 画像 */
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

.msg--me .msg__image-wrapper {
  margin-left: auto;
}

.msg--other .msg__image-wrapper {
  margin-right: auto;
}

/* 空状態 */
.widget__empty {
  margin: auto;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

/* 入力 */
.widget__footer {
  padding: 10px 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  background: #ffffff;
  align-items: center;
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
  cursor: pointer;
}

/* Bot選択肢（横スクロール） */
.bot-options--inline {
  padding: 8px 12px;
  border-top: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  gap: 8px;
  overflow-x: auto;
}

.bot-option-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  flex: 0 0 auto;
}

.bot-option-btn:hover {
  background: #f1f5f9;
}

/* 開閉アニメ */
.widget-panel-enter-active,
.widget-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.widget-panel-enter-from,
.widget-panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}

/* メッセージ追加アニメ */
.msg-enter-active {
  transition: all 0.16s ease-out;
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

/* 画像プレビュー */
.image-preview {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.image-preview__inner {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.image-preview__img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 14px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
}

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
</style>

<style>
/* ★ これを追加：iframe内ページ全体を透明にする */
html,
body {
  background: transparent !important;
  margin: 0;
  padding: 0;
}

#app {
  background: transparent !important;
}

html,
body,
#app {
  height: 100%;
}
</style>
