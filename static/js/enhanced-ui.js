// Enhanced UI JavaScript
// This file contains all the enhanced UI functionality

// Enhanced file upload with drag and drop
const fileDropZone = document.getElementById('fileDropZone');
const fileInput = document.getElementById('fileInput');
const currentFileInfo = document.getElementById('currentFileInfo');
const currentFile = document.getElementById('currentFile');

// Initialize drag and drop functionality
function initializeDragAndDrop() {
  if (!fileDropZone) return;

  // Drag and drop handlers
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, preventDefaults, false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, highlight, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, unhighlight, false);
  });

  fileDropZone.addEventListener('drop', handleDrop, false);
  fileDropZone.addEventListener('click', () => fileInput.click());
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function highlight(e) {
  fileDropZone.classList.add('dragover');
  // Add visual feedback
  const title = fileDropZone.querySelector('.drag-drop-title');
  if (title) {
    title.textContent = 'Drop your file here!';
  }
}

function unhighlight(e) {
  fileDropZone.classList.remove('dragover');
  // Reset visual feedback
  const title = fileDropZone.querySelector('.drag-drop-title');
  if (title) {
    title.textContent = 'Drop your Excel file here';
  }
}

function handleDrop(e) {
  const dt = e.dataTransfer;
  const files = dt.files;
  handleFiles(files);
}

// File input change handler
if (fileInput) {
  fileInput.addEventListener('change', function() {
    handleFiles(this.files);
  });
}

// Clear file function
function clearFile() {
  if (fileInput) {
    fileInput.value = '';
  }
  if (currentFileInfo) {
    currentFileInfo.style.display = 'none';
  }
  if (fileDropZone) {
    fileDropZone.classList.remove('file-uploaded', 'file-error', 'file-loading');
  }
  // Reset the drop zone to initial state
  const title = fileDropZone?.querySelector('.drag-drop-title');
  if (title) {
    title.textContent = 'Drop your Excel file here';
  }
}

async function handleFiles(files) {
  if (files.length > 0) {
    const file = files[0];
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      showFileError('Please select an Excel (.xlsx) file');
      return;
    }

    // Validate file size (16MB limit)
    if (file.size > 16 * 1024 * 1024) {
      showFileError('File size must be less than 16MB');
      return;
    }

    // Show file info
    showFileInfo(file.name);
    
    // Set loading state
    if (fileDropZone) {
      fileDropZone.classList.add('file-loading');
    }

    // Handle file upload
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      if (window.TagManager) {
        TagManager.setLoading(true);
      }
      
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Success state
        if (fileDropZone) {
          fileDropZone.classList.remove('file-loading');
          fileDropZone.classList.add('file-uploaded');
        }
        
        if (window.TagManager) {
          TagManager.debouncedUpdateAvailableTags(data.tags);
          TagManager.updateFilters(data.filters);
        }
        
        // Show success feedback
        showToast('success', `File "${file.name}" uploaded successfully!`);
        
        // Reset to normal state after 2 seconds
        setTimeout(() => {
          if (fileDropZone) {
            fileDropZone.classList.remove('file-uploaded');
          }
        }, 2000);
        
      } else {
        showFileError(data.error || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      showFileError('Upload failed. Please try again.');
    } finally {
      if (window.TagManager) {
        TagManager.setLoading(false);
      }
    }
  }
}

function showFileInfo(fileName) {
  if (currentFile) {
    currentFile.textContent = fileName;
  }
  if (currentFileInfo) {
    currentFileInfo.style.display = 'flex';
  }
}

function showFileError(message) {
  if (fileDropZone) {
    fileDropZone.classList.remove('file-loading');
    fileDropZone.classList.add('file-error');
  }
  
  showToast('error', message);
  
  // Reset error state after 3 seconds
  setTimeout(() => {
    if (fileDropZone) {
      fileDropZone.classList.remove('file-error');
    }
  }, 3000);
}

function showToast(type, message) {
  if (window.Toast) {
    Toast.show(type, message);
  } else {
    // Fallback toast
    console.log(`${type.toUpperCase()}: ${message}`);
  }
}

// Initialize drag and drop when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  initializeDragAndDrop();
});

// Add smooth scrolling
document.querySelectorAll('.tag-list-container').forEach(container => {
  container.addEventListener('wheel', (e) => {
    e.preventDefault();
    container.scrollTop += e.deltaY * 0.5;
  });
});

// Add keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey) {
    switch(e.key) {
      case 'g':
        e.preventDefault();
        document.getElementById('generateBtn').click();
        break;
      case 'z':
        e.preventDefault();
        document.getElementById('undo-move-btn').click();
        break;
      case 'h':
        e.preventDefault();
        document.getElementById('help-btn').click();
        break;
    }
  }
});

// Initialize tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
tooltipTriggerList.map(function (tooltipTriggerEl) {
  return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Page load animations
window.addEventListener('DOMContentLoaded', function() {
  window.scrollTo(0, 0);
  
  // Add staggered fade-in animation
  document.querySelectorAll('.fade-in').forEach((el, index) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    }, index * 100);
  });
});

// Enhanced button click feedback
document.querySelectorAll('.btn').forEach(button => {
  button.addEventListener('click', function(e) {
    // Create ripple effect
    const ripple = document.createElement('span');
    const rect = this.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.classList.add('ripple');
    
    this.appendChild(ripple);
    
    setTimeout(() => {
      ripple.remove();
    }, 600);
  });
});

// Enhanced modal animations
const modals = document.querySelectorAll('.modal');
modals.forEach(modal => {
  modal.addEventListener('show.bs.modal', function() {
    this.style.opacity = '0';
    setTimeout(() => {
      this.style.transition = 'opacity 0.3s ease';
      this.style.opacity = '1';
    }, 10);
  });
});

// Add hover sound effects (optional - requires adding audio files)
function addHoverSound() {
  const hoverSound = new Audio('/static/sounds/hover.mp3');
  hoverSound.volume = 0.1;
  
  document.querySelectorAll('.btn, .tag-item').forEach(element => {
    element.addEventListener('mouseenter', () => {
      hoverSound.currentTime = 0;
      hoverSound.play().catch(() => {});
    });
  });
}

// Particle effect on button clicks (optional)
function createParticles(x, y) {
  const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c'];
  
  for (let i = 0; i < 10; i++) {
    const particle = document.createElement('div');
    particle.style.position = 'fixed';
    particle.style.left = x + 'px';
    particle.style.top = y + 'px';
    particle.style.width = '5px';
    particle.style.height = '5px';
    particle.style.background = colors[Math.floor(Math.random() * colors.length)];
    particle.style.borderRadius = '50%';
    particle.style.pointerEvents = 'none';
    particle.style.zIndex = '9999';
    
    const angle = (Math.PI * 2 * i) / 10;
    const velocity = 2 + Math.random() * 2;
    const vx = Math.cos(angle) * velocity;
    const vy = Math.sin(angle) * velocity;
    
    document.body.appendChild(particle);
    
    let opacity = 1;
    const animate = () => {
      particle.style.left = (parseFloat(particle.style.left) + vx) + 'px';
      particle.style.top = (parseFloat(particle.style.top) + vy) + 'px';
      opacity -= 0.02;
      particle.style.opacity = opacity;
      
      if (opacity > 0) {
        requestAnimationFrame(animate);
      } else {
        particle.remove();
      }
    };
    
    requestAnimationFrame(animate);
  }
}

// Add particle effect to important buttons
document.getElementById('generateBtn')?.addEventListener('click', function(e) {
  createParticles(e.clientX, e.clientY);
});

// Auto-save functionality indicator
let autoSaveTimer;
function showAutoSave() {
  const indicator = document.createElement('div');
  indicator.className = 'auto-save-indicator';
  indicator.textContent = 'Auto-saved';
  indicator.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 20px;
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    padding: 10px 20px;
    border-radius: 8px;
    color: #4facfe;
    font-weight: 600;
    opacity: 0;
    transition: opacity 0.3s ease;
    z-index: 1000;
  `;
  
  document.body.appendChild(indicator);
  
  setTimeout(() => {
    indicator.style.opacity = '1';
  }, 10);
  
  setTimeout(() => {
    indicator.style.opacity = '0';
    setTimeout(() => {
      indicator.remove();
    }, 300);
  }, 2000);
}

// Dynamic background based on time of day (optional)
function setDynamicBackground() {
  const hour = new Date().getHours();
  const body = document.body;
  
  if (hour >= 6 && hour < 12) {
    // Morning
    body.style.setProperty('--bg-gradient', 'linear-gradient(-45deg, #0a0a0a, #1a0033, #330066, #4d0080)');
  } else if (hour >= 12 && hour < 18) {
    // Afternoon
    body.style.setProperty('--bg-gradient', 'linear-gradient(-45deg, #0a0a0a, #1a0033, #4d0033, #660033)');
  } else {
    // Evening/Night
    body.style.setProperty('--bg-gradient', 'linear-gradient(-45deg, #0a0a0a, #0a0a1a, #1a0a2a, #2a0a3a)');
  }
}

// Initialize enhanced features
document.addEventListener('DOMContentLoaded', function() {
  // Optional: Enable hover sounds
  // addHoverSound();
  
  // Optional: Set dynamic background
  // setDynamicBackground();
  
  // Show welcome animation
  const welcome = document.createElement('div');
  welcome.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 2rem;
    font-weight: bold;
    background: var(--primary-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    opacity: 0;
    animation: welcomeFade 2s ease-out;
    pointer-events: none;
    z-index: 10000;
  `;
  welcome.textContent = 'Welcome to AGT Label Maker';
  
  const style = document.createElement('style');
  style.textContent = `
    @keyframes welcomeFade {
      0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
      50% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
      100% { opacity: 0; transform: translate(-50%, -50%) scale(1.1); }
    }
  `;
  document.head.appendChild(style);
  document.body.appendChild(welcome);
  
  setTimeout(() => {
    welcome.remove();
  }, 2000);
});

