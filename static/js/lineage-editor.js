class LineageEditor {
    constructor() {
        this.modal = null;
        this.saveTimeout = null;
        this.loadingTimeout = null;
        this.isLoading = false;
        this.userRequestedClose = false;
        this.init();
    }

    // Lineage abbreviation mapping (matching Python version)
    static ABBREVIATED_LINEAGE = {
        "SATIVA": "S",
        "INDICA": "I", 
        "HYBRID": "H",
        "HYBRID/SATIVA": "H/S",
        "HYBRID/INDICA": "H/I",
        "CBD": "CBD",
        "CBD_BLEND": "CBD",
        "MIXED": "THC",
        "PARA": "P"
    };

    // Reverse mapping for abbreviation to full value
    static ABBR_TO_LINEAGE = {
        "S": "SATIVA",
        "I": "INDICA", 
        "H": "HYBRID",
        "H/S": "HYBRID/SATIVA",
        "H/I": "HYBRID/INDICA",
        "CBD": "CBD",
        "THC": "MIXED",
        "P": "PARA"
    };

    init() {
        // Wait for both DOM and Bootstrap to be ready
        this.waitForBootstrapAndInitialize();
    }

    waitForBootstrapAndInitialize() {
        // Check if Bootstrap is already available
        if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
            this.initializeWithTimeout();
            return;
        }

        // Wait for Bootstrap to load
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds with 100ms intervals
        
        const checkBootstrap = () => {
            attempts++;
            
            if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
                console.log('Bootstrap detected, initializing lineage editor');
                this.initializeWithTimeout();
                return;
            }
            
            if (attempts >= maxAttempts) {
                console.warn('Bootstrap not detected after 5 seconds, attempting initialization anyway');
                this.initializeWithTimeout();
                return;
            }
            
            setTimeout(checkBootstrap, 100);
        };
        
        // Start checking for Bootstrap
        setTimeout(checkBootstrap, 100);
    }

    initializeWithTimeout() {
        // Add timeout protection for initialization
        const initTimeout = setTimeout(() => {
            console.warn('Lineage editor initialization timed out, forcing initialization');
            this.forceInitialize();
        }, 10000); // 10 second timeout

        try {
            const modalElement = document.getElementById('lineageEditorModal');
            if (!modalElement) {
                console.error('Lineage editor modal element not found');
                clearTimeout(initTimeout);
                return;
            }

            if (typeof bootstrap === 'undefined' || typeof bootstrap.Modal === 'undefined') {
                console.error('Bootstrap.Modal not available');
                clearTimeout(initTimeout);
                this.forceInitialize();
                return;
            }

            this.modal = new bootstrap.Modal(modalElement);
            this.initializeEventListeners();
            clearTimeout(initTimeout);
            console.log('Lineage editor initialized successfully');
        } catch (error) {
            console.error('Error initializing lineage editor:', error);
            clearTimeout(initTimeout);
            this.forceInitialize();
        }
    }

    forceInitialize() {
        // Force initialization even if there are issues
        try {
            const modalElement = document.getElementById('lineageEditorModal');
            if (modalElement && !this.modal) {
                if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
                    this.modal = new bootstrap.Modal(modalElement);
                    this.initializeEventListeners();
                    console.log('Lineage editor force initialized');
                } else {
                    console.error('Bootstrap.Modal still not available for force initialization');
                }
            }
        } catch (error) {
            console.error('Force initialization failed:', error);
        }
    }

    initializeEventListeners() {
        // Save changes button handler
        const saveButton = document.getElementById('saveLineageChanges');
        if (saveButton) {
            saveButton.addEventListener('click', () => this.saveChanges());
        }
        
        // Add modal event listeners to prevent immediate closure
        const modalElement = document.getElementById('lineageEditorModal');
        if (modalElement) {
            // Prevent modal from closing when clicking backdrop during loading
            modalElement.addEventListener('click', (event) => {
                if (event.target === modalElement && this.isLoading) {
                    event.preventDefault();
                    event.stopPropagation();
                    console.log('Modal backdrop clicked during loading, preventing closure');
                }
            });
            
            // Handle modal hidden event
            modalElement.addEventListener('hidden.bs.modal', () => {
                console.log('Lineage editor modal hidden');
                this.isLoading = false;
                if (this.loadingTimeout) {
                    clearTimeout(this.loadingTimeout);
                }
            });
            
            // Handle modal show event
            modalElement.addEventListener('shown.bs.modal', () => {
                console.log('Lineage editor modal shown');
            });
            
            // Handle modal hide event
            modalElement.addEventListener('hide.bs.modal', (event) => {
                console.log('Lineage editor modal hiding');
                // Only prevent closing if it's not a user-requested close and we're still loading
                if (!this.userRequestedClose && this.isLoading) {
                    event.preventDefault();
                    console.log('Prevented automatic modal closure during loading');
                } else {
                    console.log('Allowing lineage modal closure');
                }
            });
            
            // Handle close button clicks
            const closeButton = modalElement.querySelector('.btn-close');
            if (closeButton) {
                closeButton.addEventListener('click', () => {
                    console.log('Close button clicked');
                    this.userRequestedClose = true;
                    this.closeModal();
                });
            }
            
            // Handle cancel button clicks
            const cancelButton = modalElement.querySelector('.btn-secondary');
            if (cancelButton) {
                cancelButton.addEventListener('click', () => {
                    console.log('Cancel button clicked');
                    this.userRequestedClose = true;
                    this.closeModal();
                });
            }
        }
    }

    openEditor(tagName, currentLineage) {
        // Prevent multiple simultaneous openings
        if (this.isLoading) {
            console.log('Lineage editor already loading, ignoring request');
            return;
        }

        this.isLoading = true;
        
        // Add loading timeout protection
        this.loadingTimeout = setTimeout(() => {
            console.warn('Lineage editor loading timed out, forcing cleanup');
            this.isLoading = false;
            this.forceCleanup();
        }, 15000); // 15 second timeout

        try {
            // Ensure modal is initialized
            if (!this.modal) {
                console.log('Modal not initialized, attempting to initialize now');
                this.initializeWithTimeout();
                
                // Wait a bit for initialization
                setTimeout(() => {
                    this.continueOpenEditor(tagName, currentLineage);
                }, 100);
                return;
            }
            
            this.continueOpenEditor(tagName, currentLineage);
        } catch (error) {
            console.error('Error opening lineage editor:', error);
            clearTimeout(this.loadingTimeout);
            this.isLoading = false;
            this.forceCleanup();
        }
    }

    continueOpenEditor(tagName, currentLineage) {
        try {
            const tagNameInput = document.getElementById('editTagName');
            const lineageSelect = document.getElementById('editLineageSelect');
            
            if (tagNameInput && lineageSelect) {
                // Store the currently focused element before opening modal
                const activeElement = document.activeElement;
                if (activeElement && !document.getElementById('lineageEditorModal').contains(activeElement)) {
                    activeElement.setAttribute('data-bs-focus-prev', 'true');
                }
                
                tagNameInput.value = tagName;
                
                // Check if this is a paraphernalia product
                let tag = null;
                let isParaphernalia = false;
                
                try {
                    if (window.TagManager && window.TagManager.state && window.TagManager.state.tags && Array.isArray(window.TagManager.state.tags)) {
                        tag = window.TagManager.state.tags.find(t => t['Product Name*'] === tagName);
                        isParaphernalia = tag && tag['Product Type*'] && tag['Product Type*'].toLowerCase().trim() === 'paraphernalia';
                    } else {
                        console.warn('TagManager not available, assuming not paraphernalia');
                    }
                } catch (error) {
                    console.warn('Error checking TagManager, assuming not paraphernalia:', error);
                }
                
                // Populate dropdown with abbreviated options
                lineageSelect.innerHTML = '';
                const uniqueLineages = ['SATIVA','INDICA','HYBRID','HYBRID/SATIVA','HYBRID/INDICA','CBD','MIXED','PARA'];
                
                uniqueLineages.forEach(lin => {
                    const option = document.createElement('option');
                    option.value = lin;
                    const abbr = LineageEditor.ABBREVIATED_LINEAGE[lin] || lin;
                    option.textContent = abbr;
                    
                    // For paraphernalia products, only allow PARAPHERNALIA lineage
                    if (isParaphernalia && lin !== 'PARA') {
                        option.disabled = true;
                        option.textContent += ' (not available for paraphernalia)';
                    }
                    
                    if ((currentLineage === lin) || (lin === 'CBD' && currentLineage === 'CBD_BLEND')) {
                        option.selected = true;
                    }
                    lineageSelect.appendChild(option);
                });
                
                // Force PARAPHERNALIA lineage for paraphernalia products
                if (isParaphernalia) {
                    lineageSelect.value = 'PARA';
                    lineageSelect.disabled = true;
                    // Add a note about the restriction
                    const note = document.createElement('div');
                    note.className = 'text-muted small mt-2';
                    note.textContent = 'Paraphernalia products must always have PARAPHERNALIA lineage.';
                    lineageSelect.parentNode.appendChild(note);
                }
                
                // Clear loading timeout and show modal
                clearTimeout(this.loadingTimeout);
                this.isLoading = false;
                
                try {
                    if (this.modal) {
                        this.modal.show();
                        console.log('Lineage editor modal shown successfully');
                    } else {
                        console.error('Modal not initialized, attempting force initialization');
                        this.forceInitialize();
                        if (this.modal) {
                            this.modal.show();
                            console.log('Lineage editor modal shown after force initialization');
                        } else {
                            console.error('Modal still not available after force initialization');
                            // Fallback: try to show modal directly
                            const modalElement = document.getElementById('lineageEditorModal');
                            if (modalElement) {
                                const fallbackModal = new bootstrap.Modal(modalElement);
                                fallbackModal.show();
                                console.log('Lineage editor modal shown with fallback initialization');
                            }
                        }
                    }
                } catch (error) {
                    console.error('Error showing modal:', error);
                    // Emergency fallback
                    try {
                        const modalElement = document.getElementById('lineageEditorModal');
                        if (modalElement) {
                            modalElement.classList.add('show');
                            modalElement.style.display = 'block';
                            modalElement.setAttribute('aria-hidden', 'false');
                            console.log('Lineage editor modal shown with emergency fallback');
                        }
                    } catch (fallbackError) {
                        console.error('Emergency fallback also failed:', fallbackError);
                    }
                }
            } else {
                console.error('Lineage editor modal elements not found');
                clearTimeout(this.loadingTimeout);
                this.isLoading = false;
            }
        } catch (error) {
            console.error('Error in continueOpenEditor:', error);
            clearTimeout(this.loadingTimeout);
            this.isLoading = false;
            this.forceCleanup();
        }
    }

    forceCleanup() {
        // Force cleanup of any stuck state
        try {
            if (this.modal) {
                this.modal.hide();
            }
            document.body.style.overflow = '';
            document.body.classList.remove('modal-open');
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => backdrop.remove());
            console.log('Forced cleanup completed');
        } catch (error) {
            console.error('Force cleanup failed:', error);
        }
    }

    closeModal() {
        console.log('Closing lineage editor modal');
        this.isLoading = false;
        if (this.loadingTimeout) {
            clearTimeout(this.loadingTimeout);
        }
        if (this.modal) {
            this.modal.hide();
        } else {
            // Force cleanup if modal is not available
            this.forceCleanup();
        }
        this.userRequestedClose = false;
    }

    async saveChanges() {
        const tagName = document.getElementById('editTagName').value;
        const newLineage = document.getElementById('editLineageSelect').value;
        const saveButton = document.getElementById('saveLineageChanges');
        
        if (!tagName || !newLineage) {
            alert('Please select both tag name and lineage.');
            return;
        }
        
        // Store original button state
        const originalText = saveButton.textContent;
        saveButton.textContent = 'Saving...';
        saveButton.disabled = true;
        
        // Clear any existing timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        this.saveTimeout = setTimeout(() => {
            console.error('Lineage save operation timed out after 30 seconds');
            saveButton.textContent = originalText;
            saveButton.disabled = false;
            alert('The lineage save operation timed out. Please try again. If the problem persists, refresh the page.');
        }, 30000); // 30 second timeout

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 25000); // 25 second abort

            const response = await fetch('/api/update-lineage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tag_name: tagName, "Product Name*": tagName, lineage: newLineage }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            if (this.saveTimeout) {
                clearTimeout(this.saveTimeout);
                this.saveTimeout = null;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update lineage');
            }

            // Update the tag in TagManager state
            if (window.TagManager && window.TagManager.state && window.TagManager.state.tags && Array.isArray(window.TagManager.state.tags)) {
                const tag = window.TagManager.state.tags.find(t => t['Product Name*'] === tagName);
                if (tag) {
                    tag.lineage = newLineage;
                }

                // Update the tag in original tags as well
                if (window.TagManager.state.originalTags && Array.isArray(window.TagManager.state.originalTags)) {
                    const originalTag = window.TagManager.state.originalTags.find(t => t['Product Name*'] === tagName);
                    if (originalTag) {
                        originalTag.lineage = newLineage;
                    }
                }
            } else {
                console.warn('TagManager not available, skipping local updates');
            }

            // Update UI elements
            const tagElements = document.querySelectorAll(`[data-tag-name="${tagName}"]`);
            tagElements.forEach(element => {
                const lineageElement = element.querySelector('.lineage-display');
                if (lineageElement) {
                    const abbr = LineageEditor.ABBREVIATED_LINEAGE[newLineage] || newLineage;
                    lineageElement.textContent = abbr;
                    lineageElement.className = `lineage-display lineage-${newLineage.toLowerCase()}`;
                }
            });

            // Close modal
            if (this.modal) {
                this.modal.hide();
            }
            
            // Refresh available tags from backend to ensure UI shows updated lineage
            if (window.TagManager && window.TagManager.fetchAndUpdateAvailableTags) {
                try {
                    console.log('Refreshing available tags to show updated lineage...');
                    await window.TagManager.fetchAndUpdateAvailableTags();
                    console.log('Available tags refreshed successfully');
                } catch (refreshError) {
                    console.warn('Failed to refresh available tags:', refreshError);
                    // Don't fail the lineage update if refresh fails
                }
            }
            
            // Show success message
            this.showNotification('Lineage updated successfully!', 'success');
            
        } catch (error) {
            console.error('Failed to update lineage:', error);
            if (this.saveTimeout) {
                clearTimeout(this.saveTimeout);
                this.saveTimeout = null;
            }
            if (error.name === 'AbortError') {
                console.error('Request was aborted due to timeout');
                alert('The lineage update request timed out. Please try again. If the problem persists, refresh the page.');
            } else {
                console.error('Failed to update lineage:', error.message);
                alert(`Failed to update lineage: ${error.message}`);
            }
        } finally {
            // Restore button state
            saveButton.textContent = originalText;
            saveButton.disabled = false;
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    static init() {
        return new LineageEditor();
    }
}

// Force compact lineage select styling
(function forceCompactLineageSelect() {
    const style = document.createElement('style');
    style.textContent = `
        .lineage-dropdown-mini {
            font-size: 0.85em;
            padding: 2px 6px;
            min-width: 40px;
            max-width: 60px;
        }
    `;
    document.head.appendChild(style);
})();

class StrainLineageEditor {
    constructor() {
        this.modal = null;
        this.saveTimeout = null;
        this.loadingTimeout = null;
        this.isLoading = false;
        this.userRequestedClose = false;
        this.init();
    }

    // Lineage abbreviation mapping (matching Python version)
    static ABBREVIATED_LINEAGE = {
        "SATIVA": "S",
        "INDICA": "I", 
        "HYBRID": "H",
        "HYBRID/SATIVA": "H/S",
        "HYBRID/INDICA": "H/I",
        "CBD": "CBD",
        "CBD_BLEND": "CBD",
        "MIXED": "THC",
        "PARA": "P"
    };

    // Reverse mapping for abbreviation to full value
    static ABBR_TO_LINEAGE = {
        "S": "SATIVA",
        "I": "INDICA", 
        "H": "HYBRID",
        "H/S": "HYBRID/SATIVA",
        "H/I": "HYBRID/INDICA",
        "CBD": "CBD",
        "THC": "MIXED",
        "P": "PARA"
    };

    init() {
        // Wait for both DOM and Bootstrap to be ready
        this.waitForBootstrapAndInitialize();
    }
    
    waitForBootstrapAndInitialize() {
        // Check if Bootstrap is already available
        if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
            this.initializeWithTimeout();
            return;
        }

        // Wait for Bootstrap to load
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds with 100ms intervals
        
        const checkBootstrap = () => {
            attempts++;
            
            if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
                console.log('Bootstrap detected, initializing strain lineage editor');
                this.initializeWithTimeout();
                return;
            }
            
            if (attempts >= maxAttempts) {
                console.warn('Bootstrap not detected after 5 seconds, attempting initialization anyway');
                this.initializeWithTimeout();
                return;
            }
            
            setTimeout(checkBootstrap, 100);
        };
        
        // Start checking for Bootstrap
        setTimeout(checkBootstrap, 100);
    }
    
    initializeWithTimeout() {
        // Add timeout protection for initialization
        const initTimeout = setTimeout(() => {
            console.warn('Strain lineage editor initialization timed out, forcing initialization');
            this.forceInitialize();
        }, 10000); // 10 second timeout

        try {
            const modalElement = document.getElementById('strainLineageEditorModal');
            if (!modalElement) {
                console.error('Strain lineage editor modal element not found');
                clearTimeout(initTimeout);
                return;
            }

            if (typeof bootstrap === 'undefined' || typeof bootstrap.Modal === 'undefined') {
                console.error('Bootstrap.Modal not available for strain lineage editor');
                clearTimeout(initTimeout);
                this.forceInitialize();
                return;
            }

            this.initializeModal();
            clearTimeout(initTimeout);
            console.log('Strain lineage editor initialized successfully');
        } catch (error) {
            console.error('Error initializing strain lineage editor:', error);
            clearTimeout(initTimeout);
            this.forceInitialize();
        }
    }

    forceInitialize() {
        // Force initialization even if there are issues
        try {
            const modalElement = document.getElementById('strainLineageEditorModal');
            if (modalElement && !this.modal) {
                if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
                    this.modal = new bootstrap.Modal(modalElement);
                    this.initializeEventListeners();
                    console.log('Strain lineage editor force initialized');
                } else {
                    console.error('Bootstrap.Modal still not available for strain lineage editor force initialization');
                }
            }
        } catch (error) {
            console.error('Force initialization failed:', error);
        }
    }
    
    initializeModal() {
        const modalElement = document.getElementById('strainLineageEditorModal');
        if (modalElement) {
            this.modal = new bootstrap.Modal(modalElement);
            this.initializeEventListeners();
            console.log('Strain lineage editor modal initialized');
        } else {
            console.error('Strain lineage editor modal element not found');
        }
    }

    initializeEventListeners() {
        // Save changes button handler
        const saveButton = document.getElementById('saveStrainLineageBtn');
        if (saveButton) {
            saveButton.addEventListener('click', () => this.saveChanges());
        }
        
        // Add modal event listeners to prevent immediate closure
        const modalElement = document.getElementById('strainLineageEditorModal');
        if (modalElement) {
            // Prevent modal from closing when clicking backdrop during loading
            modalElement.addEventListener('click', (event) => {
                if (event.target === modalElement && this.isLoading) {
                    event.preventDefault();
                    event.stopPropagation();
                    console.log('Strain lineage modal backdrop clicked during loading, preventing closure');
                }
            });
            
            // Handle modal hidden event
            modalElement.addEventListener('hidden.bs.modal', () => {
                console.log('Strain lineage editor modal hidden');
                this.isLoading = false;
                if (this.loadingTimeout) {
                    clearTimeout(this.loadingTimeout);
                }
            });
            
            // Handle modal show event
            modalElement.addEventListener('shown.bs.modal', () => {
                console.log('Strain lineage editor modal shown');
            });
            
            // Handle modal hide event
            modalElement.addEventListener('hide.bs.modal', (event) => {
                console.log('Strain lineage editor modal hiding');
                // Only prevent closing if it's not a user-requested close and we're still loading
                if (!this.userRequestedClose && this.isLoading) {
                    event.preventDefault();
                    console.log('Prevented automatic strain lineage modal closure during loading');
                } else {
                    console.log('Allowing strain lineage modal closure');
                }
            });
            
            // Handle close button clicks
            const closeButton = modalElement.querySelector('.btn-close');
            if (closeButton) {
                closeButton.addEventListener('click', () => {
                    console.log('Strain lineage close button clicked');
                    this.userRequestedClose = true;
                    this.closeModal();
                });
            }
            
            // Handle cancel button clicks
            const cancelButton = modalElement.querySelector('.btn-secondary');
            if (cancelButton) {
                cancelButton.addEventListener('click', () => {
                    console.log('Strain lineage cancel button clicked');
                    this.userRequestedClose = true;
                    this.closeModal();
                });
            }
        }
    }
    
    forceCleanup() {
        // Force cleanup of any stuck state
        try {
            if (this.modal) {
                this.modal.hide();
            }
            document.body.style.overflow = '';
            document.body.classList.remove('modal-open');
            const backdrops = document.querySelectorAll('.modal-backdrop');
            backdrops.forEach(backdrop => backdrop.remove());
            console.log('Forced cleanup completed');
        } catch (error) {
            console.error('Force cleanup failed:', error);
        }
    }

    closeModal() {
        console.log('Closing strain lineage editor modal');
        this.isLoading = false;
        if (this.loadingTimeout) {
            clearTimeout(this.loadingTimeout);
        }
        if (this.modal) {
            this.modal.hide();
        } else {
            // Force cleanup if modal is not available
            this.forceCleanup();
        }
        this.userRequestedClose = false;
    }

    async openEditor(strainName, currentLineage) {
        console.log('StrainLineageEditor.openEditor called with:', strainName, currentLineage);
        
        // Prevent multiple simultaneous openings
        if (this.isLoading) {
            console.log('Strain lineage editor already loading, ignoring request');
            return;
        }

        this.isLoading = true;
        
        // Add loading timeout protection
        this.loadingTimeout = setTimeout(() => {
            console.warn('Strain lineage editor loading timed out, forcing cleanup');
            this.isLoading = false;
            this.forceCleanup();
        }, 15000); // 15 second timeout

        try {
            // Ensure modal is initialized
            if (!this.modal) {
                console.log('Modal not initialized, attempting to initialize now');
                this.initializeWithTimeout();
                
                // Wait a bit for initialization
                setTimeout(async () => {
                    try {
                        await this.continueOpenStrainEditor(strainName, currentLineage);
                    } catch (continueError) {
                        console.error('Error in continueOpenStrainEditor:', continueError);
                        clearTimeout(this.loadingTimeout);
                        this.isLoading = false;
                        this.forceCleanup();
                    }
                }, 100);
                return;
            }
            
            await this.continueOpenStrainEditor(strainName, currentLineage);
        } catch (error) {
            console.error('Error opening strain lineage editor:', error);
            clearTimeout(this.loadingTimeout);
            this.isLoading = false;
            this.forceCleanup();
        }
    }

    async continueOpenStrainEditor(strainName, currentLineage) {
        console.log('continueOpenStrainEditor called with:', strainName, currentLineage);
        
        try {
            // Ensure modal is initialized
            if (!this.modal) {
                console.log('Modal still not initialized, attempting to initialize now');
                this.initializeModal();
            }
            
            // Reset user requested close flag
            this.userRequestedClose = false;
            
            const strainNameInput = document.getElementById('strainName');
            const lineageSelect = document.getElementById('strainLineageSelect');
            const affectedProductsList = document.getElementById('affectedProductsList');
            
            if (!strainNameInput || !lineageSelect || !affectedProductsList) {
                console.error('Required modal elements not found:', {
                    strainNameInput: !!strainNameInput,
                    lineageSelect: !!lineageSelect,
                    affectedProductsList: !!affectedProductsList
                });
                throw new Error('Required modal elements not found');
            }
            
            // Store the currently focused element before opening modal
            const activeElement = document.activeElement;
            if (activeElement && !document.getElementById('strainLineageEditorModal').contains(activeElement)) {
                activeElement.setAttribute('data-bs-focus-prev', 'true');
            }
            
            strainNameInput.value = strainName;
            
            // Find all products with this strain in current data
            let affectedProducts = [];
            let paraphernaliaProducts = [];
            
            // Check if TagManager is available and has data
            if (window.TagManager && window.TagManager.state && window.TagManager.state.tags && Array.isArray(window.TagManager.state.tags)) {
                affectedProducts = window.TagManager.state.tags.filter(tag => 
                    tag['Product Strain'] === strainName
                );
                
                // Check if any are paraphernalia products
                paraphernaliaProducts = affectedProducts.filter(tag => 
                    tag['Product Type*'] && tag['Product Type*'].toLowerCase().trim() === 'paraphernalia'
                );
            } else {
                console.warn('TagManager not available or no tags loaded, using fallback data');
                // Fallback: show a message that we can't determine affected products
                affectedProducts = [];
                paraphernaliaProducts = [];
            }
            
            // Get the actual count from the master database
            let masterDatabaseCount = 0;
            try {
                const countResponse = await fetch('/api/get-strain-product-count', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ strain_name: strainName })
                });
                
                if (countResponse.ok) {
                    const countResult = await countResponse.json();
                    masterDatabaseCount = countResult.product_count || 0;
                } else {
                    console.warn('Failed to get master database count, using current data count');
                    masterDatabaseCount = affectedProducts.length;
                }
            } catch (error) {
                console.warn('Error getting master database count:', error);
                masterDatabaseCount = affectedProducts.length;
            }
            
            // Populate dropdown with abbreviated options
            lineageSelect.innerHTML = '';
            const uniqueLineages = ['SATIVA','INDICA','HYBRID','HYBRID/SATIVA','HYBRID/INDICA','CBD','MIXED','PARA'];
            
            uniqueLineages.forEach(lin => {
                const option = document.createElement('option');
                option.value = lin;
                const abbr = StrainLineageEditor.ABBREVIATED_LINEAGE[lin] || lin;
                option.textContent = abbr;
                
                // For paraphernalia products, only allow PARAPHERNALIA lineage
                if (paraphernaliaProducts.length > 0 && lin !== 'PARA') {
                    option.disabled = true;
                    option.textContent += ' (not available for paraphernalia)';
                }
                
                if ((currentLineage === lin) || (lin === 'CBD' && currentLineage === 'CBD_BLEND')) {
                    option.selected = true;
                }
                lineageSelect.appendChild(option);
            });
            
            // Force PARAPHERNALIA lineage for paraphernalia products
            if (paraphernaliaProducts.length > 0) {
                lineageSelect.value = 'PARA';
                lineageSelect.disabled = true;
                // Add a note about the restriction
                const note = document.createElement('div');
                note.className = 'text-muted small mt-2';
                note.textContent = 'Paraphernalia products must always have PARAPHERNALIA lineage.';
                lineageSelect.parentNode.appendChild(note);
            }
            
            // Update modal title to reflect master database operation
            const modalTitle = document.querySelector('#strainLineageEditorModal .modal-title');
            if (modalTitle) {
                modalTitle.textContent = 'Edit Strain Lineage (Master Database)';
            }
            
            // Update the info alert
            const infoAlert = document.querySelector('#strainLineageEditorModal .alert-info');
            if (infoAlert) {
                infoAlert.innerHTML = '<i class="fas fa-info-circle me-2"></i>This will update the lineage for ALL products with this strain in the master database across all data.';
            }
            
            // Populate affected products list with master database info
            affectedProductsList.innerHTML = '';
            affectedProductsList.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    <strong>Master Database Operation:</strong> This change will affect ALL products with strain "${strainName}" across the entire database, not just the current sheet.
                </div>
                <p class="text-muted mb-2">This strain appears in ${masterDatabaseCount} products in the master database.</p>
                <p class="text-muted mb-2">This strain appears in ${affectedProducts.length} products in the current data.</p>
                <p class="text-muted small">Note: The master database count reflects all products across all data files.</p>
            `;
            
            // Clear loading timeout and show modal
            clearTimeout(this.loadingTimeout);
            this.isLoading = false;
            
            console.log('About to show strain lineage editor modal...');
            console.log('Modal instance:', this.modal);
            console.log('Modal element:', document.getElementById('strainLineageEditorModal'));
            
            if (this.modal) {
                try {
                    this.modal.show();
                    console.log('Strain lineage editor modal shown successfully');
                    
                    // Add a check to see if modal is actually visible
                    setTimeout(() => {
                        const modalElement = document.getElementById('strainLineageEditorModal');
                        if (modalElement) {
                            console.log('Modal classes after show:', modalElement.className);
                            console.log('Modal display style:', modalElement.style.display);
                            console.log('Modal visibility:', modalElement.style.visibility);
                        }
                    }, 100);
                } catch (showError) {
                    console.error('Error showing modal:', showError);
                    // Fallback: try to show modal directly
                    const modalElement = document.getElementById('strainLineageEditorModal');
                    if (modalElement) {
                        modalElement.classList.add('show');
                        modalElement.style.display = 'block';
                        console.log('Modal shown with fallback method');
                    }
                }
            } else {
                console.error('Modal instance not available');
                this.forceInitialize();
                if (this.modal) {
                    this.modal.show();
                }
            }
        } catch (error) {
            console.error('Error in continueOpenStrainEditor:', error);
            clearTimeout(this.loadingTimeout);
            this.isLoading = false;
            this.forceCleanup();
        }
    }

    async saveChanges() {
        const strainName = document.getElementById('strainName').value;
        const newLineage = document.getElementById('strainLineageSelect').value;
        const saveButton = document.getElementById('saveStrainLineageBtn');
        let affectedProducts = [];
        
        if (!strainName || !newLineage) {
            alert('Please select both strain name and lineage.');
            return;
        }
        
        // Store original button state
        const originalText = saveButton.textContent;
        saveButton.textContent = 'Saving...';
        saveButton.disabled = true;
        
        // Clear any existing timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        this.saveTimeout = setTimeout(() => {
            console.error('Strain lineage save operation timed out after 45 seconds');
            saveButton.textContent = originalText;
            saveButton.disabled = false;
            alert('The strain lineage save operation timed out. Please try again. If the problem persists, refresh the page.');
        }, 45000); // 45 second timeout

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 40000); // 40 second abort

            const response = await fetch('/api/update-strain-lineage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strain_name: strainName, lineage: newLineage }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            if (this.saveTimeout) {
                clearTimeout(this.saveTimeout);
                this.saveTimeout = null;
            }

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update strain lineage');
            }

            const result = await response.json();
            
            // Update all products with this strain in TagManager state
            if (window.TagManager && window.TagManager.state && window.TagManager.state.tags && Array.isArray(window.TagManager.state.tags)) {
                window.TagManager.state.tags.forEach(tag => {
                    if (tag['Product Strain'] === strainName) {
                        tag.lineage = newLineage;
                    }
                });
                
                if (window.TagManager.state.originalTags && Array.isArray(window.TagManager.state.originalTags)) {
                    window.TagManager.state.originalTags.forEach(tag => {
                        if (tag['Product Strain'] === strainName) {
                            tag.lineage = newLineage;
                        }
                    });
                }

                // Update UI elements for all affected products
                let affectedProducts = window.TagManager.state.tags.filter(tag => 
                    tag['Product Strain'] === strainName
                );
            } else {
                console.warn('TagManager not available, skipping local updates');
                // affectedProducts is already initialized as empty array
            }
            
            affectedProducts.forEach(tag => {
                const tagElements = document.querySelectorAll(`[data-tag-name="${tag['Product Name*']}"]`);
                tagElements.forEach(element => {
                    const lineageElement = element.querySelector('.lineage-display');
                    if (lineageElement) {
                        const abbr = StrainLineageEditor.ABBREVIATED_LINEAGE[newLineage] || newLineage;
                        lineageElement.textContent = abbr;
                        lineageElement.className = `lineage-display lineage-${newLineage.toLowerCase()}`;
                    }
                });
            });

            // Close modal
            if (this.modal) {
                this.modal.hide();
            }
            
            // Refresh available tags from backend to ensure UI shows updated lineage
            if (window.TagManager && window.TagManager.fetchAndUpdateAvailableTags) {
                try {
                    console.log('Refreshing available tags to show updated strain lineage...');
                    await window.TagManager.fetchAndUpdateAvailableTags();
                    console.log('Available tags refreshed successfully');
                } catch (refreshError) {
                    console.warn('Failed to refresh available tags:', refreshError);
                    // Don't fail the lineage update if refresh fails
                }
            }
            
            // Show success message
            const affectedCount = result.affected_product_count || affectedProducts.length;
            this.showNotification(`Strain lineage updated successfully! Affected ${affectedCount} products.`, 'success');
            
        } catch (error) {
            console.error('Failed to update strain lineage:', error);
            if (this.saveTimeout) {
                clearTimeout(this.saveTimeout);
                this.saveTimeout = null;
            }
            if (error.name === 'AbortError') {
                console.error('Request was aborted due to timeout');
                alert('The strain lineage update request timed out. Please try again. If the problem persists, refresh the page.');
            } else {
                console.error('Failed to update strain lineage:', error.message);
                alert(`Failed to update strain lineage: ${error.message}`);
            }
        } finally {
            // Restore button state
            saveButton.textContent = originalText;
            saveButton.disabled = false;
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    static init() {
        return new StrainLineageEditor();
    }
}

// Global emergency cleanup function for stuck modals
window.emergencyLineageModalCleanup = function() {
    console.log('Emergency lineage modal cleanup initiated');
    
    // Force close any open strain lineage editor modal
    const modalElement = document.getElementById('strainLineageEditorModal');
    if (modalElement) {
        modalElement.classList.remove('show');
        modalElement.style.display = 'none';
        modalElement.setAttribute('aria-hidden', 'true');
    }
    
    // Force close any open lineage editor modal
    const lineageModalElement = document.getElementById('lineageEditorModal');
    if (lineageModalElement) {
        lineageModalElement.classList.remove('show');
        lineageModalElement.style.display = 'none';
        lineageModalElement.setAttribute('aria-hidden', 'true');
    }
    
    // Restore body scroll
    if (typeof restoreBodyScroll === 'function') {
        restoreBodyScroll();
    } else {
        document.body.style.overflow = '';
        document.body.classList.remove('modal-open');
        document.body.style.paddingRight = '';
        document.body.style.pointerEvents = '';
    }
    
    // Remove any modal backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => backdrop.remove());
    
    console.log('Emergency lineage modal cleanup completed');
};

// Debug function to check lineage editor status
window.debugLineageEditor = function() {
    console.log('=== Lineage Editor Debug Info ===');
    
    // Check if Bootstrap is available
    console.log('Bootstrap available:', typeof bootstrap !== 'undefined');
    console.log('Bootstrap.Modal available:', typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined');
    
    // Check modal elements
    const lineageModal = document.getElementById('lineageEditorModal');
    const strainModal = document.getElementById('strainLineageEditorModal');
    console.log('Lineage modal element:', lineageModal);
    console.log('Strain modal element:', strainModal);
    
    // Check modal instances
    console.log('Lineage editor instance:', window.lineageEditor);
    console.log('Strain lineage editor instance:', window.strainLineageEditor);
    
    // Check modal visibility
    if (lineageModal) {
        console.log('Lineage modal classes:', lineageModal.className);
        console.log('Lineage modal display:', lineageModal.style.display);
        console.log('Lineage modal z-index:', lineageModal.style.zIndex);
    }
    
    if (strainModal) {
        console.log('Strain modal classes:', strainModal.className);
        console.log('Strain modal display:', strainModal.style.display);
        console.log('Strain modal z-index:', strainModal.style.zIndex);
    }
    
    // Check body state
    console.log('Body modal-open class:', document.body.classList.contains('modal-open'));
    console.log('Body overflow:', document.body.style.overflow);
    
    // Check for modal backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    console.log('Modal backdrops found:', backdrops.length);
    backdrops.forEach((backdrop, index) => {
        console.log(`Backdrop ${index}:`, backdrop.className, backdrop.style.zIndex);
    });
    
    console.log('=== End Debug Info ===');
};

// Initialize both editors with startup delay to avoid conflicts with database operations
document.addEventListener('DOMContentLoaded', () => {
    // Add a delay to allow database operations to complete
    setTimeout(() => {
        try {
            console.log('Initializing lineage editors...');
            
            // Check if Bootstrap is available first
            if (typeof bootstrap === 'undefined' || typeof bootstrap.Modal === 'undefined') {
                console.warn('Bootstrap not available, waiting for it to load...');
                // Wait for Bootstrap to load
                let bootstrapAttempts = 0;
                const maxBootstrapAttempts = 100; // 10 seconds
                
                const waitForBootstrap = () => {
                    bootstrapAttempts++;
                    if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
                        console.log('Bootstrap detected, proceeding with initialization');
                        initializeLineageEditors();
                        return;
                    }
                    
                    if (bootstrapAttempts >= maxBootstrapAttempts) {
                        console.error('Bootstrap not available after 10 seconds, attempting initialization anyway');
                        initializeLineageEditors();
                        return;
                    }
                    
                    setTimeout(waitForBootstrap, 100);
                };
                
                waitForBootstrap();
            } else {
                initializeLineageEditors();
            }
        } catch (error) {
            console.error('Error in lineage editors initialization:', error);
        }
    }, 2000); // 2 second startup delay
    
    function initializeLineageEditors() {
        try {
            // Initialize LineageEditor
            try {
                window.lineageEditor = LineageEditor.init();
                console.log('LineageEditor initialized successfully');
            } catch (lineageError) {
                console.error('Error initializing LineageEditor:', lineageError);
                window.lineageEditor = null;
            }
            
            // Initialize StrainLineageEditor
            try {
                window.strainLineageEditor = StrainLineageEditor.init();
                console.log('StrainLineageEditor initialized successfully');
            } catch (strainError) {
                console.error('Error initializing StrainLineageEditor:', strainError);
                window.strainLineageEditor = null;
            }
            
            console.log('Lineage editors initialization completed');
            
            // Add a final check to ensure modals are properly set up
            setTimeout(() => {
                const lineageModal = document.getElementById('lineageEditorModal');
                const strainModal = document.getElementById('strainLineageEditorModal');
                
                if (lineageModal && !window.lineageEditor) {
                    console.warn('Lineage modal exists but editor not initialized, attempting recovery');
                    try {
                        window.lineageEditor = LineageEditor.init();
                    } catch (error) {
                        console.error('Recovery failed:', error);
                    }
                }
                
                if (strainModal && !window.strainLineageEditor) {
                    console.warn('Strain modal exists but editor not initialized, attempting recovery');
                    try {
                        window.strainLineageEditor = StrainLineageEditor.init();
                    } catch (error) {
                        console.error('Recovery failed:', error);
                    }
                }
            }, 1000);
            
        } catch (error) {
            console.error('Error in initializeLineageEditors:', error);
            // Retry initialization after another delay
            setTimeout(() => {
                try {
                    console.log('Retrying lineage editors initialization...');
                    
                    // Retry LineageEditor
                    if (!window.lineageEditor) {
                        try {
                            window.lineageEditor = LineageEditor.init();
                            console.log('LineageEditor initialized on retry');
                        } catch (lineageError) {
                            console.error('Error initializing LineageEditor on retry:', lineageError);
                        }
                    }
                    
                    // Retry StrainLineageEditor
                    if (!window.strainLineageEditor) {
                        try {
                            window.strainLineageEditor = StrainLineageEditor.init();
                            console.log('StrainLineageEditor initialized on retry');
                        } catch (strainError) {
                            console.error('Error initializing StrainLineageEditor on retry:', strainError);
                        }
                    }
                    
                    console.log('Lineage editors retry initialization completed');
                } catch (retryError) {
                    console.error('Failed to initialize lineage editors on retry:', retryError);
                }
            }, 5000); // 5 second retry delay
        }
    }
});

// Add a simple fallback for immediate testing
window.testLineageEditor = function() {
    console.log('Testing lineage editor fallback...');
    
    // Check if Bootstrap is available
    if (typeof bootstrap === 'undefined' || typeof bootstrap.Modal === 'undefined') {
        console.error('Bootstrap not available for lineage editor test');
        alert('Bootstrap not loaded. Please refresh the page.');
        return;
    }
    
    // Check if modal elements exist
    const lineageModal = document.getElementById('lineageEditorModal');
    const strainModal = document.getElementById('strainLineageEditorModal');
    
    if (!lineageModal) {
        console.error('Lineage editor modal not found');
        alert('Lineage editor modal not found. Please check the page.');
        return;
    }
    
    if (!strainModal) {
        console.error('Strain lineage editor modal not found');
        alert('Strain lineage editor modal not found. Please check the page.');
        return;
    }
    
    console.log('Lineage editor modals found, attempting to show...');
    
    // Try to show the lineage editor modal
    try {
        const modal = new bootstrap.Modal(lineageModal);
        modal.show();
        console.log('Lineage editor modal shown successfully');
    } catch (error) {
        console.error('Error showing lineage editor modal:', error);
        alert('Error showing lineage editor modal: ' + error.message);
    }
};

// Quick fix function for lineage editor issues
window.fixLineageEditor = function() {
    console.log('Attempting to fix lineage editor issues...');
    
    // First, run emergency cleanup
    window.emergencyLineageModalCleanup();
    
    // Wait a moment, then reinitialize
    setTimeout(() => {
        try {
            // Reinitialize lineage editors
            if (typeof LineageEditor !== 'undefined') {
                window.lineageEditor = LineageEditor.init();
                console.log('LineageEditor reinitialized');
            }
            
            if (typeof StrainLineageEditor !== 'undefined') {
                window.strainLineageEditor = StrainLineageEditor.init();
                console.log('StrainLineageEditor reinitialized');
            }
            
            console.log('Lineage editor fix completed');
        } catch (error) {
            console.error('Error during lineage editor fix:', error);
        }
    }, 500);
};

// Test strain lineage editor specifically
window.testStrainLineageEditor = function() {
    console.log('Testing strain lineage editor...');
    
    if (window.strainLineageEditor) {
        console.log('Strain lineage editor instance found, testing with sample data...');
        window.strainLineageEditor.openEditor('Test Strain', 'HYBRID');
    } else {
        console.error('Strain lineage editor not initialized');
        // Try to initialize it
        if (typeof StrainLineageEditor !== 'undefined') {
            console.log('Attempting to initialize strain lineage editor...');
            window.strainLineageEditor = StrainLineageEditor.init();
            setTimeout(() => {
                if (window.strainLineageEditor) {
                    window.strainLineageEditor.openEditor('Test Strain', 'HYBRID');
                } else {
                    console.error('Failed to initialize strain lineage editor');
                }
            }, 1000);
        } else {
            console.error('StrainLineageEditor class not found');
        }
    }
};