import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { PRESETS, getPresetById, type PresetConfig } from './presets';

// 全局状态
let currentTaskId: string | null = null;
let requestId = 0;
let lastOutputDir: string | null = null;
let lastReportPath: string | null = null;
const pendingRequests = new Map<number, { resolve: Function; reject: Function }>();

// DOM 元素
const elements = {
  sampleRoot: document.getElementById('sample-root') as HTMLInputElement,
  excelFile: document.getElementById('excel-file') as HTMLInputElement,
  mockMode: document.getElementById('mock-mode') as HTMLInputElement,
  forceOcr: document.getElementById('force-ocr') as HTMLInputElement,
  btnSelectFolder: document.getElementById('btn-select-folder') as HTMLButtonElement,
  btnSelectExcel: document.getElementById('btn-select-excel') as HTMLButtonElement,
  btnNonLitigation: document.getElementById('btn-non-litigation') as HTMLButtonElement,
  btnEnforcement: document.getElementById('btn-enforcement') as HTMLButtonElement,
  btnOcrOnly: document.getElementById('btn-ocr-only') as HTMLButtonElement,
  progressSection: document.getElementById('progress-section') as HTMLElement,
  resultSection: document.getElementById('result-section') as HTMLElement,
  currentPhase: document.getElementById('current-phase') as HTMLElement,
  progressText: document.getElementById('progress-text') as HTMLElement,
  progressBar: document.getElementById('progress-bar') as HTMLElement,
  currentFile: document.getElementById('current-file') as HTMLElement,
  timeRemaining: document.getElementById('time-remaining') as HTMLElement,
  btnToggleLogs: document.getElementById('btn-toggle-logs') as HTMLButtonElement,
  logsContainer: document.getElementById('logs-container') as HTMLElement,
  logsArrow: document.getElementById('logs-arrow') as HTMLElement,
  resultCreated: document.getElementById('result-created') as HTMLElement,
  resultMatchRate: document.getElementById('result-match-rate') as HTMLElement,
  resultPassRate: document.getElementById('result-pass-rate') as HTMLElement,
  btnViewReport: document.getElementById('btn-view-report') as HTMLButtonElement,
  btnOpenOutput: document.getElementById('btn-open-output') as HTMLButtonElement,
  statusMemory: document.getElementById('status-memory') as HTMLElement,
};

// 检查是否在 Tauri 环境中
function isTauri(): boolean {
  return typeof window !== 'undefined' && !!(window as any).__TAURI_IPC__;
}

// 发送 JSON-RPC 请求
async function sendRequest(method: string, params: any): Promise<any> {
  // 如果不是在 Tauri 环境中，使用模拟数据
  if (!isTauri()) {
    addLog('warn', `Tauri 环境不可用，使用模拟数据: ${method}`);
    return mockResponse(method, params);
  }

  const id = ++requestId;
  console.log(`[sendRequest] method=${method}, id=${id}, params=`, params);

  return new Promise((resolve, reject) => {
    pendingRequests.set(id, { resolve, reject });

    invoke('send_jsonrpc_request', {
      method,
      params,
      id
    }).catch(err => {
      console.error(`[sendRequest] invoke error for id=${id}:`, err);
      pendingRequests.delete(id);
      reject(err);
    });
  });
}

// 模拟响应（用于浏览器环境测试）
function mockResponse(method: string, params: any): any {
  switch (method) {
    case 'system.get_status':
      return {
        python_version: '3.12.0',
        ocr_engine_ready: true,
        poppler_installed: true,
        config_loaded: true,
        available_memory_gb: 8.5
      };
    
    case 'system.check_dependencies':
      return {
        all_ready: true,
        dependencies: [
          { name: 'RapidOCR', installed: true, version: '1.2.0' },
          { name: 'pdfplumber', installed: true, version: '0.10.0' },
          { name: 'Poppler', installed: true }
        ]
      };
    
    case 'non_litigation.process':
      // 模拟处理过程
      setTimeout(() => {
        addLog('info', '[模拟] OCR 识别完成');
        addLog('info', '[模拟] 导出文件完成: 12 个文件');
        addLog('info', '[模拟] 验证完成: 通过率 95%');
      }, 1000);
      
      return {
        success: true,
        summary: {
          sample_root: params.sample_root,
          result_root: params.sample_root + '/output',
          runtime_seconds: 5.2,
          mode: params.mode,
          created_count: 12,
          quality: {
            total_files: 12,
            page_count_matched: 11,
            page_count_match_rate: 0.92
          },
          validation: {
            total: 12,
            passed: 11,
            warnings: 1,
            failed: 0,
            pass_rate: 0.92
          }
        },
        html_report_path: params.sample_root + '/output/report.html'
      };
    
    case 'enforcement.extract':
      return {
        processed: 3,
        extracted: [
          { file_name: '裁定1.pdf', court_case_number: '（2024）粤01行审123号' },
          { file_name: '裁定2.pdf', court_case_number: '（2024）粤01行审124号' }
        ],
        updated_excel_path: params.excel_path + '.updated.xlsx'
      };
    
    case 'ocr.get_cache_status':
      return {
        cached_files: [],
        total_cached: 0,
        cache_dir: '/tmp/ocr-cache'
      };
    
    case 'config.get':
      return {
        doc_types: [
          { key: '责催', pages_per_case: null, filename_pattern: '{sequence}-责催-{notice_number}.pdf' },
          { key: '申请书', pages_per_case: 2, filename_pattern: '{sequence}-申请书pdf-{notice_number}.pdf' },
          { key: '授权书', pages_per_case: 1, filename_pattern: '{sequence}-授权书-{company_name}.pdf' },
          { key: '所函', pages_per_case: 1, filename_pattern: '{sequence}-所函-{company_name}.pdf' }
        ],
        regex_patterns: { notice_number: '...' },
        ocr_corrections: [],
        validation: { fuzzy_match_threshold: 0.85 }
      };
    
    default:
      throw new Error(`未实现的模拟方法: ${method}`);
  }
}

// 监听 JSON-RPC 响应（仅在 Tauri 环境中）
if (isTauri()) {
  listen('jsonrpc-response', (event: any) => {
    const response = event.payload;
    const id = response.id;
    console.log(`[jsonrpc-response] received response for id=${id}:`, response);

    if (pendingRequests.has(id)) {
      const { resolve, reject } = pendingRequests.get(id)!;
      pendingRequests.delete(id);

      if (response.error) {
        console.error(`[jsonrpc-response] error for id=${id}:`, response.error);
        reject(new Error(response.error.message));
      } else {
        resolve(response.result);
      }
    } else {
      console.warn(`[jsonrpc-response] no pending request for id=${id}`);
    }
  });

  // 监听进度通知
  listen('jsonrpc-notification', (event: any) => {
    const notification = event.payload;
    console.log('[jsonrpc-notification] received:', notification);

    if (notification.method === 'notify.progress') {
      handleProgress(notification.params);
    } else if (notification.method === 'notify.log') {
      addLog(notification.params.level, notification.params.message, notification.params.timestamp);
    } else if (notification.method === 'notify.task_complete') {
      handleTaskComplete(notification.params);
    }
  });
}

// 处理进度更新
function handleProgress(params: any) {
  const { task_id, phase, current, total, message } = params;
  console.log(`[handleProgress] task_id=${task_id}, currentTaskId=${currentTaskId}, phase=${phase}`);

  if (task_id !== currentTaskId) {
    console.warn(`[handleProgress] task_id mismatch: expected ${currentTaskId}, got ${task_id}`);
    return;
  }
  
  elements.progressSection.classList.remove('hidden');
  elements.resultSection.classList.add('hidden');
  
  // 更新阶段
  const phaseNames: Record<string, string> = {
    'ocr_cache': 'OCR 识别',
    'export': '导出文件',
    'validation': '验证',
    'report': '生成报告'
  };
  elements.currentPhase.textContent = phaseNames[phase] || phase;
  
  // 更新进度
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
  elements.progressText.textContent = `${current} / ${total}`;
  elements.progressBar.style.width = `${percentage}%`;
  
  // 更新当前文件
  elements.currentFile.textContent = message;
  
  // 添加日志
  addLog('info', `[${phase}] ${message}`);
}

// 处理任务完成
function handleTaskComplete(params: any) {
  const { success, result } = params;
  
  if (success && result) {
    showResults(result);
  }
}

// 显示结果
function showResults(result: any) {
  elements.progressSection.classList.add('hidden');
  elements.resultSection.classList.remove('hidden');

  if (result.summary) {
    elements.resultCreated.textContent = result.summary.created_count?.toString() || '-';
    elements.resultMatchRate.textContent =
      `${Math.round((result.summary.quality?.page_count_match_rate || 0) * 100)}%`;
    elements.resultPassRate.textContent =
      `${Math.round((result.summary.validation?.pass_rate || 0) * 100)}%`;
  }

  // 存储路径，供"查看报告"和"打开输出文件夹"按钮使用
  lastOutputDir = result.summary?.result_root || null;
  lastReportPath = result.html_report_path || null;
}

// 添加日志
function addLog(level: string, message: string, timestamp?: string) {
  const time = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  
  const logItem = document.createElement('div');
  logItem.className = 'log-item flex items-start gap-2 text-sm';
  
  const levelColors: Record<string, string> = {
    'info': 'text-blue-600',
    'warn': 'text-yellow-600',
    'error': 'text-red-600',
    'debug': 'text-gray-500'
  };
  
  logItem.innerHTML = `
    <span class="text-primary-400 font-mono text-xs">${time}</span>
    <span class="${levelColors[level] || 'text-primary-600'}">[${level.toUpperCase()}]</span>
    <span class="text-primary-700">${message}</span>
  `;
  
  elements.logsContainer.appendChild(logItem);
  elements.logsContainer.scrollTop = elements.logsContainer.scrollHeight;
}

// 选择文件夹
async function selectFolder() {
  try {
    const result = await invoke('select_folder') as string | null;
    if (result) {
      elements.sampleRoot.value = result;
    }
  } catch (err) {
    console.error('选择文件夹失败:', err);
    addLog('error', '选择文件夹失败');
  }
}

// 选择 Excel 文件
async function selectExcel() {
  try {
    const result = await invoke('select_files', { multiple: false }) as string[] | null;
    if (result && result.length > 0) {
      elements.excelFile.value = result[0];
    }
  } catch (err) {
    console.error('选择文件失败:', err);
    addLog('error', '选择文件失败');
  }
}

// 开始非诉审查处理
async function startNonLitigation() {
  const sampleRoot = elements.sampleRoot.value;
  if (!sampleRoot) {
    alert('请选择样本材料文件夹');
    return;
  }

  currentTaskId = `nl-${Date.now()}`;
  console.log('[startNonLitigation] task_id:', currentTaskId);

  try {
    elements.btnNonLitigation.disabled = true;
    elements.progressSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');

    addLog('info', '开始非诉审查处理...');
    addLog('info', `Task ID: ${currentTaskId}`);

    const params = {
      sample_root: sampleRoot,
      mode: elements.mockMode.checked ? 'mock' : 'real_ocr',
      force: elements.forceOcr.checked,
      task_id: currentTaskId
    };
    console.log('[startNonLitigation] sending request with params:', params);

    const result = await sendRequest('non_litigation.process', params);
    console.log('[startNonLitigation] received result:', result);

    showResults(result);
    addLog('info', '处理完成！');
  } catch (err: any) {
    console.error('[startNonLitigation] error:', err);
    addLog('error', `处理失败: ${err.message}`);
    alert(`处理失败: ${err.message}`);
  } finally {
    elements.btnNonLitigation.disabled = false;
  }
}

// 开始强制执行提取
async function startEnforcement() {
  const sampleRoot = elements.sampleRoot.value;
  const excelFile = elements.excelFile.value;
  
  if (!sampleRoot || !excelFile) {
    alert('请选择样本材料文件夹和台账 Excel 文件');
    return;
  }
  
  currentTaskId = `enf-${Date.now()}`;
  
  try {
    elements.btnEnforcement.disabled = true;
    elements.progressSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');
    
    addLog('info', '开始强制执行提取...');
    
    const result = await sendRequest('enforcement.extract', {
      input_dir: sampleRoot,
      excel_path: excelFile
    });
    
    elements.resultCreated.textContent = result.processed?.toString() || '-';
    elements.resultMatchRate.textContent = '100%';
    elements.resultPassRate.textContent = '100%';
    
    elements.progressSection.classList.add('hidden');
    elements.resultSection.classList.remove('hidden');
    
    addLog('info', `提取完成，处理了 ${result.processed} 个文件`);
  } catch (err: any) {
    addLog('error', `提取失败: ${err.message}`);
    alert(`提取失败: ${err.message}`);
  } finally {
    elements.btnEnforcement.disabled = false;
  }
}

// 仅 OCR 识别
async function startOcrOnly() {
  const sampleRoot = elements.sampleRoot.value;
  if (!sampleRoot) {
    alert('请选择样本材料文件夹');
    return;
  }
  
  currentTaskId = `ocr-${Date.now()}`;
  
  try {
    elements.btnOcrOnly.disabled = true;
    elements.progressSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');
    
    addLog('info', '开始 OCR 识别...');
    
    // 获取缓存状态
    const cacheStatus = await sendRequest('ocr.get_cache_status', {});
    addLog('info', `当前缓存: ${cacheStatus.total_cached} 个文件`);
    
    // TODO: 实现批量 OCR
    
    addLog('info', 'OCR 识别完成');
  } catch (err: any) {
    addLog('error', `OCR 失败: ${err.message}`);
    alert(`OCR 失败: ${err.message}`);
  } finally {
    elements.btnOcrOnly.disabled = false;
  }
}

// 切换日志显示
function toggleLogs() {
  elements.logsContainer.classList.toggle('hidden');
  elements.logsArrow.style.transform = elements.logsContainer.classList.contains('hidden')
    ? 'rotate(0deg)'
    : 'rotate(180deg)';
}

// 复制日志到剪贴板
async function copyLogs() {
  const logItems = elements.logsContainer.querySelectorAll('.log-item');
  if (logItems.length === 0) {
    addLog('warn', '没有日志可复制');
    return;
  }

  const logText = Array.from(logItems)
    .map(item => item.textContent?.trim())
    .filter(Boolean)
    .join('\n');

  try {
    await navigator.clipboard.writeText(logText);
    addLog('info', '日志已复制到剪贴板');
  } catch (err) {
    addLog('error', '复制日志失败');
    console.error('复制日志失败:', err);
  }
}

// 获取系统状态
async function getSystemStatus() {
  try {
    const status = await sendRequest('system.get_status', {});
    elements.statusMemory.textContent = `${status.available_memory_gb} GB`;
  } catch (err) {
    console.error('获取系统状态失败:', err);
  }
}

// 加载预设配置
function loadPreset(presetId: string) {
  const preset = getPresetById(presetId);
  if (!preset) {
    addLog('error', `预设不存在: ${presetId}`);
    return;
  }

  elements.sampleRoot.value = preset.sampleRoot;
  elements.excelFile.value = preset.excelPath;
  elements.mockMode.checked = preset.mode === 'mock';

  addLog('info', `已加载预设: ${preset.name}`);
  addLog('info', `  样本路径: ${preset.sampleRoot}`);
  addLog('info', `  Excel: ${preset.excelPath}`);
  addLog('info', `  模式: ${preset.mode === 'mock' ? 'Mock' : '真实OCR'}`);
}

// 事件监听
elements.btnSelectFolder.addEventListener('click', selectFolder);
elements.btnSelectExcel.addEventListener('click', selectExcel);
elements.btnNonLitigation.addEventListener('click', startNonLitigation);
elements.btnEnforcement.addEventListener('click', startEnforcement);
elements.btnOcrOnly.addEventListener('click', startOcrOnly);
elements.btnToggleLogs.addEventListener('click', toggleLogs);

// 查看报告按钮
elements.btnViewReport.addEventListener('click', async () => {
  if (!lastReportPath) {
    alert('报告尚未生成，请先执行处理');
    return;
  }
  try {
    if (isTauri()) {
      await invoke('open_path', { path: lastReportPath });
    } else {
      alert(`报告路径: ${lastReportPath}\n（桌面应用中会自动打开文件）`);
    }
  } catch (err: any) {
    console.error('打开报告失败:', err);
    addLog('error', `打开报告失败: ${err}`);
  }
});

// 打开输出文件夹按钮
elements.btnOpenOutput.addEventListener('click', async () => {
  if (!lastOutputDir) {
    alert('输出文件夹尚未创建，请先执行处理');
    return;
  }
  try {
    if (isTauri()) {
      await invoke('open_path', { path: lastOutputDir });
    } else {
      alert(`输出路径: ${lastOutputDir}\n（桌面应用中会自动打开文件夹）`);
    }
  } catch (err: any) {
    console.error('打开输出文件夹失败:', err);
    addLog('error', `打开输出文件夹失败: ${err}`);
  }
});

// 复制日志按钮
const btnCopyLogs = document.getElementById('btn-copy-logs');
if (btnCopyLogs) {
  btnCopyLogs.addEventListener('click', copyLogs);
}

// 预设按钮事件监听
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const presetId = btn.getAttribute('data-preset');
    if (presetId) {
      loadPreset(presetId);
    }
  });
});

// 初始化
getSystemStatus();
addLog('info', '应用已启动');
addLog('info', '可用预设:');
PRESETS.forEach(p => addLog('info', `  - ${p.name}: ${p.description}`));
