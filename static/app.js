document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const themeToggle = document.getElementById('theme-toggle');
    const detectRuntimeBtn = document.getElementById('detect-runtime');
    const loadModelBtn = document.getElementById('load-model');
    const unloadModelBtn = document.getElementById('unload-model');
    const openBrowserBtn = document.getElementById('open-browser-btn');
    const clearLogsBtn = document.getElementById('clear-logs');
    const autoScrollCheckbox = document.getElementById('auto-scroll');
    const logsDiv = document.getElementById('logs');
    const runtimeList = document.getElementById('runtime-list');
    const modelInput = document.getElementById('model-input');
    const scanModelsBtn = document.getElementById('scan-models');
    const browseFolderBtn = document.getElementById('browse-folder');
    const scannedModelsSelect = document.getElementById('scanned-models');
    const deleteModelBtn = document.getElementById('delete-model-btn');
    const commandPreview = document.getElementById('command-preview');
    const collapsibleHeaders = document.querySelectorAll('.collapsible-header');
    const tooltip = document.getElementById('custom-tooltip');
    const backendSelect = document.getElementById('backend-select');

    // V0.6: Editable preview (restored)
    const editPreviewBtn = document.getElementById('edit-preview-btn');
    const discardPreviewBtn = document.getElementById('discard-preview-btn');
    const commandEditor = document.getElementById('command-editor');
    const previewActions = document.getElementById('preview-actions');

    // Log Filters
    const showWarn = document.getElementById('show-warn');
    const showToken = document.getElementById('show-token');
    const showSystem = document.getElementById('show-system');

    let availableBackends = [];

    // --- Theme Management ---
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', savedTheme);
    themeToggle.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
    });

    // --- Custom Tooltips ---
    function setupTooltips() {
        document.querySelectorAll('.help-icon').forEach(icon => {
            const newIcon = icon.cloneNode(true);
            icon.parentNode.replaceChild(newIcon, icon);

            newIcon.addEventListener('mouseenter', (e) => {
                const text = e.target.getAttribute('data-tooltip');
                tooltip.textContent = text;
                tooltip.classList.add('visible');
            });

            newIcon.addEventListener('mousemove', (e) => {
                tooltip.style.left = e.clientX + 10 + 'px';
                tooltip.style.top = e.clientY + 10 + 'px';
            });

            newIcon.addEventListener('mouseleave', () => {
                tooltip.classList.remove('visible');
            });
        });
    }
    setupTooltips();

    // --- Collapsible Sections ---
    collapsibleHeaders.forEach(header => {
        header.addEventListener('click', () => {
            header.parentElement.classList.toggle('active');
            const content = header.nextElementSibling;
            content.classList.toggle('open');
        });
    });

    // --- Runtime Detection ---
    detectRuntimeBtn.addEventListener('click', async () => {
        runtimeList.innerHTML = '<div class="status-item loading">Detecting...</div>';
        availableBackends = ['cpu']; // CPU always available

        try {
            const serverPath = document.getElementById('server-path').value;
            const response = await fetch(`/detect-runtime?serverPath=${encodeURIComponent(serverPath)}`);
            const data = await response.json();

            if (data.error) {
                runtimeList.innerHTML = `<div class="status-item error">${data.error}</div>`;
                return;
            }

            // Handle Available Backends (DLL Check)
            if (data.available_backends) {
                const backends = data.available_backends;

                // Helper to update option status
                const updateOption = (value, available, dllName) => {
                    const option = backendSelect.querySelector(`option[value="${value}"]`);
                    if (option) {
                        if (!available) {
                            option.disabled = true;
                            // Only append text if not already appended
                            if (!option.textContent.includes('(Missing')) {
                                option.textContent += ` (Missing ${dllName})`;
                            }
                            option.title = `${dllName} not found in server directory`;
                        } else {
                            option.disabled = false;
                            // Reset text if previously disabled (remove "Missing...")
                            option.textContent = option.textContent.split(' (Missing')[0];
                            option.title = "";
                        }
                    }
                };

                updateOption('cuda', backends.cuda, 'ggml-cuda.dll');
                updateOption('rocm', backends.rocm, 'ggml-hip.dll');
                updateOption('vulkan', backends.vulkan, 'ggml-vk.dll');
                updateOption('sycl', backends.sycl, 'ggml-sycl.dll');
            }

            // Handle Active Runtimes (from --list-devices)
            runtimeList.innerHTML = '';
            // Handle V0.7.5 response format (data.runtimes) vs older format (data array)
            const runtimes = data.runtimes || data;

            if (runtimes.length === 0) {
                runtimeList.innerHTML = '<div class="status-item warning">No runtimes detected</div>';
                return;
            }

            runtimes.forEach(runtime => {
                const item = document.createElement('div');
                item.className = `status-item ${runtime.status}`;
                item.textContent = runtime.name;
                item.title = runtime.tooltip;
                runtimeList.appendChild(item);
            });

            // Auto-select best available backend if current selection is invalid/auto
            if (backendSelect.value === 'auto' || backendSelect.selectedOptions[0].disabled) {
                if (data.available_backends && data.available_backends.rocm) backendSelect.value = 'rocm';
                else if (data.available_backends && data.available_backends.cuda) backendSelect.value = 'cuda';
                else if (data.available_backends && data.available_backends.vulkan) backendSelect.value = 'vulkan';
                else backendSelect.value = 'auto'; // Fallback
            }

        } catch (error) {
            runtimeList.innerHTML = `<div class="status-item error">Connection Failed: ${error.message}</div>`;
        }
    });

    // --- Backend Selection ---
    backendSelect.addEventListener('change', () => {
        updateCommandPreview();
    });


    // --- Delete Model ---
    deleteModelBtn.addEventListener('click', async () => {
        const modelPath = scannedModelsSelect.value;
        if (!modelPath) return;

        const modelName = modelPath.split('\\').pop().split('/').pop();
        if (confirm(`Are you sure you want to delete "${modelName}"?\nThis cannot be undone.`)) {
            try {
                const response = await fetch('/delete-model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: modelPath })
                });
                const result = await response.json();
                if (result.error) {
                    alert(`Error: ${result.error}`);
                } else {
                    alert(`Model "${modelName}" deleted successfully.`);
                    scanModelsBtn.click(); // Refresh list
                    modelInput.value = '';
                    deleteModelBtn.style.display = 'none';
                }
            } catch (e) {
                alert(`Error: ${e.message}`);
            }
        }
    });

    // --- Browse Folder ---
    browseFolderBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/browse-folder');
            const data = await response.json();
            if (data.path) {
                document.getElementById('scan-path').value = data.path;
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    });

    scanModelsBtn.addEventListener('click', async () => {
        const path = document.getElementById('scan-path').value;
        scanModelsBtn.textContent = "Scanning...";
        try {
            const response = await fetch('/scan-models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });
            const data = await response.json();
            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }
            scannedModelsSelect.innerHTML = '<option value="">Select Scanned Model</option>';
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model; // Full path as value
                // Clean Name: Strip .gguf extension (case insensitive)
                const filename = model.split('\\').pop().split('/').pop();
                option.textContent = filename.replace(/\.gguf$/i, '');
                scannedModelsSelect.appendChild(option);
            });
            scannedModelsSelect.style.display = 'block';
            deleteModelBtn.style.display = 'none'; // Hide delete until selected
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            scanModelsBtn.textContent = "Scan Folder";
        }
    });

    // --- Command Preview & Generation ---
    function getParams() {
        const val = (id, def) => {
            const el = document.getElementById(id);
            return el ? (el.type === 'checkbox' ? el.checked : el.value) : def;
        };

        return {
            model: modelInput.value,
            threads: parseInt(val('threads', 8)),
            gpu_layers: parseInt(val('gpu-layers', 0)),
            port: parseInt(val('port', 8080)),
            host: val('host', '127.0.0.1'),
            ctx_size: parseInt(val('ctx-size', 4096)),
            batch_size: parseInt(val('batch-size', 512)),
            parallel: parseInt(val('parallel', 1)),
            split_mode: val('split-mode', 'layer'),
            no_mmap: val('no-mmap', false),
            mlock: val('mlock', false),
            flash_attn: val('flash-attn', false),
            jinja: val('jinja', false),
            temp: parseFloat(val('temp', 0.8)),
            top_k: parseInt(val('top-k', 40)),
            top_p: parseFloat(val('top-p', 0.9)),
            min_p: parseFloat(val('min-p', 0.05)),
            repeat_penalty: parseFloat(val('repeat-penalty', 1.1)),
            rope_freq_base: parseFloat(val('rope-freq-base', 0)),
            rope_freq_scale: parseFloat(val('rope-freq-scale', 0)),
            cache_path: document.getElementById('scan-path').value || "",
            cache_type_k: val('cache-type-k', 'f16'),
            cache_type_v: val('cache-type-v', 'f16'),
            backend: backendSelect.value
        };
    }

    function updateCommandPreview() {
        const p = getParams();
        let cmd = `$env:LLAMA_CACHE = "${p.cache_path}"; .\\llama-server `;

        // Handle model part
        if (p.model.includes("-hf")) {
            if (p.model.startsWith("llama-server")) {
                cmd += p.model.replace("llama-server ", "");
            } else {
                cmd += p.model;
            }
        } else if (p.model.includes("-m")) {
            if (p.model.startsWith("llama-server")) {
                cmd += p.model.replace("llama-server ", "");
            } else {
                cmd += p.model;
            }
        } else {
            // Assume path
            cmd += `-m "${p.model}"`;
        }

        // Handle Backend Logic for Preview
        let displayGpuLayers = p.gpu_layers;
        if (p.backend === 'cpu') {
            displayGpuLayers = 0;
        }

        cmd += ` -t ${p.threads} -ngl ${displayGpuLayers} --port ${p.port} --host ${p.host}`;
        cmd += ` -c ${p.ctx_size} -b ${p.batch_size} -np ${p.parallel} -sm ${p.split_mode}`;

        if (p.no_mmap) cmd += " --no-mmap";
        if (p.mlock) cmd += " --mlock";
        if (p.flash_attn) cmd += " -fa";
        if (p.jinja) cmd += " --jinja";

        cmd += ` --cache-type-k ${p.cache_type_k} --cache-type-v ${p.cache_type_v}`;
        cmd += ` --temp ${p.temp} --top-k ${p.top_k} --top-p ${p.top_p} --min_p ${p.min_p} --repeat-penalty ${p.repeat_penalty}`;

        if (p.rope_freq_base > 0) cmd += ` --rope-freq-base ${p.rope_freq_base}`;
        if (p.rope_freq_scale > 0) cmd += ` --rope-freq-scale ${p.rope_freq_scale}`;

        commandPreview.textContent = cmd;
    }

    // --- Editable Command Preview (V0.5) ---
    let isEditingPreview = false;
    let originalCommand = '';

    editPreviewBtn.addEventListener('click', () => {
        if (!isEditingPreview) {
            // Enter edit mode
            originalCommand = commandPreview.textContent;
            commandEditor.value = originalCommand;
            commandPreview.style.display = 'none';
            commandEditor.style.display = 'block';
            previewActions.style.display = 'block';
            editPreviewBtn.textContent = 'Apply Changes';
            isEditingPreview = true;
        } else {
            // Apply changes
            commandPreview.textContent = commandEditor.value;
            commandPreview.style.display = 'block';
            commandEditor.style.display = 'none';
            previewActions.style.display = 'none';
            editPreviewBtn.textContent = 'Edit';
            isEditingPreview = false;
        }
    });

    discardPreviewBtn.addEventListener('click', () => {
        commandPreview.textContent = originalCommand;
        commandPreview.style.display = 'block';
        commandEditor.style.display = 'none';
        previewActions.style.display = 'none';
        editPreviewBtn.textContent = 'Edit';
        isEditingPreview = false;
    });

    // Update preview on any input change
    document.querySelectorAll('input, select').forEach(el => {
        el.addEventListener('input', updateCommandPreview);
        el.addEventListener('change', updateCommandPreview);
    });

    // --- History Management ---
    const historyFields = ['server-path', 'threads', 'gpu-layers', 'ctx-size', 'port', 'host'];

    function loadHistory() {
        historyFields.forEach(id => {
            const listId = `${id}-list`;
            const list = document.getElementById(listId);
            const saved = JSON.parse(localStorage.getItem(`history_${id}`) || '[]');

            // Add defaults if empty
            if (id === 'threads' && !saved.includes(8)) saved.push(8);
            if (id === 'gpu-layers' && !saved.includes(50)) saved.push(50);
            if (id === 'ctx-size' && !saved.includes(4096)) saved.push(4096);
            if (id === 'port' && !saved.includes(8080)) saved.push(8080);
            if (id === 'host' && !saved.includes('127.0.0.1')) saved.push('127.0.0.1');

            list.innerHTML = '';
            saved.forEach(val => {
                const option = document.createElement('option');
                option.value = val;
                list.appendChild(option);
            });
        });
    }

    function saveHistory() {
        historyFields.forEach(id => {
            const el = document.getElementById(id);
            const val = el.value;
            if (!val) return;

            let saved = JSON.parse(localStorage.getItem(`history_${id}`) || '[]');
            if (!saved.includes(val)) {
                saved.unshift(val); // Add to top
                if (saved.length > 5) saved.pop(); // Keep last 5
                localStorage.setItem(`history_${id}`, JSON.stringify(saved));
            }
        });
        loadHistory(); // Refresh lists
    }

    loadHistory();

    // --- Browse Server Path ---
    const browseServerBtn = document.getElementById('browse-server-btn');
    if (browseServerBtn) {
        browseServerBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/browse-file', { method: 'POST' });
                const result = await response.json();
                if (result.path) {
                    document.getElementById('server-path').value = result.path;
                }
            } catch (e) {
                alert("Error opening file picker: " + e.message);
            }
        });
    }

    // --- Model Selection Logic ---
    let selectedModelFullPath = "";

    function truncateName(name, maxLength = 50) {
        if (name.length <= maxLength) return name;
        const start = name.substring(0, 20);
        const end = name.substring(name.length - 20);
        return `${start}...${end}`;
    }

    scannedModelsSelect.addEventListener('change', () => {
        if (scannedModelsSelect.value) {
            const fullPath = scannedModelsSelect.value;
            const filename = fullPath.split('\\').pop().split('/').pop();
            let cleanName = filename.replace(/\.gguf$/i, '');

            // Truncate for display if really long
            cleanName = truncateName(cleanName);

            modelInput.value = cleanName; // Show clean/truncated name
            selectedModelFullPath = fullPath; // Store full path

            // Show delete button when model is selected
            deleteModelBtn.style.display = 'inline-block';

            // Trigger preview update
            updateCommandPreview();
        } else {
            modelInput.value = '';
            selectedModelFullPath = '';
            deleteModelBtn.style.display = 'none';
            updateCommandPreview();
        }
    });

    modelInput.addEventListener('input', () => {
        // If user types manually, assume it's a path or command
        selectedModelFullPath = modelInput.value; // Update selectedModelFullPath to reflect manual input
        updateCommandPreview();
    });

    function getParams() {
        // Simple logic: if we have a selectedModelFullPath from dropdown selection, use it
        // Otherwise, use whatever the user typed in modelInput
        let modelPath = selectedModelFullPath || modelInput.value;

        const val = (id, def) => {
            const el = document.getElementById(id);
            return el ? (el.type === 'checkbox' ? el.checked : el.value) : def;
        };

        return {
            model: modelPath,
            serverPath: document.getElementById('server-path').value,
            threads: parseInt(val('threads', 8)),
            gpu_layers: parseInt(val('gpu-layers', 0)),
            port: parseInt(val('port', 8080)),
            host: val('host', '127.0.0.1'),
            ctx_size: parseInt(val('ctx-size', 4096)),
            batch_size: parseInt(val('batch-size', 512)),
            parallel: parseInt(val('parallel', 1)),
            split_mode: val('split-mode', 'layer'),
            no_mmap: val('no-mmap', false),
            mlock: val('mlock', false),
            flash_attn: val('flash-attn', false),
            jinja: val('jinja', false),
            temp: parseFloat(val('temp', 0.8)),
            top_k: parseInt(val('top-k', 40)),
            top_p: parseFloat(val('top-p', 0.9)),
            min_p: parseFloat(val('min-p', 0.05)),
            repeat_penalty: parseFloat(val('repeat-penalty', 1.1)),
            rope_freq_base: parseFloat(val('rope-freq-base', 0)),
            rope_freq_scale: parseFloat(val('rope-freq-scale', 0)),
            cache_path: document.getElementById('scan-path').value || "",
            cache_type_k: val('cache-type-k', 'f16'),
            cache_type_v: val('cache-type-v', 'f16'),
            backend: backendSelect.value
        };
    }

    // --- Server Control ---
    loadModelBtn.addEventListener('click', async () => {
        const data = getParams();
        if (!data.model) {
            alert("Please select or enter a model first.");
            return;
        }

        // Save History on Start
        saveHistory();

        loadModelBtn.disabled = true;
        loadModelBtn.textContent = "Starting...";

        try {
            const response = await fetch('/start-server', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (result.error) {
                alert(`Error: ${result.error}`);
                loadModelBtn.disabled = false;
                loadModelBtn.textContent = "Start Server";
            } else {
                loadModelBtn.textContent = "Running";
                unloadModelBtn.disabled = false;
                openBrowserBtn.disabled = false;
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
            loadModelBtn.disabled = false;
            loadModelBtn.textContent = "Start Server";
        }
    });

    unloadModelBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/stop-server', { method: 'POST' });
            const result = await response.json();
            loadModelBtn.disabled = false;
            loadModelBtn.textContent = "Start Server";
            unloadModelBtn.disabled = true;
            openBrowserBtn.disabled = true;
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    });

    openBrowserBtn.addEventListener('click', () => {
        const host = document.getElementById('host').value || '127.0.0.1';
        const port = document.getElementById('port').value || '8080';
        window.open(`http://${host}:${port}`, '_blank');
    });

    // --- Logs & Scanning ---
    const eventSource = new EventSource('/logs');

    function scanLogForRuntime(line) {
        const lower = line.toLowerCase();
        let detected = null;

        if (lower.includes("loaded cuda backend")) detected = "CUDA (NVIDIA)";
        else if (lower.includes("loaded rocm backend")) detected = "ROCm (AMD)";
        else if (lower.includes("loaded vulkan backend")) detected = "Vulkan";
        else if (lower.includes("loaded metal backend")) detected = "Metal";
        else if (lower.includes("loaded sycl backend")) detected = "SYCL";

        if (detected) {
            // Check if status box already exists
            let statusItem = document.getElementById('active-runtime-status');
            if (!statusItem) {
                statusItem = document.createElement('div');
                statusItem.id = 'active-runtime-status';
                statusItem.className = 'status-item active';
                statusItem.style.borderColor = 'var(--success-color)';
                statusItem.style.color = 'var(--success-color)';
                runtimeList.insertBefore(statusItem, runtimeList.firstChild);
            }
            statusItem.innerHTML = `<strong>Active Backend:</strong> ${detected}`;
        }
    }

    eventSource.onmessage = (event) => {
        const data = event.data;
        if (data) {
            const [color, line] = data.split('|');

            // Determine Class based on content
            let logClass = 'log-system';
            const lowerLine = line.toLowerCase();
            if (lowerLine.includes('error') || lowerLine.includes('failed')) logClass = 'log-error';
            else if (lowerLine.includes('warn') || lowerLine.includes('warning')) logClass = 'log-warn';

            if (lowerLine.includes('eval time') ||
                lowerLine.includes('tokens per second') ||
                lowerLine.includes('total time') ||
                lowerLine.includes('prompt eval time')) {
                logClass = 'log-token';
            }

            // Scan for runtime
            scanLogForRuntime(line);

            const span = document.createElement('span');
            span.className = logClass;
            span.textContent = line + '\n';

            if (logClass === 'log-warn' && !showWarn.checked) span.style.display = 'none';
            if (logClass === 'log-token' && !showToken.checked) span.style.display = 'none';
            if (logClass === 'log-system' && !showSystem.checked) span.style.display = 'none';

            logsDiv.appendChild(span);
            if (autoScrollCheckbox.checked) {
                logsDiv.scrollTop = logsDiv.scrollHeight;
            }
        }
    };

    clearLogsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        logsDiv.innerHTML = '';
    });

    // Filter Event Listeners
    const toggleLogs = (cls, checked) => {
        document.querySelectorAll(`.${cls}`).forEach(el => {
            el.style.display = checked ? 'inline' : 'none';
        });
    };

    showWarn.addEventListener('change', (e) => toggleLogs('log-warn', e.target.checked));
    showToken.addEventListener('change', (e) => toggleLogs('log-token', e.target.checked));
    showSystem.addEventListener('change', (e) => toggleLogs('log-system', e.target.checked));

    // Initial actions
    // V0.7.6: Auto-detect runtime on load
    updateCommandPreview();

    // Small delay to ensure UI is ready
    setTimeout(() => {
        detectRuntimeBtn.click();
    }, 500);
});
