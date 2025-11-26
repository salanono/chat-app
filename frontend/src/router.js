// frontend/src/router.js
import { createRouter, createWebHistory } from "vue-router";
import Widget from "./pages/Widget.vue";
import Admin from "./pages/Admin.vue";

const routes = [
  {
    path: "/",
    redirect: "/widget", // ルートに来たら /widget に飛ばす
  },
  {
    path: "/widget",
    component: Widget,
  },
  {
    path: "/admin",
    component: Admin,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
