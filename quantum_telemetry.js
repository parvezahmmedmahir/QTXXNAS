// QUANTUM X PRO - ENTERPRISE TELEMETRY ENGINE
// Ultra-Powerful Data Collection System
// Place this in index.html after FingerprintJS is loaded

class QuantumTelemetry {
    constructor() {
        this.deviceId = null;
        this.licenseKey = null;
        this.telemetryInterval = null;
        this.API_BASE = null;
    }

    async initialize(licenseKey) {
        this.licenseKey = licenseKey;
        this.deviceId = await this.getDeviceFingerprint();
        this.API_BASE = this.getAPIBase();

        console.log('[TELEMETRY] Quantum Tracking Initialized');

        // Immediate data collection
        await this.collectAllData();

        // Start continuous tracking (every 30 seconds)
        this.startContinuousTracking();
    }

    getAPIBase() {
        const isLocal = window.location.hostname === 'localhost' ||
            window.location.hostname === '127.0.0.1' ||
            window.location.protocol === 'file:';
        const PROD_URL = 'https://quantum-x-pro.onrender.com';
        return isLocal ? 'http://127.0.0.1:5000' :
            (window.location.hostname.includes('onrender.com') ? window.location.origin : PROD_URL);
    }

    async getDeviceFingerprint() {
        const fpPromise = FingerprintJS.load();
        const fp = await fpPromise;
        const result = await fp.get();
        const browserFp = result.visitorId;

        // Canvas fingerprint
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = "top";
        ctx.font = "16px 'Outfit', sans-serif";
        ctx.fillStyle = "#3b82f6";
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = "#fff";
        ctx.fillText("Quantum-X-Pro-Guardian-v6", 2, 15);
        const canvasData = canvas.toDataURL();

        // GPU info
        const gl = document.createElement('canvas').getContext('webgl');
        const debugInfo = gl ? gl.getExtension('WEBGL_debug_renderer_info') : null;
        const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : "Unknown_GPU";

        // Create comprehensive fingerprint
        const info = {
            visitor: browserFp,
            gpu: renderer,
            resolution: `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}`,
            hardware: {
                cores: navigator.hardwareConcurrency || 0,
                memory: navigator.deviceMemory || 0,
                platform: navigator.platform,
                language: navigator.language
            },
            context: canvasData.slice(-64)
        };

        const rawString = JSON.stringify(info);
        let hash = 0;
        for (let i = 0; i < rawString.length; i++) {
            const char = rawString.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }

        return `QX-HW-${Math.abs(hash).toString(16).toUpperCase()}-${browserFp.slice(0, 8).toUpperCase()}`;
    }

    async getRealIP() {
        try {
            const response = await fetch('https://api.ipify.org?format=json');
            const data = await response.json();
            return data.ip;
        } catch {
            return 'Unknown';
        }
    }

    async getGeolocation() {
        try {
            const ip = await this.getRealIP();
            const response = await fetch(`http://ip-api.com/json/${ip}`);
            const data = await response.json();
            return {
                ip: ip,
                country: data.country || 'Unknown',
                region: data.regionName || 'Unknown',
                city: data.city || 'Unknown',
                latitude: data.lat || 0,
                longitude: data.lon || 0,
                isp: data.isp || 'Unknown',
                organization: data.org || 'Unknown',
                timezone: data.timezone || 'Unknown',
                postal: data.zip || 'Unknown'
            };
        } catch {
            return {
                ip: await this.getRealIP(),
                country: 'Unknown',
                region: 'Unknown',
                city: 'Unknown',
                latitude: 0,
                longitude: 0,
                isp: 'Unknown',
                organization: 'Unknown',
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                postal: 'Unknown'
            };
        }
    }

    getBrowserInfo() {
        const ua = navigator.userAgent;
        let browserName = 'Unknown', browserVersion = 'Unknown';
        let osName = 'Unknown', osVersion = 'Unknown';

        // Browser detection
        if (ua.indexOf('Firefox') > -1) {
            browserName = 'Firefox';
            browserVersion = ua.match(/Firefox\/([0-9.]+)/)?.[1] || 'Unknown';
        } else if (ua.indexOf('Chrome') > -1) {
            browserName = 'Chrome';
            browserVersion = ua.match(/Chrome\/([0-9.]+)/)?.[1] || 'Unknown';
        } else if (ua.indexOf('Safari') > -1) {
            browserName = 'Safari';
            browserVersion = ua.match(/Version\/([0-9.]+)/)?.[1] || 'Unknown';
        } else if (ua.indexOf('Edge') > -1) {
            browserName = 'Edge';
            browserVersion = ua.match(/Edge\/([0-9.]+)/)?.[1] || 'Unknown';
        }

        // OS detection
        if (ua.indexOf('Windows NT 10.0') > -1) osName = 'Windows 10';
        else if (ua.indexOf('Windows NT 6.3') > -1) osName = 'Windows 8.1';
        else if (ua.indexOf('Windows NT 6.2') > -1) osName = 'Windows 8';
        else if (ua.indexOf('Windows NT 6.1') > -1) osName = 'Windows 7';
        else if (ua.indexOf('Mac OS X') > -1) osName = 'macOS';
        else if (ua.indexOf('Linux') > -1) osName = 'Linux';
        else if (ua.indexOf('Android') > -1) osName = 'Android';
        else if (ua.indexOf('iOS') > -1) osName = 'iOS';

        return {
            browserName,
            browserVersion,
            osName,
            osVersion,
            isMobile: /Mobile|Android|iPhone/i.test(ua),
            isTablet: /iPad|Tablet/i.test(ua),
            screenWidth: window.screen.width,
            screenHeight: window.screen.height,
            colorDepth: window.screen.colorDepth,
            pixelRatio: window.devicePixelRatio || 1,
            touchSupport: 'ontouchstart' in window
        };
    }

    getNetworkInfo() {
        const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (conn) {
            return {
                connectionType: conn.type || 'Unknown',
                effectiveType: conn.effectiveType || 'Unknown',
                downlink: conn.downlink || 0,
                rtt: conn.rtt || 0,
                saveData: conn.saveData || false
            };
        }
        return {
            connectionType: 'Unknown',
            effectiveType: 'Unknown',
            downlink: 0,
            rtt: 0,
            saveData: false
        };
    }

    async collectAllData() {
        console.log('[TELEMETRY] Collecting comprehensive data...');

        const geo = await this.getGeolocation();
        const browser = this.getBrowserInfo();
        const network = this.getNetworkInfo();

        const payload = {
            license_key: this.licenseKey,
            device_id: this.deviceId,

            // Geolocation data
            geo: geo,

            // Browser data
            browser: browser,

            // Network data
            network: network,

            // Device fingerprint details
            fingerprint: {
                canvas: document.createElement('canvas').toDataURL().slice(-64),
                webgl: this.getWebGLInfo(),
                screen: `${window.screen.width}x${window.screen.height}`,
                cores: navigator.hardwareConcurrency || 0,
                memory: navigator.deviceMemory || 0,
                platform: navigator.platform,
                language: navigator.language,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            }
        };

        try {
            const response = await fetch(`${this.API_BASE}/api/telemetry/collect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                console.log('[TELEMETRY] ✅ Data collected successfully');
            }
        } catch (error) {
            console.warn('[TELEMETRY] Collection failed:', error);
        }
    }

    getWebGLInfo() {
        const gl = document.createElement('canvas').getContext('webgl');
        if (!gl) return 'Not Supported';
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        return debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'Unknown';
    }

    startContinuousTracking() {
        // Clear any existing interval
        if (this.telemetryInterval) {
            clearInterval(this.telemetryInterval);
        }

        // Collect data every 30 seconds
        this.telemetryInterval = setInterval(async () => {
            await this.collectAllData();
        }, 30000); // 30 seconds

        console.log('[TELEMETRY] Continuous tracking started (30s interval)');
    }

    stop() {
        if (this.telemetryInterval) {
            clearInterval(this.telemetryInterval);
            console.log('[TELEMETRY] Tracking stopped');
        }
    }
}

// Global telemetry instance
window.quantumTelemetry = new QuantumTelemetry();
