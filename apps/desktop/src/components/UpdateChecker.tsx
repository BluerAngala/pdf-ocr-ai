import { useState } from "react";
import { openDownloadUrl } from "../services/updater";
import type { CheckResult } from "../services/updater";

interface UpdateModalProps {
  checkResult: CheckResult;
  onClose: () => void;
  onCheck: () => void;
}

export function UpdateModal({ checkResult, onClose, onCheck }: UpdateModalProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    if (!checkResult.info?.downloadUrl) return;

    setIsDownloading(true);
    await openDownloadUrl(checkResult.info.downloadUrl);
    setIsDownloading(false);
    // 不关闭弹窗，让用户看到提示
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-white rounded-xl shadow-2xl overflow-hidden">
        {/* 头部 */}
        <div className="px-6 py-4 bg-gradient-to-r from-blue-500 to-blue-600">
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            <h3 className="text-lg font-semibold text-white">发现新版本</h3>
          </div>
        </div>

        {/* 内容 */}
        <div className="px-6 py-4">
          {checkResult.error ? (
            <div className="text-red-600 text-sm">
              <p>检查更新失败：{checkResult.error}</p>
              <p className="text-slate-500 mt-2">请稍后重试或手动下载更新</p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4 mb-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">当前版本</span>
                  <span className="px-2 py-0.5 bg-slate-100 rounded text-slate-700 font-medium">
                    v{checkResult.currentVersion}
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
                    v{checkResult.latestVersion}
                  </span>
                </div>
              </div>

              {checkResult.info?.releaseDate && (
                <p className="text-xs text-slate-400 mb-3">
                  发布日期：{checkResult.info.releaseDate}
                </p>
              )}

              {checkResult.info?.releaseNotes && checkResult.info.releaseNotes.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-slate-700 mb-2">更新内容：</p>
                  <ul className="text-sm text-slate-600 space-y-1 max-h-32 overflow-y-auto">
                    {checkResult.info.releaseNotes.map((note, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-blue-500 mt-1">•</span>
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        {/* 按钮 */}
        <div className="px-6 py-4 bg-slate-50 flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
          >
            稍后提醒
          </button>
          {checkResult.hasUpdate && checkResult.info?.downloadUrl && (
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isDownloading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
                  打开下载...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  立即下载
                </>
              )}
            </button>
          )}
          {!checkResult.hasUpdate && !checkResult.error && (
            <button
              onClick={onCheck}
              className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-sm font-medium rounded-lg transition-colors"
            >
              重新检查
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
