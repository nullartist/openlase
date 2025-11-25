/**
 * OpenLase Web - Frontend Application
 * 
 * Provides the user interface for controlling the laser output,
 * video/screen capture input, and ILDA recording/editing.
 */

// Constants
const SSE_RECONNECT_DELAY_MS = 2000;  // Milliseconds before SSE reconnection
const STATUS_UPDATE_INTERVAL_MS = 2000;  // Milliseconds between status updates
const CAPTURE_FRAME_INTERVAL_MS = 33;  // ~30 FPS for capture

class OpenLaseApp {
    constructor() {
        this.canvas = document.getElementById('preview-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.patterns = [];
        this.currentPattern = null;
        this.isRunning = false;
        this.frameCount = 0;
        this.lastFpsUpdate = Date.now();
        this.fps = 0;
        
        // Capture state
        this.captureVideo = document.getElementById('capture-video');
        this.captureCanvas = document.getElementById('capture-canvas');
        this.captureCtx = this.captureCanvas ? this.captureCanvas.getContext('2d') : null;
        this.captureStream = null;
        this.captureInterval = null;
        this.inputMode = 'pattern';
        
        // Recording state
        this.isRecording = false;
        this.recordingStartTime = null;
        this.recordingStatusInterval = null;
        
        // Editor state
        this.editorLoaded = false;
        this.currentFrameIndex = 0;
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadPatterns();
        await this.updateStatus();
        this.startPreviewStream();
        
        // Update status periodically
        setInterval(() => this.updateStatus(), STATUS_UPDATE_INTERVAL_MS);
    }

    setupEventListeners() {
        // Start/Stop buttons
        document.getElementById('btn-start').addEventListener('click', () => this.start());
        document.getElementById('btn-stop').addEventListener('click', () => this.stop());
        
        // Tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.mode));
        });
        
        // Pattern controls
        document.getElementById('pattern-select').addEventListener('change', (e) => {
            this.onPatternChange(e.target.value);
        });
        document.getElementById('btn-apply-pattern').addEventListener('click', () => {
            this.applyPattern();
        });
        
        // PPS slider
        const ppsSlider = document.getElementById('pps-slider');
        const ppsValue = document.getElementById('pps-value');
        ppsSlider.addEventListener('input', (e) => {
            ppsValue.textContent = e.target.value;
        });
        ppsSlider.addEventListener('change', (e) => {
            this.setPps(parseInt(e.target.value));
        });
        
        // Capture controls
        const btnWebcam = document.getElementById('btn-webcam');
        const btnScreen = document.getElementById('btn-screen');
        const btnStopCapture = document.getElementById('btn-stop-capture');
        const btnApplyCaptureParams = document.getElementById('btn-apply-capture-params');
        
        if (btnWebcam) btnWebcam.addEventListener('click', () => this.startWebcamCapture());
        if (btnScreen) btnScreen.addEventListener('click', () => this.startScreenCapture());
        if (btnStopCapture) btnStopCapture.addEventListener('click', () => this.stopCapture());
        if (btnApplyCaptureParams) btnApplyCaptureParams.addEventListener('click', () => this.applyCaptureParams());
        
        // Capture parameter sliders
        this.setupCaptureSliders();
        
        // Recording controls
        const btnRecordStart = document.getElementById('btn-record-start');
        const btnRecordStop = document.getElementById('btn-record-stop');
        const btnDownloadRecording = document.getElementById('btn-download-recording');
        
        if (btnRecordStart) btnRecordStart.addEventListener('click', () => this.startRecording());
        if (btnRecordStop) btnRecordStop.addEventListener('click', () => this.stopRecording());
        if (btnDownloadRecording) btnDownloadRecording.addEventListener('click', () => this.downloadRecording());
        
        // Editor controls
        const btnLoadIlda = document.getElementById('btn-load-ilda');
        const ildaFileInput = document.getElementById('ilda-file-input');
        const btnLoadRecording = document.getElementById('btn-load-recording');
        const btnDownloadIlda = document.getElementById('btn-download-ilda');
        const btnUndo = document.getElementById('btn-undo');
        const btnScale = document.getElementById('btn-scale');
        const btnRotate = document.getElementById('btn-rotate');
        const btnSetColor = document.getElementById('btn-set-color');
        
        if (btnLoadIlda) btnLoadIlda.addEventListener('click', () => ildaFileInput.click());
        if (ildaFileInput) ildaFileInput.addEventListener('change', (e) => this.loadIldaFile(e));
        if (btnLoadRecording) btnLoadRecording.addEventListener('click', () => this.loadRecordingToEditor());
        if (btnDownloadIlda) btnDownloadIlda.addEventListener('click', () => this.downloadEditorFile());
        if (btnUndo) btnUndo.addEventListener('click', () => this.editorUndo());
        if (btnScale) btnScale.addEventListener('click', () => this.editorScale());
        if (btnRotate) btnRotate.addEventListener('click', () => this.editorRotate());
        if (btnSetColor) btnSetColor.addEventListener('click', () => this.editorSetColor());
    }

    setupCaptureSliders() {
        const sliders = [
            { id: 'threshold-slider', valueId: 'threshold-value' },
            { id: 'threshold2-slider', valueId: 'threshold2-value' },
            { id: 'blur-slider', valueId: 'blur-value', divisor: 10 },
            { id: 'decimate-slider', valueId: 'decimate-value' }
        ];
        
        sliders.forEach(({ id, valueId, divisor }) => {
            const slider = document.getElementById(id);
            const value = document.getElementById(valueId);
            if (slider && value) {
                slider.addEventListener('input', (e) => {
                    value.textContent = divisor ? (parseFloat(e.target.value) / divisor).toFixed(1) : e.target.value;
                });
            }
        });
    }

    switchTab(mode) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        
        // Hide all tab content
        const patternControls = document.getElementById('pattern-controls');
        const captureControls = document.getElementById('capture-controls');
        const editorControls = document.getElementById('editor-controls');
        
        if (patternControls) patternControls.classList.add('hidden');
        if (captureControls) captureControls.classList.add('hidden');
        if (editorControls) editorControls.classList.add('hidden');
        
        // Show selected tab content
        if (mode === 'pattern' && patternControls) {
            patternControls.classList.remove('hidden');
        } else if (mode === 'capture' && captureControls) {
            captureControls.classList.remove('hidden');
        } else if (mode === 'editor' && editorControls) {
            editorControls.classList.remove('hidden');
        }
        
        // Set input mode on server
        this.setInputMode(mode === 'editor' ? 'pattern' : mode);
    }

    async setInputMode(mode) {
        try {
            await fetch('/api/input/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode })
            });
            this.inputMode = mode;
        } catch (error) {
            console.error('Failed to set input mode:', error);
        }
    }

    async loadPatterns() {
        try {
            const response = await fetch('/api/patterns');
            this.patterns = await response.json();
            
            const select = document.getElementById('pattern-select');
            select.innerHTML = this.patterns.map(p => 
                `<option value="${p.id}">${p.name}</option>`
            ).join('');
            
            if (this.patterns.length > 0) {
                this.onPatternChange(this.patterns[0].id);
            }
        } catch (error) {
            console.error('Failed to load patterns:', error);
        }
    }

    onPatternChange(patternId) {
        const pattern = this.patterns.find(p => p.id === patternId);
        if (!pattern) return;
        
        this.currentPattern = pattern;
        this.renderPatternParams(pattern);
    }

    renderPatternParams(pattern) {
        const container = document.getElementById('pattern-params');
        container.innerHTML = '';
        
        if (!pattern.parameters) return;
        
        for (const [name, config] of Object.entries(pattern.parameters)) {
            const item = document.createElement('div');
            item.className = 'param-item';
            
            const label = document.createElement('label');
            label.textContent = name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' ');
            item.appendChild(label);
            
            let input;
            
            if (config.type === 'bool') {
                input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = config.default;
            } else if (config.type === 'str') {
                input = document.createElement('input');
                input.type = 'text';
                input.value = config.default || '';
            } else if (config.type === 'int' || config.type === 'float') {
                input = document.createElement('input');
                input.type = 'range';
                input.min = config.min || 0;
                input.max = config.max || 100;
                input.step = config.type === 'float' ? 0.1 : 1;
                input.value = config.default || config.min || 0;
                
                const valueSpan = document.createElement('span');
                valueSpan.className = 'param-value';
                valueSpan.textContent = input.value;
                
                input.addEventListener('input', () => {
                    valueSpan.textContent = parseFloat(input.value).toFixed(
                        config.type === 'float' ? 1 : 0
                    );
                });
                
                item.appendChild(valueSpan);
            }
            
            if (input) {
                input.id = `param-${name}`;
                input.dataset.name = name;
                input.dataset.type = config.type;
                item.insertBefore(input, item.lastChild);
            }
            
            container.appendChild(item);
        }
    }

    async applyPattern() {
        if (!this.currentPattern) return;
        
        const params = {};
        const inputs = document.querySelectorAll('#pattern-params input');
        
        for (const input of inputs) {
            const name = input.dataset.name;
            const type = input.dataset.type;
            
            if (type === 'bool') {
                params[name] = input.checked;
            } else if (type === 'int') {
                params[name] = parseInt(input.value);
            } else if (type === 'float') {
                params[name] = parseFloat(input.value);
            } else {
                params[name] = input.value;
            }
        }
        
        try {
            const response = await fetch('/api/pattern', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pattern: this.currentPattern.id,
                    params: params
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to apply pattern');
            }
            
            console.log('Pattern applied:', this.currentPattern.id, params);
        } catch (error) {
            console.error('Failed to apply pattern:', error);
        }
    }

    async updateStatus() {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();
            
            // Update DAC status
            const dacStatus = document.getElementById('dac-status');
            if (status.dac_connected) {
                dacStatus.textContent = 'Connected';
                dacStatus.className = 'status-value connected';
            } else {
                dacStatus.textContent = 'Disconnected';
                dacStatus.className = 'status-value disconnected';
            }
            
            // Update output status
            const outputStatus = document.getElementById('output-status');
            this.isRunning = status.running;
            if (status.running) {
                outputStatus.textContent = 'Running';
                outputStatus.className = 'status-value running';
            } else {
                outputStatus.textContent = 'Stopped';
                outputStatus.className = 'status-value stopped';
            }
            
            // Update mode status
            const modeStatus = document.getElementById('mode-status');
            if (status.simulate_mode) {
                modeStatus.textContent = 'Simulation';
                modeStatus.className = 'status-value simulation';
            } else {
                modeStatus.textContent = 'Hardware';
                modeStatus.className = 'status-value connected';
            }
            
        } catch (error) {
            console.error('Failed to update status:', error);
        }
    }

    async start() {
        try {
            await fetch('/api/start', { method: 'POST' });
            this.isRunning = true;
            this.updateStatus();
        } catch (error) {
            console.error('Failed to start:', error);
        }
    }

    async stop() {
        try {
            await fetch('/api/stop', { method: 'POST' });
            this.isRunning = false;
            this.updateStatus();
        } catch (error) {
            console.error('Failed to stop:', error);
        }
    }

    async setPps(pps) {
        try {
            await fetch('/api/pps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pps: pps })
            });
        } catch (error) {
            console.error('Failed to set PPS:', error);
        }
    }

    // ========================================================================
    // Capture Methods
    // ========================================================================

    async startWebcamCapture() {
        try {
            this.captureStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 320, height: 240 }
            });
            this.setupCapture();
        } catch (error) {
            console.error('Failed to start webcam:', error);
            alert('Failed to access webcam. Please ensure you have granted camera permissions.');
        }
    }

    async startScreenCapture() {
        try {
            this.captureStream = await navigator.mediaDevices.getDisplayMedia({
                video: { width: 320, height: 240 }
            });
            this.setupCapture();
        } catch (error) {
            console.error('Failed to start screen capture:', error);
            alert('Failed to start screen capture.');
        }
    }

    setupCapture() {
        // Set input mode to capture
        this.setInputMode('capture');
        
        // Show video preview
        if (this.captureVideo) {
            this.captureVideo.srcObject = this.captureStream;
            this.captureVideo.style.display = 'block';
        }
        
        // Setup capture canvas
        if (this.captureCanvas) {
            this.captureCanvas.width = 320;
            this.captureCanvas.height = 240;
        }
        
        // Update UI
        const btnWebcam = document.getElementById('btn-webcam');
        const btnScreen = document.getElementById('btn-screen');
        const btnStopCapture = document.getElementById('btn-stop-capture');
        
        if (btnWebcam) btnWebcam.classList.add('hidden');
        if (btnScreen) btnScreen.classList.add('hidden');
        if (btnStopCapture) btnStopCapture.classList.remove('hidden');
        
        // Start capture loop
        this.captureInterval = setInterval(() => this.captureFrame(), CAPTURE_FRAME_INTERVAL_MS);
    }

    stopCapture() {
        if (this.captureStream) {
            this.captureStream.getTracks().forEach(track => track.stop());
            this.captureStream = null;
        }
        
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
            this.captureInterval = null;
        }
        
        // Hide video preview
        if (this.captureVideo) {
            this.captureVideo.style.display = 'none';
            this.captureVideo.srcObject = null;
        }
        
        // Update UI
        const btnWebcam = document.getElementById('btn-webcam');
        const btnScreen = document.getElementById('btn-screen');
        const btnStopCapture = document.getElementById('btn-stop-capture');
        
        if (btnWebcam) btnWebcam.classList.remove('hidden');
        if (btnScreen) btnScreen.classList.remove('hidden');
        if (btnStopCapture) btnStopCapture.classList.add('hidden');
        
        // Switch back to pattern mode
        this.setInputMode('pattern');
    }

    async captureFrame() {
        if (!this.captureStream || !this.captureVideo || !this.captureVideo.videoWidth) return;
        if (!this.captureCanvas || !this.captureCtx) return;
        
        // Draw video frame to canvas
        this.captureCtx.drawImage(
            this.captureVideo,
            0, 0,
            this.captureCanvas.width,
            this.captureCanvas.height
        );
        
        // Get image data as base64
        const imageData = this.captureCanvas.toDataURL('image/jpeg', 0.7);
        
        try {
            await fetch('/api/input/capture/frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
        } catch (error) {
            console.error('Failed to send capture frame:', error);
        }
    }

    async applyCaptureParams() {
        const thresholdSlider = document.getElementById('threshold-slider');
        const threshold2Slider = document.getElementById('threshold2-slider');
        const blurSlider = document.getElementById('blur-slider');
        const decimateSlider = document.getElementById('decimate-slider');
        const useCanny = document.getElementById('use-canny');
        const invertEdges = document.getElementById('invert-edges');
        
        const params = {
            threshold: thresholdSlider ? parseInt(thresholdSlider.value) : 50,
            threshold2: threshold2Slider ? parseInt(threshold2Slider.value) : 100,
            blur_sigma: blurSlider ? parseFloat(blurSlider.value) / 10 : 1.0,
            decimate: decimateSlider ? parseInt(decimateSlider.value) : 2,
            use_canny: useCanny ? useCanny.checked : true,
            invert: invertEdges ? invertEdges.checked : false
        };
        
        try {
            await fetch('/api/input/capture/params', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params)
            });
            console.log('Capture params applied:', params);
        } catch (error) {
            console.error('Failed to apply capture params:', error);
        }
    }

    // ========================================================================
    // Recording Methods
    // ========================================================================

    async startRecording() {
        const name = prompt('Enter recording name:', 'Recording');
        if (!name) return;
        
        try {
            await fetch('/api/record/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            
            this.isRecording = true;
            this.recordingStartTime = Date.now();
            
            // Update UI
            const btnRecordStart = document.getElementById('btn-record-start');
            const btnRecordStop = document.getElementById('btn-record-stop');
            const recordingIndicator = document.getElementById('recording-indicator');
            
            if (btnRecordStart) btnRecordStart.disabled = true;
            if (btnRecordStop) btnRecordStop.disabled = false;
            if (recordingIndicator) recordingIndicator.classList.remove('hidden');
            
            // Start status updates
            this.recordingStatusInterval = setInterval(() => this.updateRecordingStatus(), 500);
            
        } catch (error) {
            console.error('Failed to start recording:', error);
        }
    }

    async stopRecording() {
        try {
            const response = await fetch('/api/record/stop', { method: 'POST' });
            const result = await response.json();
            
            this.isRecording = false;
            
            // Update UI
            const btnRecordStart = document.getElementById('btn-record-start');
            const btnRecordStop = document.getElementById('btn-record-stop');
            const recordingIndicator = document.getElementById('recording-indicator');
            const btnDownloadRecording = document.getElementById('btn-download-recording');
            
            if (btnRecordStart) btnRecordStart.disabled = false;
            if (btnRecordStop) btnRecordStop.disabled = true;
            if (recordingIndicator) recordingIndicator.classList.add('hidden');
            if (btnDownloadRecording) btnDownloadRecording.classList.remove('hidden');
            
            // Stop status updates
            if (this.recordingStatusInterval) {
                clearInterval(this.recordingStatusInterval);
                this.recordingStatusInterval = null;
            }
            
            // Show final stats
            const recordFrameCount = document.getElementById('record-frame-count');
            const recordDuration = document.getElementById('record-duration');
            
            if (recordFrameCount) recordFrameCount.textContent = `Frames: ${result.frame_count}`;
            if (recordDuration) recordDuration.textContent = `Duration: ${result.duration.toFixed(1)}s`;
            
        } catch (error) {
            console.error('Failed to stop recording:', error);
        }
    }

    async updateRecordingStatus() {
        try {
            const response = await fetch('/api/record/status');
            const status = await response.json();
            
            const recordFrameCount = document.getElementById('record-frame-count');
            const recordDuration = document.getElementById('record-duration');
            
            if (recordFrameCount) recordFrameCount.textContent = `Frames: ${status.frame_count}`;
            if (recordDuration) recordDuration.textContent = `Duration: ${status.duration.toFixed(1)}s`;
            
        } catch (error) {
            console.error('Failed to update recording status:', error);
        }
    }

    downloadRecording() {
        window.location.href = '/api/record/download?format=2d_rgb';
    }

    // ========================================================================
    // Editor Methods
    // ========================================================================

    async loadIldaFile(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/editor/load', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            } else {
                alert('Failed to load ILDA file: ' + result.message);
            }
        } catch (error) {
            console.error('Failed to load ILDA file:', error);
        }
    }

    async loadRecordingToEditor() {
        try {
            const response = await fetch('/api/editor/load-recording', { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            } else {
                alert('Failed to load recording: ' + result.message);
            }
        } catch (error) {
            console.error('Failed to load recording to editor:', error);
        }
    }

    updateEditorUI(info) {
        this.editorLoaded = true;
        
        // Show editor info
        const editorInfo = document.getElementById('editor-info');
        const editorFilename = document.getElementById('editor-filename');
        const editorFrameCount = document.getElementById('editor-frame-count');
        const editorPointCount = document.getElementById('editor-point-count');
        const btnDownloadIlda = document.getElementById('btn-download-ilda');
        const editorFrameList = document.getElementById('editor-frame-list');
        const editorTransform = document.getElementById('editor-transform');
        
        if (editorInfo) editorInfo.classList.remove('hidden');
        if (editorFilename) editorFilename.textContent = info.name || 'Unknown';
        if (editorFrameCount) editorFrameCount.textContent = info.frame_count;
        if (editorPointCount) editorPointCount.textContent = info.total_points;
        
        // Enable download button
        if (btnDownloadIlda) btnDownloadIlda.disabled = false;
        
        // Show frame list
        if (editorFrameList) {
            editorFrameList.classList.remove('hidden');
            this.renderFrameList(info.frames);
        }
        
        // Show transform controls
        if (editorTransform) editorTransform.classList.remove('hidden');
    }

    renderFrameList(frames) {
        const container = document.getElementById('frame-list-container');
        if (!container) return;
        
        container.innerHTML = frames.map((frame, index) => `
            <div class="frame-item" data-index="${index}">
                <div class="frame-item-info">
                    #${index + 1} - ${frame.point_count} points
                </div>
                <div class="frame-item-buttons">
                    <button class="btn btn-small" onclick="app.playFrame(${index})">▶</button>
                    <button class="btn btn-small" onclick="app.duplicateFrame(${index})">📋</button>
                    <button class="btn btn-small btn-danger" onclick="app.deleteFrame(${index})">🗑</button>
                </div>
            </div>
        `).join('');
        
        // Add click handlers for frame selection
        container.querySelectorAll('.frame-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.tagName !== 'BUTTON') {
                    this.selectFrame(parseInt(item.dataset.index));
                }
            });
        });
    }

    async selectFrame(index) {
        this.currentFrameIndex = index;
        
        // Update UI
        document.querySelectorAll('.frame-item').forEach((item, i) => {
            item.classList.toggle('active', i === index);
        });
        
        // Load frame preview
        try {
            const response = await fetch(`/api/editor/frame/${index}`);
            const points = await response.json();
            this.renderFrame(points);
        } catch (error) {
            console.error('Failed to load frame:', error);
        }
    }

    async playFrame(index) {
        try {
            await fetch(`/api/editor/play/${index}`, { method: 'POST' });
        } catch (error) {
            console.error('Failed to play frame:', error);
        }
    }

    async deleteFrame(index) {
        if (!confirm('Delete this frame?')) return;
        
        try {
            const response = await fetch(`/api/editor/frame/${index}/delete`, { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            }
        } catch (error) {
            console.error('Failed to delete frame:', error);
        }
    }

    async duplicateFrame(index) {
        try {
            const response = await fetch(`/api/editor/frame/${index}/duplicate`, { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            }
        } catch (error) {
            console.error('Failed to duplicate frame:', error);
        }
    }

    async editorUndo() {
        try {
            const response = await fetch('/api/editor/undo', { method: 'POST' });
            const result = await response.json();
            
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            } else {
                alert(result.message || 'Nothing to undo');
            }
        } catch (error) {
            console.error('Failed to undo:', error);
        }
    }

    async editorScale() {
        const scaleX = parseFloat(prompt('Scale X (0.1-2.0):', '1.0'));
        const scaleY = parseFloat(prompt('Scale Y (0.1-2.0):', '1.0'));
        
        if (isNaN(scaleX) || isNaN(scaleY)) return;
        
        try {
            const response = await fetch('/api/editor/transform', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'scale',
                    scale_x: scaleX,
                    scale_y: scaleY
                })
            });
            
            const result = await response.json();
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            }
        } catch (error) {
            console.error('Failed to scale:', error);
        }
    }

    async editorRotate() {
        const angle = parseFloat(prompt('Rotation angle (degrees):', '0'));
        if (isNaN(angle)) return;
        
        try {
            const response = await fetch('/api/editor/transform', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'rotate',
                    angle: angle
                })
            });
            
            const result = await response.json();
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            }
        } catch (error) {
            console.error('Failed to rotate:', error);
        }
    }

    async editorSetColor() {
        const color = prompt('Enter color (hex, e.g., #FF0000):', '#FFFFFF');
        if (!color) return;
        
        // Parse hex color
        const hex = color.replace('#', '');
        const r = parseInt(hex.substring(0, 2), 16);
        const g = parseInt(hex.substring(2, 4), 16);
        const b = parseInt(hex.substring(4, 6), 16);
        
        if (isNaN(r) || isNaN(g) || isNaN(b)) {
            alert('Invalid color format');
            return;
        }
        
        try {
            const response = await fetch('/api/editor/transform', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    operation: 'set_color',
                    r: r, g: g, b: b
                })
            });
            
            const result = await response.json();
            if (result.status === 'ok') {
                this.updateEditorUI(result.info);
            }
        } catch (error) {
            console.error('Failed to set color:', error);
        }
    }

    downloadEditorFile() {
        window.location.href = '/api/editor/download?format=2d_rgb';
    }

    // ========================================================================
    // Preview Methods
    // ========================================================================

    startPreviewStream() {
        const eventSource = new EventSource('/api/frame/stream');
        
        eventSource.onmessage = (event) => {
            try {
                const points = JSON.parse(event.data);
                this.renderFrame(points);
            } catch (error) {
                console.error('Failed to parse frame:', error);
            }
        };
        
        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            // Reconnect after a delay
            setTimeout(() => {
                eventSource.close();
                this.startPreviewStream();
            }, SSE_RECONNECT_DELAY_MS);
        };
    }

    renderFrame(points) {
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // Clear with fade effect
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        this.ctx.fillRect(0, 0, width, height);
        
        if (!points || points.length === 0) return;
        
        // Draw points and lines
        let lastPoint = null;
        let lastColor = null;
        
        for (const point of points) {
            // Convert from Helios coordinates (0-4095) to canvas
            const x = (point.x / 4095) * width;
            const y = height - (point.y / 4095) * height;  // Flip Y
            
            const color = `rgb(${point.r}, ${point.g}, ${point.b})`;
            const brightness = (point.r + point.g + point.b) / 3;
            
            if (brightness > 0) {
                // Draw glow
                const gradient = this.ctx.createRadialGradient(x, y, 0, x, y, 3);
                gradient.addColorStop(0, color);
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
                
                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.arc(x, y, 3, 0, Math.PI * 2);
                this.ctx.fill();
                
                // Draw line from last point if same color and both visible
                if (lastPoint && lastColor === color) {
                    this.ctx.strokeStyle = color;
                    this.ctx.lineWidth = 1;
                    this.ctx.globalAlpha = 0.7;
                    this.ctx.beginPath();
                    this.ctx.moveTo(lastPoint.x, lastPoint.y);
                    this.ctx.lineTo(x, y);
                    this.ctx.stroke();
                    this.ctx.globalAlpha = 1;
                }
                
                lastPoint = { x, y };
                lastColor = color;
            } else {
                lastPoint = null;
                lastColor = null;
            }
        }
        
        // Update FPS counter
        this.frameCount++;
        const now = Date.now();
        if (now - this.lastFpsUpdate >= 1000) {
            this.fps = this.frameCount;
            this.frameCount = 0;
            this.lastFpsUpdate = now;
            document.getElementById('fps-display').textContent = `FPS: ${this.fps}`;
        }
        
        // Update point count
        document.getElementById('point-count').textContent = `Points: ${points.length}`;
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new OpenLaseApp();
});
