import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

/**
 * 统一版本号：tauri.conf.json 是单一来源。
 * - Tauri/Rust 通过 env!("CARGO_PKG_VERSION") 读
 * - 前端通过 __APP_VERSION__ 全局常量读
 * 编译时从 tauri.conf.json 注入。
 */
function readAppVersion(): string {
  const confPath = resolve(__dirname, 'src-tauri/tauri.conf.json');
  if (!existsSync(confPath)) return '0.0.0';
  try {
    const conf = JSON.parse(readFileSync(confPath, 'utf-8'));
    return conf.version || '0.0.0';
  } catch {
    return '0.0.0';
  }
}

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  define: {
    __APP_VERSION__: JSON.stringify(readAppVersion()),
  },
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: ['es2021', 'chrome100', 'safari13'],
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
})
