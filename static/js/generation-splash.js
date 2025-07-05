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
            height: options.height || 400,
            blobCount: options.blobCount || 12,
            speed: options.speed || 0.03,
            labelCount: options.labelCount || 0,
            templateType: options.templateType || 'Horizontal',
            ...options
        };
        
        this.blobs = [];
        this.particles = [];
        this.time = 0;
        this.gradient = null;
        this.animationId = null;
        this.isRunning = false;
        this.generationProgress = 0;
        
        this.init();
    }
    
    init() {
        try {
            // Set canvas size
            this.canvas.width = this.options.width;
            this.canvas.height = this.options.height;
            
            // Create gradient background
            this.createGradient();
            
            // Create blobs
            this.createBlobs();
            
            // Create particles
            this.createParticles();
            
            // Start animation
            this.animate();
        } catch (error) {
            console.error('Error initializing GenerationSplash:', error);
            throw error;
        }
    }
    
    createGradient() {
        try {
            this.gradient = this.ctx.createLinearGradient(0, 0, 0, this.options.height);
            this.gradient.addColorStop(0, '#0a001a');   // Dark blue
            this.gradient.addColorStop(0.3, '#1a0033'); // Medium blue
            this.gradient.addColorStop(0.7, '#330066'); // Light blue
            this.gradient.addColorStop(1, '#6600cc');   // Bright blue
        } catch (error) {
            // Fallback to solid color
            this.gradient = '#0a001a';
        }
    }
    
    createBlobs() {
        try {
            for (let i = 0; i < this.options.blobCount; i++) {
                const baseRadius = 20 + Math.random() * 40;
                this.blobs.push({
                    x: Math.random() * this.options.width,
                    y: Math.random() * this.options.height,
                    radius: baseRadius,
                    baseRadius: baseRadius, // Store the original radius
                    speedX: (Math.random() - 0.5) * 1.5,
                    speedY: (Math.random() - 0.5) * 1.5,
                    color: this.getRandomColor(),
                    phase: Math.random() * Math.PI * 2,
                    amplitude: 15 + Math.random() * 25,
                    pulse: Math.random() * Math.PI * 2
                });
            }
        } catch (error) {
            // Create at least one blob as fallback
            this.blobs = [{
                x: this.options.width / 2,
                y: this.options.height / 2,
                radius: 50,
                baseRadius: 50,
                speedX: 0,
                speedY: 0,
                color: '#00ffff',
                phase: 0,
                amplitude: 20,
                pulse: 0
            }];
        }
    }
    
    createParticles() {
        try {
            for (let i = 0; i < 30; i++) {
                this.particles.push({
                    x: Math.random() * this.options.width,
                    y: Math.random() * this.options.height,
                    speedX: (Math.random() - 0.5) * 2,
                    speedY: (Math.random() - 0.5) * 2,
                    size: 1 + Math.random() * 3,
                    color: this.getRandomParticleColor(),
                    life: Math.random() * 100,
                    maxLife: 100 + Math.random() * 100
                });
            }
        } catch (error) {
            console.error('Error creating particles:', error);
        }
    }
    
    getRandomColor() {
        const colors = [
            '#00ffff', // Cyan
            '#00ff80', // Green
            '#ffff00', // Yellow
            '#ff8000', // Orange
            '#ff0080', // Pink
            '#8000ff', // Purple
            '#0080ff', // Blue
            '#80ff00'  // Lime
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    getRandomParticleColor() {
        const colors = [
            '#ffffff', // White
            '#00ffff', // Cyan
            '#00ff80', // Green
            '#ffff00', // Yellow
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    animate() {
        if (!this.isRunning) {
            this.isRunning = true;
        }
        
        try {
            // Clear canvas
            this.ctx.clearRect(0, 0, this.options.width, this.options.height);
            
            // Draw gradient background
            if (this.gradient) {
                this.ctx.fillStyle = this.gradient;
                this.ctx.fillRect(0, 0, this.options.width, this.options.height);
            }
            
            // Update and draw blobs
            this.updateBlobs();
            this.blobs.forEach(blob => {
                try {
                    this.drawBlob(blob);
                } catch (blobError) {
                    console.warn('Error drawing individual blob:', blobError);
                }
            });
            
            // Update and draw particles
            this.updateParticles();
            this.drawParticles();
            
            // Draw title and progress
            this.drawTitle();
            this.drawGenerationProgress();
            
            // Update time
            this.time += this.options.speed;
            
            // Continue animation
            this.animationId = requestAnimationFrame(() => this.animate());
        } catch (error) {
            console.error('Error in GenerationSplash animation:', error);
            // Don't stop the animation completely, just log the error
            // and continue with the next frame
            this.animationId = requestAnimationFrame(() => this.animate());
        }
    }
    
    updateBlobs() {
        this.blobs.forEach((blob, index) => {
            // Update position with sine wave motion
            blob.x += blob.speedX;
            blob.y += blob.speedY + Math.sin(this.time + blob.phase) * blob.amplitude * 0.1;
            
            // Add pulsing effect with bounds checking
            const pulseEffect = Math.sin(this.time * 2 + blob.pulse) * 2;
            blob.radius = Math.max(5, blob.baseRadius + pulseEffect); // Ensure minimum radius of 5
            
            // Bounce off walls
            if (blob.x < blob.radius || blob.x > this.options.width - blob.radius) {
                blob.speedX *= -1;
            }
            if (blob.y < blob.radius || blob.y > this.options.height - blob.radius) {
                blob.speedY *= -1;
            }
            
            // Keep blobs in bounds
            blob.x = Math.max(blob.radius, Math.min(this.options.width - blob.radius, blob.x));
            blob.y = Math.max(blob.radius, Math.min(this.options.height - blob.radius, blob.y));
        });
    }
    
    updateParticles() {
        this.particles.forEach((particle, index) => {
            // Update position
            particle.x += particle.speedX;
            particle.y += particle.speedY;
            
            // Update life
            particle.life++;
            
            // Remove dead particles
            if (particle.life > particle.maxLife) {
                this.particles.splice(index, 1);
                // Add new particle
                this.particles.push({
                    x: Math.random() * this.options.width,
                    y: Math.random() * this.options.height,
                    speedX: (Math.random() - 0.5) * 2,
                    speedY: (Math.random() - 0.5) * 2,
                    size: 1 + Math.random() * 3,
                    color: this.getRandomParticleColor(),
                    life: 0,
                    maxLife: 100 + Math.random() * 100
                });
            }
            
            // Bounce off walls
            if (particle.x < 0 || particle.x > this.options.width) {
                particle.speedX *= -1;
            }
            if (particle.y < 0 || particle.y > this.options.height) {
                particle.speedY *= -1;
            }
        });
    }
    
    drawBlob(blob) {
        try {
            // Ensure radius is positive
            const radius = Math.max(1, blob.radius || 20);
            
            // Create radial gradient for blob
            const gradient = this.ctx.createRadialGradient(
                blob.x, blob.y, 0,
                blob.x, blob.y, radius
            );
            
            gradient.addColorStop(0, blob.color);
            gradient.addColorStop(0.7, blob.color + '80'); // 50% opacity
            gradient.addColorStop(1, blob.color + '20');   // 12% opacity
            
            // Draw main blob
            this.ctx.beginPath();
            this.ctx.arc(blob.x, blob.y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
            
            // Add glow effect
            this.ctx.shadowColor = blob.color;
            this.ctx.shadowBlur = 25;
            this.ctx.beginPath();
            this.ctx.arc(blob.x, blob.y, radius * 0.8, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.shadowBlur = 0;
        } catch (error) {
            console.error('Error drawing blob:', error);
        }
    }
    
    drawParticles() {
        try {
            this.particles.forEach(particle => {
                const alpha = 1 - (particle.life / particle.maxLife);
                this.ctx.beginPath();
                this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                this.ctx.fillStyle = `${particle.color}${Math.floor(alpha * 255).toString(16).padStart(2, '0')}`;
                this.ctx.fill();
            });
        } catch (error) {
            console.error('Error drawing particles:', error);
        }
    }
    
    drawTitle() {
        try {
            const title = "Generating Labels";
            const subtitle = `Processing ${this.options.labelCount} labels...`;
            const template = `Template: ${this.options.templateType}`;
            
            // Title glow effect
            this.ctx.shadowColor = '#00ffff';
            this.ctx.shadowBlur = 20;
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = 'bold 48px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(title, this.options.width / 2, this.options.height / 2 - 60);
            
            // Subtitle with pulsing effect
            const pulse = 0.6 + Math.sin(this.time * 2) * 0.2;
            this.ctx.shadowBlur = 15;
            this.ctx.fillStyle = `rgba(255, 255, 255, ${pulse})`;
            this.ctx.font = '24px Arial';
            this.ctx.fillText(subtitle, this.options.width / 2, this.options.height / 2 - 10);
            
            // Template info
            this.ctx.shadowBlur = 10;
            this.ctx.fillStyle = `rgba(0, 255, 255, ${pulse})`;
            this.ctx.font = '18px Arial';
            this.ctx.fillText(template, this.options.width / 2, this.options.height / 2 + 20);
            
            this.ctx.shadowBlur = 0;
        } catch (error) {
            console.error('Error drawing title:', error);
        }
    }
    
    drawGenerationProgress() {
        try {
            // Draw progress circles
            const centerX = this.options.width / 2;
            const centerY = this.options.height / 2 + 80;
            const radius = 60;
            
            // Background circle
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
            this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            this.ctx.lineWidth = 8;
            this.ctx.stroke();
            
            // Progress arc
            const progress = (this.time * 50) % 100;
            const angle = (progress / 100) * Math.PI * 2;
            
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, radius, -Math.PI / 2, -Math.PI / 2 + angle);
            this.ctx.strokeStyle = '#00ffff';
            this.ctx.lineWidth = 8;
            this.ctx.lineCap = 'round';
            this.ctx.stroke();
            
            // Progress text
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = 'bold 20px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(`${Math.floor(progress)}%`, centerX, centerY + 8);
            
        } catch (error) {
            console.error('Error drawing generation progress:', error);
        }
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
                width: 800,
                height: 600,
                blobCount: 12,
                speed: 0.03,
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