interface StartupOverlayProps {
  phase: string;
  detail?: string;
  error?: string | null;
}

export default function StartupOverlay({ phase, detail, error }: StartupOverlayProps) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/55 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-2xl bg-white px-8 py-7 shadow-2xl">
        <div className="mb-4 flex items-center gap-3">
          <div
            className="h-9 w-9 animate-spin rounded-full border-[3px] border-blue-200 border-t-blue-600"
            aria-hidden
          />
          <div>
            <h2 className="text-lg font-semibold text-slate-900">正在启动</h2>
            <p className="text-sm text-slate-500">首次启动可能需要 30–60 秒，请稍候</p>
          </div>
        </div>
        {error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-800">{phase}</p>
            {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
          </>
        )}
      </div>
    </div>
  );
}
