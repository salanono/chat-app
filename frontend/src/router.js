// frontend/src/router.js
import { createRouter, createWebHistory } from "vue-router";

import WidgetPage from "./pages/Widget.vue";
import AdminLogin from "./pages/AdminLogin.vue";
import AdminRegister from "./pages/AdminRegister.vue";
import Admin from "./pages/Admin.vue";
import AdminBotSettings from "./pages/AdminBotSettings.vue";
import AdminInstall from "./pages/AdminInstall.vue";
import AdminApiKeys from "./pages/AdminApiKeys.vue";

const routes = [
  { path: "/widget", component: WidgetPage },
  { path: "/admin/login", component: AdminLogin },
  { path: "/admin/register", component: AdminRegister },
  { path: "/admin", component: Admin },
  { path: "/admin/install", component: AdminInstall },
  { path: "/admin/bot", component: AdminBotSettings },
  { path: "/admin/api-keys", component: AdminApiKeys },
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

  const publicAdminPaths = ["/admin/login", "/admin/register"];

  if (isAdminArea && !token && !publicAdminPaths.includes(to.path)) {
    return next("/admin/login");
  }

  if (token && publicAdminPaths.includes(to.path)) {
    return next("/admin");
  }

  next();
});

export default router;
