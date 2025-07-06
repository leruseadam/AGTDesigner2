class GenerationSplash {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element with id '${canvasId}' not found`);
        }
        
        this.ctx = this.canvas.getContext('2d');
        if (!this.ctx) {
            throw new Error('2D context not supported');
        }
        
        this.options = {
            width: options.width || 500,
            height: options.height || 350,
            labelCount: options.labelCount || 0,
            templateType: options.templateType || 'Horizontal',
            ...options
        };
        
        this.time = 0;
        this.animationId = null;
        this.isRunning = false;
        this.generationProgress = 0;
        this.particles = [];
        
        this.init();
    }
    
    init() {
        try {
            // Set canvas size
            this.canvas.width = this.options.width;
            this.canvas.height = this.options.height;
            
            // Create particles
            this.createParticles();
            
            // Start animation
            this.isRunning = true;
            this.animate();
        } catch (error) {
            console.error('Error initializing GenerationSplash:', error);
            throw error;
        }
    }
    
    createParticles() {
        this.particles = [];
        const particleCount = 20;
        
        for (let i = 0; i < particleCount; i++) {
                this.particles.push({
                    x: Math.random() * this.options.width,
                    y: Math.random() * this.options.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                size: Math.random() * 2 + 1,
                opacity: Math.random() * 0.3 + 0.1,
                color: '#00d4aa'
            });
    }
    }
    
    animate() {
        if (!this.isRunning) return;
        
        this.time += 0.016; // 60fps
        this.update();
        this.draw();
            
            this.animationId = requestAnimationFrame(() => this.animate());
        }
    
    update() {
        // Update particles
        this.particles.forEach(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            // Wrap around edges
            if (particle.x < 0) particle.x = this.options.width;
            if (particle.x > this.options.width) particle.x = 0;
            if (particle.y < 0) particle.y = this.options.height;
            if (particle.y > this.options.height) particle.y = 0;
            
            // Subtle opacity animation
            particle.opacity = 0.1 + 0.2 * Math.sin(this.time + particle.x * 0.01);
        });
    }
    
    draw() {
        // Clear canvas with gradient background
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.options.height);
        gradient.addColorStop(0, '#1a1a2e');
        gradient.addColorStop(0.5, '#16213e');
        gradient.addColorStop(1, '#0f3460');
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.options.width, this.options.height);
        
        // Draw particles
        this.particles.forEach(particle => {
            this.ctx.save();
            this.ctx.globalAlpha = particle.opacity;
            this.ctx.fillStyle = particle.color;
            this.ctx.beginPath();
            this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.restore();
        });
        
        // Draw subtle grid pattern
        this.drawGrid();
            
        // Draw central content area
        this.drawContentArea();
    }
    
    drawGrid() {
        this.ctx.strokeStyle = 'rgba(0, 212, 170, 0.05)';
        this.ctx.lineWidth = 1;
        
        const gridSize = 30;
        for (let x = 0; x < this.options.width; x += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.options.height);
            this.ctx.stroke();
        }
        
        for (let y = 0; y < this.options.height; y += gridSize) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.options.width, y);
            this.ctx.stroke();
        }
    }
    
    drawContentArea() {
        const centerX = this.options.width / 2;
        const centerY = this.options.height / 2;
        const contentWidth = 400;
        const contentHeight = 250;
        
        // Draw content background
        this.ctx.save();
        this.ctx.fillStyle = 'rgba(22, 33, 62, 0.8)';
        this.ctx.strokeStyle = 'rgba(0, 212, 170, 0.3)';
        this.ctx.lineWidth = 2;
        
        // Rounded rectangle
        const radius = 20;
                this.ctx.beginPath();
        this.ctx.moveTo(centerX - contentWidth/2 + radius, centerY - contentHeight/2);
        this.ctx.lineTo(centerX + contentWidth/2 - radius, centerY - contentHeight/2);
        this.ctx.quadraticCurveTo(centerX + contentWidth/2, centerY - contentHeight/2, centerX + contentWidth/2, centerY - contentHeight/2 + radius);
        this.ctx.lineTo(centerX + contentWidth/2, centerY + contentHeight/2 - radius);
        this.ctx.quadraticCurveTo(centerX + contentWidth/2, centerY + contentHeight/2, centerX + contentWidth/2 - radius, centerY + contentHeight/2);
        this.ctx.lineTo(centerX - contentWidth/2 + radius, centerY + contentHeight/2);
        this.ctx.quadraticCurveTo(centerX - contentWidth/2, centerY + contentHeight/2, centerX - contentWidth/2, centerY + contentHeight/2 - radius);
        this.ctx.lineTo(centerX - contentWidth/2, centerY - contentHeight/2 + radius);
        this.ctx.quadraticCurveTo(centerX - contentWidth/2, centerY - contentHeight/2, centerX - contentWidth/2 + radius, centerY - contentHeight/2);
        this.ctx.closePath();
        
                this.ctx.fill();
        this.ctx.stroke();
        this.ctx.restore();
        
        // Draw title
        this.ctx.save();
        this.ctx.fillStyle = '#00d4aa';
        this.ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('LABEL MAKER', centerX, centerY - 60);
        
        // Draw subtitle
            this.ctx.fillStyle = '#ffffff';
        this.ctx.font = '16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        this.ctx.fillText('Generating Labels...', centerX, centerY - 30);
            
        // Draw progress bar
        this.drawProgressBar(centerX, centerY);
        
        // Draw status text
        this.ctx.fillStyle = '#cccccc';
        this.ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        this.ctx.fillText('Processing your request...', centerX, centerY + 40);
        
        // Draw loading dots
        this.drawLoadingDots(centerX, centerY + 70);
        
        this.ctx.restore();
    }
    
    drawProgressBar(centerX, centerY) {
        const barWidth = 300;
        const barHeight = 6;
        const barX = centerX - barWidth / 2;
        const barY = centerY + 10;
        
        // Background
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.fillRect(barX, barY, barWidth, barHeight);
        
        // Progress fill
        const progress = (Math.sin(this.time * 2) + 1) / 2; // Animated progress
        const fillWidth = barWidth * progress;
        
        const gradient = this.ctx.createLinearGradient(barX, barY, barX + fillWidth, barY);
        gradient.addColorStop(0, '#00d4aa');
        gradient.addColorStop(1, '#0099cc');
        
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(barX, barY, fillWidth, barHeight);
        
        // Shimmer effect
        const shimmerX = barX + (this.time * 100) % (barWidth + 50) - 25;
        const shimmerGradient = this.ctx.createLinearGradient(shimmerX, barY, shimmerX + 50, barY);
        shimmerGradient.addColorStop(0, 'transparent');
        shimmerGradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.3)');
        shimmerGradient.addColorStop(1, 'transparent');
        
        this.ctx.fillStyle = shimmerGradient;
        this.ctx.fillRect(barX, barY, fillWidth, barHeight);
    }
    
    drawLoadingDots(centerX, centerY) {
        const dotRadius = 4;
        const dotSpacing = 20;
        const totalWidth = dotSpacing * 2;
        const startX = centerX - totalWidth / 2;
        
        for (let i = 0; i < 3; i++) {
            const x = startX + i * dotSpacing;
            const opacity = 0.4 + 0.6 * Math.sin(this.time * 3 + i * 2);
            const scale = 0.8 + 0.4 * Math.sin(this.time * 3 + i * 2);
            
            this.ctx.save();
            this.ctx.globalAlpha = opacity;
            this.ctx.fillStyle = '#00d4aa';
            this.ctx.beginPath();
            this.ctx.arc(x, centerY, dotRadius * scale, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.restore();
        }
    }
    
    // Method to start animation
    start() {
        this.isRunning = true;
        this.animate();
    }
    
    // Method to stop animation
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }
    
    // Method to hide splash screen
    hide() {
        this.stop();
        if (this.canvas) {
            this.canvas.style.display = 'none';
        }
    }
    
    // Method to show splash screen
    show() {
        if (this.canvas) {
            this.canvas.style.display = 'block';
        }
        if (!this.isRunning) {
            this.animate();
        }
    }
    
    // Method to update generation progress
    updateProgress(progress) {
        this.generationProgress = progress;
    }
}

// Auto-initialize if canvas exists
document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('generation-splash-canvas');
    if (canvas) {
        try {
            // Get parameters from URL
            const urlParams = new URLSearchParams(window.location.search);
            const labelCount = urlParams.get('count') || '0';
            const templateType = urlParams.get('template') || 'Horizontal';
            
            window.generationSplash = new GenerationSplash('generation-splash-canvas', {
                width: 500,
                height: 350,
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