// Mobile JavaScript for AGT Designer
class MobileAGTDesigner {
    constructor() {
        this.currentFile = null;
        this.availableTags = [];
        this.selectedTags = [];
        this.filters = {
            vendor: 'All',
            brand: 'All',
            productType: 'All',
            lineage: 'All',
            weight: 'All'
        };
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadInitialData();
        this.updateSelectedCount();
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.target.closest('.nav-tab').dataset.tab);
            });
        });

        // File upload
        document.getElementById('mobileFileInput').addEventListener('change', (e) => {
            this.handleFileUpload(e.target.files[0]);
        });

        // Filters
        document.getElementById('mobileVendorFilter').addEventListener('change', (e) => {
            this.filters.vendor = e.target.value;
            this.applyFilters();
        });

        document.getElementById('mobileBrandFilter').addEventListener('change', (e) => {
            this.filters.brand = e.target.value;
            this.applyFilters();
        });

        document.getElementById('mobileProductTypeFilter').addEventListener('change', (e) => {
            this.filters.productType = e.target.value;
            this.applyFilters();
        });

        document.getElementById('mobileLineageFilter').addEventListener('change', (e) => {
            this.filters.lineage = e.target.value;
            this.applyFilters();
        });

        document.getElementById('mobileWeightFilter').addEventListener('change', (e) => {
            this.filters.weight = e.target.value;
            this.applyFilters();
        });

        // Search
        document.getElementById('mobileSearchInput').addEventListener('input', (e) => {
            this.applySearch(e.target.value);
        });

        // Select all
        document.getElementById('mobileSelectAllAvailable').addEventListener('change', (e) => {
            this.selectAllAvailable(e.target.checked);
        });

        // Generate button
        document.getElementById('mobileGenerateBtn').addEventListener('click', () => {
            this.generateLabels();
        });

        // Settings
        document.getElementById('mobileAutoLoad').addEventListener('change', (e) => {
            this.saveSetting('autoLoad', e.target.checked);
        });

        document.getElementById('mobileShowColors').addEventListener('change', (e) => {
            this.saveSetting('showColors', e.target.checked);
            this.renderTags();
        });

        document.getElementById('mobileCompactView').addEventListener('change', (e) => {
            this.saveSetting('compactView', e.target.checked);
            this.renderTags();
        });
    }

    switchTab(tabName) {
        // Update active tab
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // Update active content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // Load data for specific tabs
        if (tabName === 'tags') {
            this.loadTags();
        } else if (tabName === 'settings') {
            this.loadSettings();
        }
    }

    async loadInitialData() {
        try {
            this.showLoading('Loading initial data...');
            
            // Load settings
            this.loadSettings();
            
            // Try to load default file if auto-load is enabled
            if (this.getSetting('autoLoad', true)) {
                await this.loadDefaultFile();
            }
            
            this.hideLoading();
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.hideLoading();
            this.showToast('Error loading initial data', 'error');
        }
    }

    async loadDefaultFile() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.current_file) {
                this.currentFile = data.current_file;
                this.updateFileInfo();
                await this.loadTags();
            }
        } catch (error) {
            console.error('Error loading default file:', error);
        }
    }

    async handleFileUpload(file) {
        if (!file) return;

        try {
            this.showLoading(`Uploading ${file.name}...`);
            
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                this.currentFile = file.name;
                this.updateFileInfo();
                await this.loadTags();
                this.showToast('File uploaded successfully!', 'success');
            } else {
                throw new Error('Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast('Upload failed. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    updateFileInfo() {
        const fileInfo = document.getElementById('mobileFileInfo');
        const fileName = document.getElementById('mobileFileName');
        
        if (this.currentFile) {
            fileName.textContent = this.currentFile;
            fileInfo.style.display = 'flex';
        } else {
            fileInfo.style.display = 'none';
        }
    }

    async loadTags() {
        if (!this.currentFile) {
            this.availableTags = [];
            this.selectedTags = [];
            this.renderTags();
            return;
        }

        try {
            this.showLoading('Loading tags...');
            
            // Load available tags
            const availableResponse = await fetch('/api/available-tags');
            const availableData = await availableResponse.json();
            this.availableTags = availableData.tags || [];

            // Load selected tags
            const selectedResponse = await fetch('/api/selected-tags');
            const selectedData = await selectedResponse.json();
            this.selectedTags = selectedData.tags || [];

            // Load filter options
            await this.loadFilterOptions();

            this.renderTags();
            this.updateSelectedCount();
            
        } catch (error) {
            console.error('Error loading tags:', error);
            this.showToast('Error loading tags', 'error');
        } finally {
            this.hideLoading();
        }
    }

    async loadFilterOptions() {
        try {
            const response = await fetch('/api/filter-options');
            const data = await response.json();

            this.populateFilter('mobileVendorFilter', data.vendors || []);
            this.populateFilter('mobileBrandFilter', data.brands || []);
            this.populateFilter('mobileProductTypeFilter', data.product_types || []);
            this.populateFilter('mobileLineageFilter', data.lineages || []);
            this.populateFilter('mobileWeightFilter', data.weights || []);
        } catch (error) {
            console.error('Error loading filter options:', error);
        }
    }

    populateFilter(filterId, options) {
        const select = document.getElementById(filterId);
        const currentValue = select.value;
        
        // Keep "All" option
        select.innerHTML = '<option value="All">All</option>';
        
        // Add new options
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            select.appendChild(optionElement);
        });
        
        // Restore previous selection if still valid
        if (options.includes(currentValue)) {
            select.value = currentValue;
        }
    }

    renderTags() {
        this.renderAvailableTags();
        this.renderSelectedTags();
    }

    renderAvailableTags() {
        const container = document.getElementById('mobileAvailableTags');
        container.innerHTML = '';

        this.availableTags.forEach(tag => {
            const tagElement = this.createTagElement(tag, 'available');
            container.appendChild(tagElement);
        });
    }

    renderSelectedTags() {
        const container = document.getElementById('mobileSelectedTags');
        container.innerHTML = '';

        this.selectedTags.forEach(tag => {
            const tagElement = this.createTagElement(tag, 'selected');
            container.appendChild(tagElement);
        });
    }

    createTagElement(tag, type) {
        const div = document.createElement('div');
        div.className = `mobile-tag-item ${type}`;
        div.dataset.tagId = tag.id || tag.name;

        const showColors = this.getSetting('showColors', true);
        const compactView = this.getSetting('compactView', false);

        const lineageClass = showColors && tag.lineage ? `lineage-${tag.lineage.toLowerCase()}` : '';
        const lineageBadge = showColors && tag.lineage ? 
            `<span class="mobile-lineage-badge ${lineageClass}">${tag.lineage}</span>` : '';

        const details = compactView ? 
            `${tag.vendor || ''} ${tag.brand || ''} ${tag.weight || ''}`.trim() :
            `${tag.vendor || ''} • ${tag.brand || ''} • ${tag.weight || ''}`.trim();

        div.innerHTML = `
            <input type="checkbox" class="mobile-tag-checkbox" 
                   ${type === 'selected' ? 'checked' : ''}>
            <div class="mobile-tag-info">
                <div class="mobile-tag-name">${tag.name}${lineageBadge}</div>
                <div class="mobile-tag-details">${details}</div>
            </div>
        `;

        // Add event listener
        const checkbox = div.querySelector('.mobile-tag-checkbox');
        checkbox.addEventListener('change', (e) => {
            if (type === 'available') {
                this.moveTagToSelected(tag);
            } else {
                this.moveTagToAvailable(tag);
            }
        });

        return div;
    }

    async moveTagToSelected(tag) {
        try {
            const response = await fetch('/api/move-tags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tags: [tag.name],
                    direction: 'to_selected'
                })
            });

            if (response.ok) {
                await this.loadTags();
                this.showToast('Tag moved to selected', 'success');
            }
        } catch (error) {
            console.error('Error moving tag:', error);
            this.showToast('Error moving tag', 'error');
        }
    }

    async moveTagToAvailable(tag) {
        try {
            const response = await fetch('/api/move-tags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tags: [tag.name],
                    direction: 'to_available'
                })
            });

            if (response.ok) {
                await this.loadTags();
                this.showToast('Tag moved to available', 'success');
            }
        } catch (error) {
            console.error('Error moving tag:', error);
            this.showToast('Error moving tag', 'error');
        }
    }

    selectAllAvailable(selectAll) {
        const checkboxes = document.querySelectorAll('#mobileAvailableTags .mobile-tag-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = selectAll;
        });

        if (selectAll) {
            this.moveAllAvailableToSelected();
        }
    }

    async moveAllAvailableToSelected() {
        try {
            const tagNames = this.availableTags.map(tag => tag.name);
            
            const response = await fetch('/api/move-tags', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tags: tagNames,
                    direction: 'to_selected'
                })
            });

            if (response.ok) {
                await this.loadTags();
                this.showToast('All tags moved to selected', 'success');
            }
        } catch (error) {
            console.error('Error moving all tags:', error);
            this.showToast('Error moving tags', 'error');
        }
    }

    applyFilters() {
        // This would be handled by the backend, but for now we'll just reload
        this.loadTags();
    }

    applySearch(searchTerm) {
        const tagItems = document.querySelectorAll('.mobile-tag-item');
        
        tagItems.forEach(item => {
            const tagName = item.querySelector('.mobile-tag-name').textContent.toLowerCase();
            const tagDetails = item.querySelector('.mobile-tag-details').textContent.toLowerCase();
            const searchLower = searchTerm.toLowerCase();
            
            if (tagName.includes(searchLower) || tagDetails.includes(searchLower)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }

    updateSelectedCount() {
        const countElement = document.getElementById('mobileSelectedCount');
        countElement.textContent = this.selectedTags.length;
    }

    async generateLabels() {
        if (this.selectedTags.length === 0) {
            this.showToast('Please select at least one tag', 'warning');
            return;
        }

        try {
            this.showLoading('Generating labels...');
            
            const template = document.getElementById('mobileTemplateSelect').value;
            const format = document.getElementById('mobileFormatSelect').value;

            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    template: template,
                    format: format
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `labels_${template}_${new Date().toISOString().slice(0, 10)}.${format}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showToast('Labels generated successfully!', 'success');
            } else {
                throw new Error('Generation failed');
            }
        } catch (error) {
            console.error('Generation error:', error);
            this.showToast('Generation failed. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    async matchJsonMobile() {
        const url = document.getElementById('mobileJsonUrl').value.trim();
        if (!url) {
            this.showToast('Please enter a JSON URL', 'warning');
            return;
        }

        try {
            this.showLoading('Matching JSON data...');
            
            const response = await fetch('/api/json-match', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            });

            if (response.ok) {
                const result = await response.json();
                this.showToast(`Matched ${result.matched_count} products`, 'success');
                await this.loadTags(); // Refresh tags after matching
            } else {
                throw new Error('JSON matching failed');
            }
        } catch (error) {
            console.error('JSON matching error:', error);
            this.showToast('JSON matching failed. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    loadSettings() {
        const autoLoad = this.getSetting('autoLoad', true);
        const showColors = this.getSetting('showColors', true);
        const compactView = this.getSetting('compactView', false);

        document.getElementById('mobileAutoLoad').checked = autoLoad;
        document.getElementById('mobileShowColors').checked = showColors;
        document.getElementById('mobileCompactView').checked = compactView;
    }

    saveSetting(key, value) {
        localStorage.setItem(`mobile_${key}`, JSON.stringify(value));
    }

    getSetting(key, defaultValue = null) {
        const stored = localStorage.getItem(`mobile_${key}`);
        return stored ? JSON.parse(stored) : defaultValue;
    }

    showLoading(message = 'Loading...') {
        const loadingSplash = document.getElementById('mobileLoadingSplash');
        const loadingTitle = loadingSplash.querySelector('.mobile-loading-title');
        loadingTitle.textContent = message;
        loadingSplash.style.display = 'flex';
    }

    hideLoading() {
        const loadingSplash = document.getElementById('mobileLoadingSplash');
        loadingSplash.style.display = 'none';
    }

    showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `mobile-toast mobile-toast-${type}`;
        toast.textContent = message;
        
        // Add to page
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    // Bottom bar actions
    clearFiltersMobile() {
        this.filters = {
            vendor: 'All',
            brand: 'All',
            productType: 'All',
            lineage: 'All',
            weight: 'All'
        };

        document.getElementById('mobileVendorFilter').value = 'All';
        document.getElementById('mobileBrandFilter').value = 'All';
        document.getElementById('mobileProductTypeFilter').value = 'All';
        document.getElementById('mobileLineageFilter').value = 'All';
        document.getElementById('mobileWeightFilter').value = 'All';
        document.getElementById('mobileSearchInput').value = '';

        this.applyFilters();
        this.showToast('Filters cleared', 'success');
    }

    refreshDataMobile() {
        this.loadTags();
        this.showToast('Data refreshed', 'success');
    }

    showHelpMobile() {
        const modal = new bootstrap.Modal(document.getElementById('mobileHelpModal'));
        modal.show();
    }
}

// Initialize mobile app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.mobileAGT = new MobileAGTDesigner();
});

// Global functions for onclick handlers
function matchJsonMobile() {
    window.mobileAGT.matchJsonMobile();
}

function generateLabelsMobile() {
    window.mobileAGT.generateLabels();
}

function clearFiltersMobile() {
    window.mobileAGT.clearFiltersMobile();
}

function refreshDataMobile() {
    window.mobileAGT.refreshDataMobile();
}

function showHelpMobile() {
    window.mobileAGT.showHelpMobile();
}

// Add mobile-specific CSS for toasts
const mobileToastCSS = `
.mobile-toast {
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%) translateY(-100px);
    background: rgba(45, 34, 58, 0.95);
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    border: 1px solid rgba(160, 132, 232, 0.3);
    z-index: 10000;
    transition: transform 0.3s ease;
    max-width: 90%;
    text-align: center;
}

.mobile-toast.show {
    transform: translateX(-50%) translateY(0);
}

.mobile-toast-success {
    border-color: rgba(67, 233, 123, 0.5);
    background: rgba(67, 233, 123, 0.1);
}

.mobile-toast-error {
    border-color: rgba(220, 53, 69, 0.5);
    background: rgba(220, 53, 69, 0.1);
}

.mobile-toast-warning {
    border-color: rgba(255, 193, 7, 0.5);
    background: rgba(255, 193, 7, 0.1);
}
`;

// Inject CSS
const style = document.createElement('style');
style.textContent = mobileToastCSS;
document.head.appendChild(style); 