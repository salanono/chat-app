// frontend/src/router.js
import { createRouter, createWebHistory } from "vue-router";

import WidgetPage from "./pages/Widget.vue";
import AdminLogin from "./pages/AdminLogin.vue";
import AdminRegister from "./pages/AdminRegister.vue";
import Admin from "./pages/Admin.vue";
import AdminBotSettings from "./pages/AdminBotSettings.vue";

const routes = [
  // ウィジェット
  { path: "/widget", component: WidgetPage },

  // 管理画面（ログインが不要なページ）
  { path: "/admin/login", component: AdminLogin },
  { path: "/admin/register", component: AdminRegister },

  // 管理画面（ログイン必須）
  { path: "/admin", component: Admin },

  { path: "/admin/bot", component: AdminBotSettings },

  // それ以外 → /widget へ
  { path: "/:pathMatch(.*)*", redirect: "/widget" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ===== ログイン制御 =====
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("admin_token");
  const isAdminArea = to.path.startsWith("/admin");

  // トークンなしでも入っていい admin 配下のパス
  const publicAdminPaths = ["/admin/login", "/admin/register"];

  // 1) admin 配下 ＆ 未ログイン ＆ 公開パス以外 → /admin/login へ
  if (isAdminArea && !token && !publicAdminPaths.includes(to.path)) {
    return next("/admin/login");
  }

  // 2) ログイン済みで login / register に来たら /admin にリダイレクト
  if (token && publicAdminPaths.includes(to.path)) {
    return next("/admin");
  }

  // 3) それ以外はそのまま
  next();
});

export default router;
