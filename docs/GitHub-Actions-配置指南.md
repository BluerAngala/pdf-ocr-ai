# 🚀 GitHub Actions 自动发布配置指南

> 配置完成后，每次推送 `v1.2.1` 这样的标签，GitHub 会自动构建并发布新版本！

---

## 📋 前置准备

### 1. 创建 GitHub 仓库

如果你还没有 GitHub 仓库：

1. 访问 https://github.com/new
2. 创建仓库（建议名：`pdf-ocr-ai`）
3. **不要初始化 README**（避免冲突）

### 2. 推送代码到 GitHub

```bash
# 添加 GitHub 远程仓库（替换为你的用户名）
git remote add github https://github.com/你的用户名/pdf-ocr-ai.git

# 推送代码
git push github main
```

### 3. 准备私钥内容

读取本地私钥文件：

```bash
# 在项目根目录执行
cat apps/desktop/tauri.key
```

复制输出的全部内容（以 `dW50cnVzdGVk` 开头的那一串）。

---

## 🔐 配置 GitHub Secrets

这是**最关键的一步**！私钥必须安全地存储在 GitHub 上。

### 步骤：

1. 打开 GitHub 仓库页面
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 填写：
   - **Name**: `TAURI_PRIVATE_KEY`
   - **Secret**: 粘贴你刚才复制的私钥内容
5. 点击 **Add secret**

> ⚠️ **警告**：私钥一旦设置，任何人都无法再查看其内容。如果丢失，需要重新生成密钥对！

---

## ⚙️ 修改配置文件

### 1. 修改 `tauri.conf.json`

打开 `apps/desktop/src-tauri/tauri.conf.json`，找到第 73 行：

```json
"endpoints": [
  "https://github.com/你的用户名/你的仓库名/releases/latest/download/version.json"
]
```

替换为实际值，例如：
```json
"endpoints": [
  "https://github.com/BluerAngala/pdf-ocr-ai/releases/latest/download/version.json"
]
```

### 2. 提交修改

```bash
git add .
git commit -m "配置 GitHub Actions 自动发布"
git push github main
```

---

## 🚀 发布新版本

现在一切准备就绪！发布新版本只需要两步：

### 1. 修改版本号（4 个文件）

和之前一样，修改：
- `apps/desktop/package.json`
- `apps/desktop/src-tauri/Cargo.toml`
- `apps/desktop/src-tauri/tauri.conf.json`
- `apps/desktop/src/App.tsx`

### 2. 推送标签

```bash
# 提交版本号修改
git add .
git commit -m "Release v1.2.1"

# 推送代码
git push github main

# 创建并推送标签（触发自动构建）
git tag v1.2.1
git push github v1.2.1
```

🎉 **完成！** GitHub Actions 会自动开始构建。

---

## 📊 查看构建状态

1. 打开 GitHub 仓库页面
2. 点击 **Actions** 标签
3. 可以看到正在运行的构建任务

构建完成后：
- 自动创建 Release（如 `v1.2.1`）
- 上传两个文件：
  - `GJJ-OCR-Tool-latest-setup.exe`（安装包）
  - `version.json`（版本信息）

---

## ✅ 验证更新功能

1. 安装旧版本应用（如 v1.2.0）
2. 点击应用内的「检查更新」按钮
3. 应该检测到新版本并提示更新
4. 点击「立即更新」自动下载安装

---

## 🔧 常见问题

### Q1: 构建失败，提示找不到私钥

**原因**：GitHub Secret 没有正确设置

**解决**：
1. 检查 Settings → Secrets → Actions 里是否有 `TAURI_PRIVATE_KEY`
2. 确认私钥内容完整（包含所有字符）
3. 重新推送标签触发构建

### Q2: 更新时提示"签名验证失败"

**原因**：`version.json` 里的 signature 和安装包不匹配

**解决**：
1. 检查构建日志中的签名步骤是否正常
2. 确认没有手动修改过 `tauri.key`
3. 重新推送标签

### Q3: 应用检查更新时网络错误

**原因**：`tauri.conf.json` 里的 GitHub 地址不正确

**解决**：
1. 确认用户名和仓库名拼写正确
2. 确认 Release 已发布（不是 Draft）
3. 测试 URL 能否直接访问：
   ```
   https://github.com/你的用户名/你的仓库名/releases/latest/download/version.json
   ```

### Q4: 如何回退到旧版本？

**方法**：
1. 在 GitHub Releases 页面找到旧版本
2. 手动下载旧版安装包
3. 覆盖安装

---

## 📁 自动发布流程图

```
你推送标签 v1.2.1
    ↓
GitHub Actions 触发
    ↓
安装依赖 (Node.js + Rust)
    ↓
构建前端 (npm run build)
    ↓
构建 Tauri 安装包 (使用私钥签名)
    ↓
生成 signature 文件 (.sig)
    ↓
创建 version.json
    ↓
创建 GitHub Release
    ↓
上传文件：
  ├─ GJJ-OCR-Tool-latest-setup.exe
  └─ version.json
    ↓
用户点击「检查更新」
    ↓
应用读取 version.json
    ↓
发现新版本 → 自动下载安装
```

---

## 📝 总结

配置好后，你的发布流程变成：

| 步骤 | 之前 | 现在 |
|------|------|------|
| 修改版本号 | ✅ 手动 | ✅ 手动 |
| 打包 | ✅ 手动 | 🤖 自动 |
| 签名 | ✅ 手动 | 🤖 自动 |
| 创建 version.json | ✅ 手动 | 🤖 自动 |
| 上传到 CDN | ✅ 手动 | 🤖 自动 |

**你只需要**：改版本号 → `git push` → `git tag` → `git push` → 完成！

---

**配置完成时间**：2025-01-20  
**适用版本**：Tauri v2.x + GitHub Actions
