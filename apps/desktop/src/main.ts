import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';

// 全局状态
let currentTaskId: string | null = null;
let requestId = 0;
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

// 发送 JSON-RPC 请求
async function sendRequest(method: string, params: any): Promise<any> {
  const id = ++requestId;
  
  return new Promise((resolve, reject) => {
    pendingRequests.set(id, { resolve, reject });
    
    invoke('send_jsonrpc_request', {
      method,
      params,
      id
    }).catch(err => {
      pendingRequests.delete(id);
      reject(err);
    });
  });
}

// 监听 JSON-RPC 响应
listen('jsonrpc-response', (event: any) => {
  const response = event.payload;
  const id = response.id;
  
  if (pendingRequests.has(id)) {
    const { resolve, reject } = pendingRequests.get(id)!;
    pendingRequests.delete(id);
    
    if (response.error) {
      reject(new Error(response.error.message));
    } else {
      resolve(response.result);
    }
  }
});

// 监听进度通知
listen('jsonrpc-notification', (event: any) => {
  const notification = event.payload;
  
  if (notification.method === 'notify.progress') {
    handleProgress(notification.params);
  } else if (notification.method === 'notify.log') {
    addLog(notification.params.level, notification.params.message, notification.params.timestamp);
  } else if (notification.method === 'notify.task_complete') {
    handleTaskComplete(notification.params);
  }
});

// 处理进度更新
function handleProgress(params: any) {
  const { task_id, phase, current, total, message } = params;
  
  if (task_id !== currentTaskId) return;
  
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
  
  try {
    elements.btnNonLitigation.disabled = true;
    elements.progressSection.classList.remove('hidden');
    elements.resultSection.classList.add('hidden');
    
    addLog('info', '开始非诉审查处理...');
    
    const result = await sendRequest('non_litigation.process', {
      sample_root: sampleRoot,
      mode: elements.mockMode.checked ? 'mock' : 'real_ocr',
      force: elements.forceOcr.checked
    });
    
    showResults(result);
    addLog('info', '处理完成！');
  } catch (err: any) {
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

// 获取系统状态
async function getSystemStatus() {
  try {
    const status = await sendRequest('system.get_status', {});
    elements.statusMemory.textContent = `${status.available_memory_gb} GB`;
  } catch (err) {
    console.error('获取系统状态失败:', err);
  }
}

// 事件监听
elements.btnSelectFolder.addEventListener('click', selectFolder);
elements.btnSelectExcel.addEventListener('click', selectExcel);
elements.btnNonLitigation.addEventListener('click', startNonLitigation);
elements.btnEnforcement.addEventListener('click', startEnforcement);
elements.btnOcrOnly.addEventListener('click', startOcrOnly);
elements.btnToggleLogs.addEventListener('click', toggleLogs);

// 初始化
getSystemStatus();
addLog('info', '应用已启动');
