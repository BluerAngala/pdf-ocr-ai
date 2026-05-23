interface OcrWarmupBannerProps {
  detail?: string;
  error?: string;
}

export default function OcrWarmupBanner({ detail, error }: OcrWarmupBannerProps) {
  if (error) {
    return (
      <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-3 flex items-center gap-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-600 text-sm">
          ⚠️
        </span>
        <div className="text-sm text-amber-900">
          <span className="font-semibold">OCR 引擎未就绪</span>
          <span className="text-amber-700 ml-1">
            {error}。仍可配置路径，开始处理前请稍候或重启应用。
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="shrink-0 border-b border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50 px-4 py-3 flex items-center gap-3">
      <span
        className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600"
        aria-hidden
      />
      <div className="flex-1">
        <div className="text-sm font-semibold text-blue-900">OCR 引擎准备中</div>
        <div className="text-xs text-blue-700 mt-0.5">
          {detail ? detail : "可先选择样本目录，处理按钮将在就绪后启用"}
        </div>
      </div>
      <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded-full animate-pulse">
        初始化
      </span>
    </div>
  );
}
