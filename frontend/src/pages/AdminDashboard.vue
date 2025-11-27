<!-- frontend/src/pages/AdminDashboard.vue -->
<template>
  <div class="admin-dashboard">
    <h1>Admin Dashboard</h1>

    <p>ログイン済みです。</p>

    <button @click="logout">ログアウト</button>
  </div>
</template>

<script setup>
const logout = () => {
  localStorage.removeItem("admin_token");
  window.location.href = "/admin";
};
</script>

<style>
.admin-dashboard {
  padding: 2rem;
}
</style>
