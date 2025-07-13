/**
 * Comprehensive Scrolling Fix for AGT Designer
 * Handles all scrolling issues and conflicts
 */

class ScrollFix {
    constructor() {
        this.initialized = false;
        this.scrollContainers = [];
        this.init();
    }

    init() {
        if (this.initialized) return;
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupScrollFix());
        } else {
            this.setupScrollFix();
        }
        
        this.initialized = true;
    }

    setupScrollFix() {
        this.fixTagListScrolling();
        this.fixStickyFilterBar();
        this.fixBodyScrolling();
        this.fixMobileScrolling();
        this.setupScrollListeners();
    }

    fixTagListScrolling() {
        // Fix tag list container scrolling
        const tagContainers = document.querySelectorAll('.tag-list-container');
        
        tagContainers.forEach(container => {
            // Ensure proper overflow settings
            container.style.overflowY = 'auto';
            container.style.overflowX = 'hidden';
            container.style.webkitOverflowScrolling = 'touch';
            
            // Add to our tracking list
            this.scrollContainers.push(container);
            
            // Fix any existing scroll issues
            this.fixContainerScroll(container);
        });
    }

    fixContainerScroll(container) {
        // Ensure scroll position is valid
        const maxScroll = container.scrollHeight - container.clientHeight;
        if (container.scrollTop > maxScroll) {
            container.scrollTop = maxScroll;
        }
        if (container.scrollTop < 0) {
            container.scrollTop = 0;
        }
    }

    fixStickyFilterBar() {
        const stickyFilterBar = document.querySelector('.sticky-filter-bar');
        if (!stickyFilterBar) return;

        // Use ResizeObserver to handle dynamic content changes
        const resizeObserver = new ResizeObserver(() => {
            this.updateStickyFilterBar();
        });

        // Observe the card header for changes
        const cardHeader = document.querySelector('.card-header');
        if (cardHeader) {
            resizeObserver.observe(cardHeader);
        }

        // Initial update
        this.updateStickyFilterBar();
    }

    updateStickyFilterBar() {
        const stickyFilterBar = document.querySelector('.sticky-filter-bar');
        const cardHeader = document.querySelector('.card-header');
        
        if (!stickyFilterBar || !cardHeader) return;

        const headerRect = cardHeader.getBoundingClientRect();
        const shouldBeSticky = headerRect.bottom <= 0;
        
        if (shouldBeSticky) {
            stickyFilterBar.classList.add('is-sticky');
        } else {
            stickyFilterBar.classList.remove('is-sticky');
        }
    }

    fixBodyScrolling() {
        // Ensure body scrolling is smooth and doesn't conflict
        document.body.style.scrollBehavior = 'smooth';
        document.documentElement.style.scrollBehavior = 'smooth';
        
        // Prevent horizontal scrolling
        document.body.style.overflowX = 'hidden';
        document.documentElement.style.overflowX = 'hidden';
    }

    fixMobileScrolling() {
        // Mobile-specific scrolling fixes
        if (window.innerWidth <= 768) {
            // Add touch-action for better mobile scrolling
            this.scrollContainers.forEach(container => {
                container.style.touchAction = 'pan-y';
            });
            
            // Fix iOS momentum scrolling
            document.body.style.webkitOverflowScrolling = 'touch';
        }
    }

    setupScrollListeners() {
        // Monitor scroll containers for issues
        this.scrollContainers.forEach(container => {
            container.addEventListener('scroll', (e) => {
                this.handleContainerScroll(e, container);
            }, { passive: true });
        });

        // Global scroll listener for sticky filter bar
        window.addEventListener('scroll', () => {
            this.updateStickyFilterBar();
        }, { passive: true });

        // Handle window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        }, { passive: true });
    }

    handleContainerScroll(e, container) {
        // Fix any scroll position issues
        this.fixContainerScroll(container);
        
        // Prevent scroll chaining on mobile
        if (window.innerWidth <= 768) {
            const { scrollTop, scrollHeight, clientHeight } = container;
            
            if ((scrollTop <= 0 && e.deltaY < 0) || 
                (scrollTop + clientHeight >= scrollHeight && e.deltaY > 0)) {
                e.preventDefault();
            }
        }
    }

    handleResize() {
        // Recalculate scroll positions after resize
        this.scrollContainers.forEach(container => {
            this.fixContainerScroll(container);
        });
        
        this.updateStickyFilterBar();
        this.fixMobileScrolling();
    }

    // Public method to refresh scroll fix
    refresh() {
        this.scrollContainers = [];
        this.fixTagListScrolling();
        this.fixStickyFilterBar();
        this.fixMobileScrolling();
    }
}

// Initialize scroll fix when DOM is ready
let scrollFix;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        scrollFix = new ScrollFix();
    });
} else {
    scrollFix = new ScrollFix();
}

// Make it available globally for debugging
window.ScrollFix = ScrollFix;
window.scrollFix = scrollFix; 