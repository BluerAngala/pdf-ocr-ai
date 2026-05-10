# 公积金 OCR 工具 - 设计系统

## 配色方案

| 角色 | 色值 | 用途 |
|------|------|------|
| **Primary** | `#0D9488` (Teal-600) | 主按钮、进度条、选中状态 |
| **Secondary** | `#14B8A6` (Teal-500) | 次级按钮、图标、hover 状态 |
| **CTA** | `#F97316` (Orange-500) | 开始按钮、重要操作、警告 |
| **Background** | `#F0FDFA` (Teal-50) | 页面背景 |
| **Surface** | `#FFFFFF` | 卡片、面板背景 |
| **Text Primary** | `#134E4A` (Teal-900) | 主要文字 |
| **Text Secondary** | `#5EEAD4` (Teal-300) | 次要文字、占位符 |
| **Border** | `#99F6E4` (Teal-200) | 边框、分割线 |
| **Success** | `#22C55E` | 成功状态 |
| **Warning** | `#EAB308` | 警告状态 |
| **Error** | `#EF4444` | 错误状态 |

## 字体

- **字体族**: Plus Jakarta Sans
- **字重**: 300 (Light), 400 (Regular), 500 (Medium), 600 (SemiBold), 700 (Bold)
- **标题**: 600-700
- **正文**: 400-500

## 动效规范

- **Hover 过渡**: 150-200ms ease-out
- **页面切换**: 300ms ease-in-out
- **进度动画**: 线性，无缓动
- **成功/错误状态**: 200ms bounce

## 组件规范

### 按钮

```
Primary Button:
- bg: #0D9488
- text: white
- px: 24px, py: 12px
- rounded: 8px
- hover: bg #0F766E, scale 1.02
- active: scale 0.98

Secondary Button:
- bg: white
- border: 1px solid #0D9488
- text: #0D9488
- hover: bg #F0FDFA

CTA Button:
- bg: #F97316
- text: white
- hover: bg #EA580C
```

### 卡片

```
Card:
- bg: white
- rounded: 12px
- shadow: 0 1px 3px rgba(0,0,0,0.1)
- p: 24px
- hover: shadow 0 4px 12px rgba(0,0,0,0.15)
```

### 输入框

```
Input:
- bg: white
- border: 1px solid #99F6E4
- rounded: 8px
- px: 16px, py: 12px
- focus: border #0D9488, ring 2px #0D9488/20
```

### 进度条

```
Progress Bar:
- bg track: #CCFBF1
- bg fill: #0D9488
- height: 8px
- rounded: full
- transition: width 300ms linear
```
