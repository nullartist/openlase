/**
 * OpenLase Web - Frontend Application
 * 
 * Provides the user interface for controlling the laser output
 * and previewing patterns.
 */

// Constants
const SSE_RECONNECT_DELAY_MS = 2000;  // Milliseconds before SSE reconnection
const STATUS_UPDATE_INTERVAL_MS = 2000;  // Milliseconds between status updates

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
        
        // Pattern selection
        document.getElementById('pattern-select').addEventListener('change', (e) => {
            this.onPatternChange(e.target.value);
        });
        
        // Apply pattern button
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
