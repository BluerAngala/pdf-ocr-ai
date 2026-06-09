/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_VERSION?: string;
  // 更多环境变量...
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// 由 vite.config.ts 注入，应用版本号（来源：tauri.conf.json）
declare const __APP_VERSION__: string;
