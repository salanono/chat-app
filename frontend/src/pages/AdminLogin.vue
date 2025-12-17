<!-- frontend/src/pages/AdminLogin.vue -->
<template>
  <div class="auth-page">
    <div class="auth-card">
      <header class="auth-header">
        <div class="auth-avatar">CS</div>
        <div>
          <h1 class="auth-title">管理者ログイン</h1>
          <p class="auth-subtitle">
            チャットの問い合わせをまとめて管理できます
          </p>
        </div>
      </header>

      <form class="auth-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label>Email</label>
          <input v-model="email" type="email" placeholder="you@example.com" />
        </div>

        <div class="form-field">
          <label>Password</label>
          <input v-model="password" type="password" placeholder="••••••••" />
        </div>

        <p v-if="error" class="auth-error">{{ error }}</p>

        <button type="submit" class="auth-button">ログイン</button>
      </form>

      <p class="auth-link">
        アカウントをお持ちでない方は
        <router-link to="/admin/register">新規登録はこちら</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

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
    error.value = "メールアドレスまたはパスワードが正しくありません";
    return;
  }

  const data = await res.json();

  localStorage.setItem("admin_token", data.access_token);

  window.location.href = "/admin/install";
};
</script>

<style>
.auth-page {
  min-height: 100vh;
  margin: 0;
  padding: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
    sans-serif;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at top left, #e0f7fa, #f1f5f9);
}

.auth-card {
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18);
  border: 1px solid #e2e8f0;
  padding: 24px 26px 22px;
  box-sizing: border-box;
}

.auth-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}

.auth-avatar {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  background: #4fc3f7;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

.auth-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.auth-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.auth-form {
  margin-top: 8px;
}

.form-field {
  margin-bottom: 14px;
}

.form-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 4px;
}

.form-field input {
  width: 100%;
  padding: 8px 11px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  font-size: 13px;
  box-sizing: border-box;
}

.form-field input:focus {
  outline: none;
  border-color: #4fc3f7;
  box-shadow: 0 0 0 1px rgba(79, 195, 247, 0.35);
}

.auth-error {
  margin: 4px 0 10px;
  font-size: 12px;
  color: #dc2626;
}

.auth-button {
  width: 100%;
  padding: 9px 0;
  border-radius: 999px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  background: linear-gradient(135deg, #4fc3f7, #0ea5e9);
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(56, 189, 248, 0.4);
}

.auth-button:hover {
  filter: brightness(1.02);
}

.auth-link {
  margin-top: 14px;
  font-size: 12px;
  text-align: center;
  color: #64748b;
}

.auth-link a {
  color: #0284c7;
  font-weight: 600;
  text-decoration: none;
}

.auth-link a:hover {
  text-decoration: underline;
}
</style>
