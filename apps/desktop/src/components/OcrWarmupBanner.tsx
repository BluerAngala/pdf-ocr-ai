interface OcrWarmupBannerProps {
  detail?: string;
  error?: string;
}

export default function OcrWarmupBanner({ detail, error }: OcrWarmupBannerProps) {
  if (error) {
    return (
      <div className="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
        <span className="font-medium">OCR 引擎未就绪：</span>
        {error}。仍可配置路径，开始处理前请稍候或重启应用。
      </div>
    );
  }

  return (
    <div className="shrink-0 border-b border-blue-100 bg-blue-50 px-4 py-2 text-xs text-blue-900 flex items-center gap-2">
      <span
        className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600"
        aria-hidden
      />
      <span>
        <span className="font-medium">OCR 引擎准备中</span>
        {detail ? ` — ${detail}` : " — 可先选择样本目录，处理按钮将在就绪后启用"}
      </span>
    </div>
  );
}
