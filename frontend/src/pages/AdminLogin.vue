<!-- frontend/src/pages/AdminLogin.vue -->
<template>
  <div class="admin-login">
    <h1>Admin Login</h1>

    <form @submit.prevent="handleLogin">
      <div class="form-field">
        <label>Email</label>
        <input v-model="email" type="text" />
      </div>

      <div class="form-field">
        <label>Password</label>
        <input v-model="password" type="password" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit">ログイン</button>
    </form>

    <p class="link">
      アカウントがありませんか？
      <router-link to="/admin/register">新規登録はこちら</router-link>
    </p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const email = ref("admin@example.com");
const password = ref("admin123");
const error = ref("");

const handleLogin = async () => {
  error.value = "";

  const res = await fetch("http://localhost:8000/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: email.value,
      password: password.value,
    }),
  });

  if (!res.ok) {
    error.value = "ログインに失敗しました";
    return;
  }

  const data = await res.json();

  localStorage.setItem("admin_token", data.access_token);

  // ログイン後に管理画面へ
  router.push("/admin");
};
</script>

<style>
.admin-login {
  padding: 2rem;
  max-width: 360px;
  margin: auto;
  font-family: sans-serif;
}

.form-field {
  margin-bottom: 1rem;
}

.error {
  color: red;
  margin-bottom: 1rem;
}

.link {
  margin-top: 1rem;
}
</style>
