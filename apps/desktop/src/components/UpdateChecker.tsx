import { useState, useEffect, useCallback } from "react";
import {
  checkForUpdates,
  downloadAndInstallUpdate,
  subscribeStatus,
  getCurrentStatus,
  type DownloadStatus,
} from "../services/updater";
import type { Update } from "@tauri-apps/plugin-updater";

interface UpdateModalProps {
  onClose: () => void;
}

export function UpdateModal({ onClose }: UpdateModalProps) {
  const [status, setStatus] = useState<DownloadStatus>(getCurrentStatus);
  const [updateInfo, setUpdateInfo] = useState<Update | null>(null);
  const [progress, setProgress] = useState(0);

  const handleCheck = useCallback(async () => {
    setProgress(0);
    const result = await checkForUpdates();
    if (result.type === "available") {
      setUpdateInfo(result.update);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = subscribeStatus((newStatus) => {
      setStatus(newStatus);
      if (newStatus.type === "available") {
        setUpdateInfo(newStatus.update);
      }
      if (newStatus.type === "downloading") {
        // 计算百分比
        if (newStatus.total && newStatus.total > 0) {
          setProgress(Math.round((newStatus.progress / newStatus.total) * 100));
        } else {
          setProgress((prev) => Math.min(prev + 5, 95));
        }
      }
    });

    // 自动开始检查
    handleCheck();

    return unsubscribe;
  }, [handleCheck]);

  const handleInstall = async () => {
    if (!updateInfo) return;
    await downloadAndInstallUpdate(updateInfo);
  };

  // 根据状态确定头部颜色
  const getHeaderStyle = () => {
    switch (status.type) {
      case "error":
        return "bg-gradient-to-r from-red-500 to-red-600";
      case "uptodate":
        return "bg-gradient-to-r from-green-500 to-green-600";
      case "available":
      case "downloading":
      case "downloaded":
      case "installing":
        return "bg-gradient-to-r from-blue-500 to-blue-600";
      default:
        return "bg-gradient-to-r from-slate-500 to-slate-600";
    }
  };

  // 根据状态确定标题
  const getTitle = () => {
    switch (status.type) {
      case "checking":
        return "正在检查更新...";
      case "error":
        return "检查更新失败";
      case "uptodate":
        return "已是最新版本";
      case "available":
        return "发现新版本";
      case "downloading":
        return "正在下载更新...";
      case "downloaded":
        return "下载完成";
      case "installing":
        return "正在安装...";
      default:
        return "检查更新";
    }
  };

  // 根据状态确定图标
  const getIcon = () => {
    switch (status.type) {
      case "error":
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        );
      case "uptodate":
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        );
      case "downloading":
        return (
          <svg className="w-5 h-5 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-xl shadow-2xl overflow-hidden">
        {/* 头部 */}
        <div className={`px-6 py-4 ${getHeaderStyle()}`}>
          <div className="flex items-center gap-2">
            {getIcon()}
            <h3 className="text-lg font-semibold text-white">{getTitle()}</h3>
          </div>
        </div>

        {/* 内容 */}
        <div className="px-6 py-5">
          {status.type === "checking" && (
            <div className="flex flex-col items-center py-6">
              <svg
                className="w-10 h-10 text-blue-500 animate-spin mb-3"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              <p className="text-slate-600">正在连接更新服务器...</p>
            </div>
          )}

          {status.type === "error" && (
            <div className="text-center py-4">
              <svg
                className="w-12 h-12 text-red-500 mx-auto mb-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-red-600 font-medium">
                {(status as Extract<DownloadStatus, { type: "error" }>).message}
              </p>
              <p className="text-sm text-slate-500 mt-2">请检查网络连接后重试</p>
            </div>
          )}

          {status.type === "uptodate" && (
            <div className="text-center py-4">
              <svg
                className="w-12 h-12 text-green-500 mx-auto mb-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-lg font-medium text-slate-800">已是最新版本</p>
              <p className="text-sm text-slate-500 mt-1">
                当前版本 v{import.meta.env.VITE_APP_VERSION || "1.2.0"}
              </p>
            </div>
          )}

          {status.type === "available" && updateInfo && (
            <div>
              <div className="flex items-center gap-4 mb-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">当前版本</span>
                  <span className="px-2 py-0.5 bg-slate-100 rounded text-slate-700 font-medium">
                    v{import.meta.env.VITE_APP_VERSION || "1.2.0"}
                  </span>
                </div>
                <svg
                  className="w-4 h-4 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">最新版本</span>
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded font-medium">
                    v{updateInfo.version}
                  </span>
                </div>
              </div>

              {updateInfo.date && (
                <p className="text-xs text-slate-400 mb-3">
                  发布日期：{new Date(updateInfo.date).toLocaleDateString("zh-CN")}
                </p>
              )}

              {updateInfo.body && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-slate-700 mb-2">更新内容：</p>
                  <div className="text-sm text-slate-600 bg-slate-50 rounded-lg p-3 max-h-32 overflow-y-auto">
                    <pre className="whitespace-pre-wrap font-sans">{updateInfo.body}</pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {(status.type === "downloading" ||
            status.type === "downloaded" ||
            status.type === "installing") && (
            <div className="py-4">
              <div className="flex justify-between text-sm text-slate-600 mb-2">
                <span>
                  {status.type === "downloading" && "正在下载..."}
                  {status.type === "downloaded" && "下载完成，准备安装..."}
                  {status.type === "installing" && "正在安装..."}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-slate-500 mt-3 text-center">
                下载完成后将自动安装并重启应用
              </p>
            </div>
          )}
        </div>

        {/* 按钮 */}
        <div className="px-6 py-4 bg-slate-50 flex gap-3 justify-end">
          {status.type === "available" && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
              >
                稍后提醒
              </button>
              <button
                onClick={handleInstall}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
                立即更新
              </button>
            </>
          )}

          {status.type === "error" && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
              >
                关闭
              </button>
              <button
                onClick={handleCheck}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
              >
                重新检查
              </button>
            </>
          )}

          {status.type === "uptodate" && (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
            >
              确定
            </button>
          )}

          {(status.type === "downloading" || status.type === "installing") && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
              title="关闭不会取消下载"
            >
              后台运行
            </button>
          )}

          {(status.type === "checking" || status.type === "idle") && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
            >
              关闭
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function UpdateBadge({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-10 right-4 z-40 flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg shadow-lg transition-all hover:scale-105 animate-pulse"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
        />
      </svg>
      有新版本
    </button>
  );
}
