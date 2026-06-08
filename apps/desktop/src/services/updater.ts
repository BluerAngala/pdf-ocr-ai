// 版本更新检查服务
const UPDATE_CHECK_URL = "https://gjj-ocr-updates.oss-cn-guangzhou.aliyuncs.com/version.json";
// 备用：可以换成你自己的服务器或GitHub Raw

interface VersionInfo {
  version: string;
  downloadUrl: string;
  releaseNotes: string[];
  releaseDate: string;
  forceUpdate?: boolean;
}

interface CheckResult {
  hasUpdate: boolean;
  currentVersion: string;
  latestVersion: string;
  info?: VersionInfo;
  error?: string;
}

/**
 * 比较版本号
 * @returns true if v2 > v1
 */
function compareVersion(v1: string, v2: string): boolean {
  const parts1 = v1.replace(/^v/, "").split(".").map(Number);
  const parts2 = v2.replace(/^v/, "").split(".").map(Number);

  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p2 > p1) return true;
    if (p2 < p1) return false;
  }
  return false;
}

/**
 * 检查更新
 */
export async function checkForUpdates(currentVersion: string): Promise<CheckResult> {
  try {
    // 添加时间戳避免缓存
    const url = `${UPDATE_CHECK_URL}?t=${Date.now()}`;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const info: VersionInfo = await response.json();

    const hasUpdate = compareVersion(currentVersion, info.version);

    return {
      hasUpdate,
      currentVersion,
      latestVersion: info.version,
      info,
    };
  } catch (error) {
    return {
      hasUpdate: false,
      currentVersion,
      latestVersion: currentVersion,
      error: error instanceof Error ? error.message : "检查更新失败",
    };
  }
}

/**
 * 打开下载链接
 */
export async function openDownloadUrl(url: string): Promise<void> {
  try {
    // 使用Tauri的shell.open
    const { open } = await import("@tauri-apps/api/shell");
    await open(url);
  } catch {
    // 备用：直接打开浏览器
    window.open(url, "_blank");
  }
}

export type { VersionInfo, CheckResult };
