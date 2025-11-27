<template>
  <div class="admin-register">
    <h1>Admin 新規登録</h1>

    <form @submit.prevent="handleRegister">
      <div class="form-field">
        <label>会社名</label>
        <input v-model="companyName" type="text" />
      </div>

      <div class="form-field">
        <label>表示名</label>
        <input v-model="displayName" type="text" />
      </div>

      <div class="form-field">
        <label>Email</label>
        <input v-model="email" type="email" />
      </div>

      <div class="form-field">
        <label>Password</label>
        <input v-model="password" type="password" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit">登録してログイン</button>
    </form>

    <p class="link">
      すでにアカウントがありますか？
      <router-link to="/admin/login">ログインはこちら</router-link>
    </p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const companyName = ref("");
const displayName = ref("");
const email = ref("");
const password = ref("");
const error = ref("");

const handleRegister = async () => {
  error.value = "";

  const res = await fetch("http://localhost:8000/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      company_name: companyName.value,
      display_name: displayName.value,
      email: email.value,
      password: password.value,
    }),
  });

  if (!res.ok) {
    try {
      const body = await res.json();
      error.value = body.detail || "登録に失敗しました";
    } catch {
      error.value = "登録に失敗しました";
    }
    return;
  }

  const data = await res.json();

  // 返却: { access_token, token_type, user }
  localStorage.setItem("admin_token", data.access_token);

  // 登録後そのまま管理画面へ
  router.push("/admin");
};
</script>

<style>
.admin-register {
  padding: 2rem;
  max-width: 400px;
  margin: auto;
  font-family: sans-serif;
}

.form-field {
  margin-bottom: 1rem;
}

.form-field label {
  display: block;
  margin-bottom: 0.25rem;
}

.form-field input {
  width: 100%;
  padding: 0.4rem;
  box-sizing: border-box;
}

.error {
  color: red;
  margin-bottom: 1rem;
}

.link {
  margin-top: 1rem;
}
</style>
