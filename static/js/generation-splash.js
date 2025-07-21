class GenerationSplash {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container element with id '${containerId}' not found`);
        }
        
        this.options = {
            labelCount: options.labelCount || 0,
            templateType: options.templateType || 'Horizontal',
            ...options
        };
        
        this.isRunning = false;
        this.generationProgress = 0;
        this.statusTextIndex = 0;
        this.statusTextInterval = null;
        
        this.init();
    }
    
    init() {
        try {
            // Create the splash HTML structure
            this.createSplashHTML();
            
            // Start animations
            this.isRunning = true;
            this.startStatusTextAnimation();
            
            // Add interactive effects
            this.addInteractiveEffects();
        } catch (error) {
            console.error('Error initializing GenerationSplash:', error);
            throw error;
        }
    }
    
    createSplashHTML() {
        this.container.innerHTML = `
            <div class="background-pattern"></div>
            
            <div id="generation-splash-container">
                <div class="splash-content">
                    <div class="logo-container">
                        <div class="logo-icon">🏷️</div>
                    </div>
                    
                    <h1 class="app-title">LABEL MAKER</h1>
                    <div class="generation-status">Generating Labels...</div>
                    
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div class="progress-fill"></div>
                        </div>
                        <div class="status-text">Processing your request...</div>
                    </div>
                    
                    <div class="loading-dots">
                        <div class="dot"></div>
                        <div class="dot"></div>
                        <div class="dot"></div>
                    </div>
                    
                    <div class="generation-details">
                        <div class="detail">
                            <div class="detail-icon">📄</div>
                            <div class="detail-text">Templates</div>
                        </div>
                        <div class="detail">
                            <div class="detail-icon">⚙️</div>
                            <div class="detail-text">Processing</div>
                        </div>
                        <div class="detail">
                            <div class="detail-icon">✅</div>
                            <div class="detail-text">Quality</div>
                        </div>
                    </div>
                </div>
                
                <div class="version-badge">v2.0.0</div>
                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span>Processing</span>
                </div>
            </div>
        `;
        
        // Add CSS styles
        this.addStyles();
    }
    
    addStyles() {
        const styleId = 'generation-splash-styles';
        if (document.getElementById(styleId)) {
            return; // Styles already added
        }
        
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            .generation-splash-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 9999;
                display: flex;
                justify-content: center;
                align-items: center;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            }
            
            .generation-splash-backdrop {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
            }
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            .background-pattern {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                opacity: 0.1;
                background-image: 
                    radial-gradient(circle at 20% 80%, #00d4aa 0%, transparent 50%),
                    radial-gradient(circle at 80% 20%, #00d4aa 0%, transparent 50%),
                    radial-gradient(circle at 40% 40%, #00d4aa 0%, transparent 50%);
                animation: background-shift 8s ease-in-out infinite;
            }
            
            @keyframes background-shift {
                0%, 100% { transform: scale(1) rotate(0deg); }
                50% { transform: scale(1.1) rotate(180deg); }
            }
            
            #generation-splash-container {
                position: relative;
                width: 600px;
                height: 400px;
                border-radius: 24px;
                overflow: hidden;
                background: rgba(22, 33, 62, 0.95);
                border: 1px solid rgba(0, 212, 170, 0.2);
                box-shadow: 
                    0 20px 40px rgba(0, 0, 0, 0.3),
                    0 0 0 1px rgba(0, 212, 170, 0.1);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                z-index: 2;
                transform: translateX(0);
            }
            
            .splash-content {
                position: relative;
                width: 100%;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 60px;
                color: white;
                text-align: center;
            }
            
            .logo-container {
                position: relative;
                margin-bottom: 30px;
            }
            
            .logo-icon {
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #00d4aa, #0099cc);
                border-radius: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 36px;
                box-shadow: 
                    0 15px 35px rgba(0, 212, 170, 0.3),
                    0 0 0 1px rgba(0, 212, 170, 0.2);
                animation: logo-float 3s ease-in-out infinite;
                position: relative;
            }
            
            .logo-icon::before {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                background: linear-gradient(45deg, #00d4aa, #0099cc, #00d4aa);
                border-radius: 22px;
                z-index: -1;
                animation: logo-glow 2s ease-in-out infinite alternate;
            }
            
            @keyframes logo-float {
                0%, 100% { 
                    transform: translateY(0px) scale(1);
                }
                50% { 
                    transform: translateY(-8px) scale(1.02);
                }
            }
            
            @keyframes logo-glow {
                0% { opacity: 0.6; }
                100% { opacity: 1; }
            }
            
            .app-title {
                font-size: 42px;
                font-weight: 800;
                margin-bottom: 12px;
                background: linear-gradient(135deg, #00d4aa, #ffffff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                letter-spacing: -0.5px;
                text-shadow: 
                    0 2px 8px rgba(0,0,0,0.4),
                    0 4px 16px rgba(0,0,0,0.3),
                    0 1px 2px rgba(160,132,232,0.3),
                    0 0 20px rgba(160,132,232,0.2);
                filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
            }
            
            .generation-status {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 30px;
                color: #ffffff;
                letter-spacing: 1px;
                text-transform: uppercase;
                text-shadow: 
                    0 2px 6px rgba(0,0,0,0.4),
                    0 3px 12px rgba(0,0,0,0.3),
                    0 1px 2px rgba(139,92,246,0.3),
                    0 0 15px rgba(139,92,246,0.2);
                filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
            }
            
            .progress-container {
                width: 100%;
                max-width: 400px;
                margin-bottom: 30px;
            }
            
            .progress-bar {
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                margin-bottom: 20px;
                position: relative;
            }
            
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #00d4aa, #0099cc, #00d4aa);
                border-radius: 3px;
                animation: progress-animation 2s ease-in-out infinite;
                position: relative;
            }
            
            .progress-fill::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
                animation: shimmer 1.5s ease-in-out infinite;
            }
            
            @keyframes progress-animation {
                0% { width: 0%; }
                50% { width: 100%; }
                100% { width: 0%; }
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            .status-text {
                font-size: 16px;
                font-weight: 500;
                opacity: 0.8;
                margin-bottom: 25px;
                transition: opacity 0.3s ease;
            }
            
            .loading-dots {
                display: flex;
                gap: 8px;
                justify-content: center;
                margin-bottom: 25px;
            }
            
            .dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: rgba(0, 212, 170, 0.6);
                animation: dot-pulse 1.6s ease-in-out infinite both;
            }
            
            .dot:nth-child(1) { animation-delay: -0.32s; }
            .dot:nth-child(2) { animation-delay: -0.16s; }
            .dot:nth-child(3) { animation-delay: 0s; }
            
            @keyframes dot-pulse {
                0%, 80%, 100% {
                    transform: scale(0.8);
                    opacity: 0.4;
                }
                40% {
                    transform: scale(1.2);
                    opacity: 1;
                }
            }
            
            .version-badge {
                position: absolute;
                top: 20px;
                right: 20px;
                background: rgba(0, 212, 170, 0.15);
                padding: 6px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 212, 170, 0.2);
                color: #00d4aa;
            }
            
            .status-indicator {
                position: absolute;
                top: 20px;
                left: 20px;
                display: flex;
                align-items: center;
                gap: 6px;
                background: rgba(0, 212, 170, 0.15);
                padding: 6px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 212, 170, 0.2);
                color: #00d4aa;
            }
            
            .status-dot {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #00d4aa;
                animation: status-pulse 2s ease-in-out infinite;
            }
            
            @keyframes status-pulse {
                0%, 100% { opacity: 0.5; }
                50% { opacity: 1; }
            }
            
            .generation-details {
                display: flex;
                gap: 25px;
                margin-top: 15px;
            }
            
            .detail {
                text-align: center;
                opacity: 0.6;
            }
            
            .detail-icon {
                font-size: 20px;
                margin-bottom: 6px;
            }
            
            .detail-text {
                font-size: 11px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            @media (max-width: 1200px) {
                #generation-splash-container {
                    transform: translateX(0);
                    width: 90vw;
                    max-width: 600px;
                }
            }
            
            @media (max-width: 900px) {
                #generation-splash-container {
                    transform: translateX(0);
                    width: 90vw;
                    max-width: 500px;
                }
            }
        `;
        
        document.head.appendChild(style);
    }
    
    startStatusTextAnimation() {
        const statusTexts = [
            'Processing your request...',
            'Loading templates...',
            'Generating labels...',
            'Applying formatting...',
            'Finalizing document...',
            'Almost complete...'
        ];
        
        const statusTextElement = this.container.querySelector('.status-text');
        if (!statusTextElement) return;
        
        this.statusTextInterval = setInterval(() => {
            statusTextElement.style.opacity = '0';
            setTimeout(() => {
                statusTextElement.textContent = statusTexts[this.statusTextIndex];
                statusTextElement.style.opacity = '1';
                this.statusTextIndex = (this.statusTextIndex + 1) % statusTexts.length;
            }, 300);
        }, 1500);
    }
    
    addInteractiveEffects() {
        const container = this.container.querySelector('#generation-splash-container');
        if (!container) return;
        
        document.addEventListener('mousemove', (e) => {
            if (!this.isRunning) return;
            
            const rect = container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = (y - centerY) / 30;
            const rotateY = (centerX - x) / 30;
            
            container.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
        });
        
        document.addEventListener('mouseleave', () => {
            if (!this.isRunning) return;
            container.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
        });
    }
    
    // Method to start animation
    start() {
        this.isRunning = true;
        this.startStatusTextAnimation();
    }
    
    // Method to stop animation
    stop() {
        this.isRunning = false;
        if (this.statusTextInterval) {
            clearInterval(this.statusTextInterval);
            this.statusTextInterval = null;
        }
    }
    
    // Method to hide splash screen
    hide() {
        this.stop();
        if (this.container) {
            this.container.style.display = 'none';
        }
    }
    
    // Method to show splash screen
    show() {
        if (this.container) {
            this.container.style.display = 'flex';
        }
        if (!this.isRunning) {
            this.start();
        }
    }
    
    // Method to update generation progress
    updateProgress(progress) {
        this.generationProgress = progress;
        // Update progress bar if needed
        const progressFill = this.container.querySelector('.progress-fill');
        if (progressFill && progress >= 0 && progress <= 100) {
            progressFill.style.width = `${progress}%`;
        }
    }
    
    // Method to update status text
    updateStatusText(text) {
        const statusTextElement = this.container.querySelector('.status-text');
        if (statusTextElement) {
            statusTextElement.textContent = text;
        }
    }
}

// Auto-initialize if container exists
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('generationSplashModal');
    if (container) {
        try {
            // Get parameters from URL
            const urlParams = new URLSearchParams(window.location.search);
            const labelCount = urlParams.get('count') || '0';
            const templateType = urlParams.get('template') || 'Horizontal';
            
            window.generationSplash = new GenerationSplash('generationSplashModal', {
                labelCount: parseInt(labelCount),
                templateType: templateType
            });
        } catch (error) {
            console.error('Failed to initialize generation splash:', error);
            // Trigger fallback in the main script
            if (typeof showFallback === 'function') {
                showFallback();
            }
        }
    }
});

window.GenerationSplash = GenerationSplash; 