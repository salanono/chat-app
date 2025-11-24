<template>
  <div class="p-2 border rounded shadow w-64">
    <h3>Chat Widget</h3>
    <input v-model="msg" @keyup.enter="send" placeholder="メッセージ" />
    <div v-for="m in messages" :key="m.id">{{ m.content }}</div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import io from "socket.io-client";

const socket = io("http://localhost:8000/ws");
const msg = ref("");
const messages = ref([]);

socket.on("visitor:message", (data) => messages.value.push(data));

const send = () => {
  socket.emit("visitor:message", { content: msg.value });
  msg.value = "";
};
</script>
