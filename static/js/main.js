// Global error handler to prevent window from exiting
window.addEventListener('error', function(event) {
    console.error('Global error caught:', event.error);
    console.error('Error at:', event.filename, 'line:', event.lineno, 'column:', event.colno);
    event.preventDefault();
    return false;
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    event.preventDefault();
});

// Toast fallback: define Toast if not present
if (typeof Toast === 'undefined') {
  window.Toast = {
    show: (type, msg) => {
      if (type === 'error') {
        alert('Error: ' + msg);
      } else {
        alert(msg);
      }
    }
  };
}

// Classic types that should show "Lineage" instead of "Brand"
const CLASSIC_TYPES = [
    "flower", "pre-roll", "concentrate", "infused pre-roll", 
    "solventless concentrate", "vape cartridge"
];

// Add this near the top of the file, before any code that uses it
// Product type normalization mapping (same as backend TYPE_OVERRIDES)
const PRODUCT_TYPE_OVERRIDES = {
  "all-in-one": "vape cartridge",
  "rosin": "concentrate",
  "mini buds": "flower",
  "bud": "flower",
  "pre-roll": "pre-roll",
  "alcohol/ethanol extract": "rso/co2 tankers",
  "Alcohol/Ethanol Extract": "rso/co2 tankers",
  "alcohol ethanol extract": "rso/co2 tankers",
  "Alcohol Ethanol Extract": "rso/co2 tankers",
  "c02/ethanol extract": "rso/co2 tankers",
  "CO2 Concentrate": "rso/co2 tankers",
  "co2 concentrate": "rso/co2 tankers"
};

// Function to normalize product types (same as backend)
function normalizeProductType(productType) {
  if (!productType) return productType;
  const normalized = PRODUCT_TYPE_OVERRIDES[productType.toLowerCase()];
  return normalized || productType;
}

// Global function to restore body scroll after modal closes
function restoreBodyScroll() {
  document.body.style.overflow = '';
  document.body.classList.remove('modal-open');
  document.body.style.paddingRight = '';
  document.body.style.pointerEvents = '';
}

// Function to open strain lineage editor
async function openStrainLineageEditor() {
  try {
    // Show loading state
    const loadingModal = document.createElement('div');
    loadingModal.className = 'modal fade';
    loadingModal.id = 'loadingModal';
    loadingModal.innerHTML = `
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-body text-center">
            <div class="spinner-border text-primary" role="status">
              <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading strains from database...</p>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(loadingModal);
    
    const loadingInstance = new bootstrap.Modal(loadingModal);
    loadingInstance.show();
    
    // Add timeout protection with shorter timeout
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => {
        // Ensure loading modal is hidden on timeout
        if (loadingInstance) {
          loadingInstance.hide();
        }
        if (loadingModal && loadingModal.parentNode) {
          loadingModal.parentNode.removeChild(loadingModal);
        }
        reject(new Error('Request timed out after 10 seconds'));
      }, 10000); // 10 second timeout
    });
    
    // Fetch all strains from the master database with timeout
    const fetchPromise = fetch('/api/get-all-strains');
    const response = await Promise.race([fetchPromise, timeoutPromise]);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch strains from database: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    // Hide loading modal and ensure it's completely removed
    if (loadingInstance) {
      loadingInstance.hide();
    }
    if (loadingModal && loadingModal.parentNode) {
      loadingModal.parentNode.removeChild(loadingModal);
    }
    
    // Ensure any remaining loading states are cleared
    const remainingLoadingModals = document.querySelectorAll('.modal[id*="loading"]');
    remainingLoadingModals.forEach(modal => {
      const instance = bootstrap.Modal.getInstance(modal);
      if (instance) {
        instance.hide();
      }
      if (modal.parentNode) {
        modal.parentNode.removeChild(modal);
      }
    });
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to load strains');
    }
    
    const strains = data.strains;
    
    if (strains.length === 0) {
      alert('No strains found in the master database.');
      return;
    }
    
    // Create a strain selection modal with search functionality
    console.log('Creating strain selection modal with', strains.length, 'strains');
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'strainSelectionModal';
    modal.setAttribute('data-bs-backdrop', 'static');
    modal.setAttribute('data-bs-keyboard', 'false');
    modal.innerHTML = `
      <div class="modal-backdrop fade show" style="z-index: 10000;"></div>
      <div class="modal-dialog modal-lg" style="z-index: 10002;">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Choose a strain to edit lineage for</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted mb-3">Choose a strain to edit lineage for ALL products with that strain in the master database:</p>
            
            <!-- Search Box -->
            <div class="mb-3">
              <div class="input-group">
                <span class="input-group-text">
                  <i class="fas fa-search"></i>
                </span>
                <input type="text" class="form-control" id="strainSearchInput" 
                       placeholder="Search strains by name..." 
                       autocomplete="off">
                <button class="btn btn-outline-secondary" type="button" id="clearStrainSearch">
                  Clear
                </button>
              </div>
              <div class="form-text">
                <small class="text-muted">
                  <span id="strainSearchResults">Showing ${strains.length} strains</span>
                </small>
              </div>
            </div>
            
            <div class="list-group" id="strainListContainer">
              ${strains.map(strain => `
                <button type="button" class="list-group-item list-group-item-action strain-item" 
                        data-strain-name="${strain.strain_name.toLowerCase()}"
                        onclick="selectStrainForEditing('${strain.strain_name.replace(/'/g, "\\'")}', '${strain.current_lineage}')">
                  <div class="d-flex justify-content-between align-items-start">
                    <div>
                      <strong class="strain-name">${strain.strain_name}</strong>
                      <br>
                      <small class="text-muted">
                        Current: ${strain.current_lineage} | 
                        Products: ${strain.total_occurrences} | 
                        Last seen: ${new Date(strain.last_seen_date).toLocaleDateString()}
                      </small>
                    </div>
                    <span class="badge bg-primary">${strain.current_lineage}</span>
                  </div>
                </button>
              `).join('')}
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
          </div>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    console.log('Modal added to DOM, modal element:', modal);
    
    // Add search functionality
    const searchInput = document.getElementById('strainSearchInput');
    const clearSearchBtn = document.getElementById('clearStrainSearch');
    const strainItems = document.querySelectorAll('.strain-item');
    const resultsCounter = document.getElementById('strainSearchResults');
    
    // Search function
    function filterStrains(searchTerm) {
      const term = searchTerm.toLowerCase().trim();
      let visibleCount = 0;
      
      strainItems.forEach(item => {
        const strainName = item.getAttribute('data-strain-name');
        const strainNameElement = item.querySelector('.strain-name');
        const originalText = strainNameElement.textContent;
        
        if (term === '' || strainName.includes(term)) {
          item.style.display = 'block';
          visibleCount++;
          
          // Highlight matching text if there's a search term
          if (term !== '') {
            const regex = new RegExp(`(${term})`, 'gi');
            strainNameElement.innerHTML = originalText.replace(regex, '<mark>$1</mark>');
          } else {
            strainNameElement.innerHTML = originalText;
          }
        } else {
          item.style.display = 'none';
        }
      });
      
      // Update results counter
      resultsCounter.textContent = `Showing ${visibleCount} of ${strains.length} strains`;
      
      // Show "no results" message if needed
      if (visibleCount === 0 && term !== '') {
        const noResults = document.createElement('div');
        noResults.className = 'text-center text-muted py-3';
        noResults.innerHTML = `
          <i class="fas fa-search me-2"></i>
          No strains found matching "${searchTerm}"
        `;
        
        const container = document.getElementById('strainListContainer');
        const existingNoResults = container.querySelector('.no-results-message');
        if (!existingNoResults) {
          noResults.classList.add('no-results-message');
          container.appendChild(noResults);
        }
      } else {
        // Remove "no results" message if it exists
        const noResults = document.querySelector('.no-results-message');
        if (noResults) {
          noResults.remove();
        }
      }
    }
    
    // Event listeners for search
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        filterStrains(e.target.value);
      });
      
      // Focus on search input when modal opens
      searchInput.focus();
      
      // Handle Enter key to select first visible strain
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const firstVisible = document.querySelector('.strain-item[style*="block"], .strain-item:not([style*="none"])');
          if (firstVisible) {
            firstVisible.click();
          }
        }
      });
    }
    
    // Clear search button
    if (clearSearchBtn) {
      clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        filterStrains('');
        searchInput.focus();
      });
    }
    
    // Ensure any remaining loading modals are completely hidden and removed
    const existingLoadingModals = document.querySelectorAll('.modal[id*="loading"]');
    console.log('Found existing loading modals:', existingLoadingModals.length);
    existingLoadingModals.forEach(loadingModal => {
      const instance = bootstrap.Modal.getInstance(loadingModal);
      if (instance) {
        console.log('Hiding loading modal instance');
        instance.hide();
      }
      if (loadingModal.parentNode) {
        console.log('Removing loading modal from DOM');
        loadingModal.parentNode.removeChild(loadingModal);
      }
    });
    
    // Show the modal with debugging
    console.log('Creating modal instance for strain selection');
    const modalInstance = new bootstrap.Modal(modal);
    console.log('Showing strain selection modal');
    modalInstance.show();
    
    // Add a small delay to ensure the modal is properly displayed
    setTimeout(() => {
      console.log('Modal should now be visible');
      // Ensure any loading spinners in the modal are removed
      const loadingSpinners = modal.querySelectorAll('.spinner-border, .spinner-grow');
      loadingSpinners.forEach(spinner => {
        spinner.remove();
      });
      
      // Force the modal to be visible if it's not
      if (!modal.classList.contains('show')) {
        console.log('Modal not visible, forcing show');
        modal.classList.add('show');
        modal.style.display = 'block';
        modal.setAttribute('aria-hidden', 'false');
      }
    }, 100);
    
    // Clean up modal when hidden
    modal.addEventListener('hidden.bs.modal', () => {
      console.log('Strain selection modal hidden, cleaning up');
      if (modal.parentNode) {
        document.body.removeChild(modal);
      }
      // Ensure body overflow is restored when modal is closed
      restoreBodyScroll();
    });
    
    // Add event listener for when modal is shown
    modal.addEventListener('shown.bs.modal', () => {
      console.log('Strain selection modal is now visible');
    });
    
  } catch (error) {
    console.error('Error opening strain lineage editor:', error);
    
    // Hide loading modal if it exists
    const loadingModal = document.getElementById('loadingModal');
    if (loadingModal) {
      const loadingInstance = bootstrap.Modal.getInstance(loadingModal);
      if (loadingInstance) {
        loadingInstance.hide();
      }
      document.body.removeChild(loadingModal);
    }
    
    // Show appropriate error message
    if (error.message === 'Request timed out') {
      alert('The request to load strains timed out. Please try again. If the problem persists, refresh the page.');
    } else {
      alert(`Failed to load strains: ${error.message}`);
    }
  }
}

// Function to select a strain for editing
function selectStrainForEditing(strainName, currentLineage) {
  console.log('selectStrainForEditing called with:', strainName, currentLineage);
  
  try {
    // Close the selection modal
    const selectionModal = document.getElementById('strainSelectionModal');
    if (selectionModal) {
      const modalInstance = bootstrap.Modal.getInstance(selectionModal);
      if (modalInstance) {
        modalInstance.hide();
        // Ensure body overflow is restored when selection modal is closed
        setTimeout(restoreBodyScroll, 100);
      }
    }
    
    // Check if strain lineage editor is available
    if (window.strainLineageEditor) {
      console.log('Strain lineage editor is available, calling openEditor');
      try {
        window.strainLineageEditor.openEditor(strainName, currentLineage);
        console.log('openEditor called successfully');
      } catch (error) {
        console.error('Error opening strain lineage editor:', error);
        alert('Error opening strain lineage editor. Please try again.');
        return;
      }
    } else {
      console.log('Strain lineage editor not available, attempting to initialize...');
      
      // Check if the modal element exists
      const modalElement = document.getElementById('strainLineageEditorModal');
      if (!modalElement) {
        console.error('strainLineageEditorModal element not found');
        alert('Strain Lineage Editor modal not found. Please refresh the page and try again.');
        return;
      }
      
      console.log('Modal element found, attempting to initialize StrainLineageEditor');
      
      // Try to initialize the editor
      try {
        if (typeof StrainLineageEditor !== 'undefined') {
          console.log('StrainLineageEditor class is available, initializing...');
          window.strainLineageEditor = StrainLineageEditor.init();
          console.log('StrainLineageEditor initialized');
          
          setTimeout(() => {
            if (window.strainLineageEditor) {
              console.log('Calling openEditor after initialization');
              try {
                window.strainLineageEditor.openEditor(strainName, currentLineage);
                console.log('openEditor called successfully after initialization');
              } catch (openError) {
                console.error('Error calling openEditor after initialization:', openError);
                alert('Error opening strain lineage editor. Please try again.');
              }
            } else {
              console.error('strainLineageEditor still not available after initialization');
              alert('Failed to initialize Strain Lineage Editor. Please refresh the page and try again.');
            }
          }, 100);
        } else {
          console.error('StrainLineageEditor class not defined');
          alert('Strain Lineage Editor not loaded. Please refresh the page and try again.');
        }
      } catch (error) {
        console.error('Error initializing strain lineage editor:', error);
        alert('Failed to initialize Strain Lineage Editor. Please refresh the page and try again.');
      }
    }
  } catch (error) {
    console.error('Error in selectStrainForEditing:', error);
    alert('An unexpected error occurred. Please refresh the page and try again.');
  }
}

const VALID_PRODUCT_TYPES = [
  "flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge",
  "edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule", "paraphernalia",
  "rso/co2 tankers"
];

const debounce = (func, delay) => {
    let timeoutId;
    let isExecuting = false; // Add execution lock
    
    return function(...args) {
        const context = this;
        
        // If already executing, don't schedule another execution
        if (isExecuting) {
            console.log('Generation already in progress, ignoring duplicate request');
            return;
        }
        
        clearTimeout(timeoutId);
        timeoutId = setTimeout(async () => {
            isExecuting = true;
            try {
                await func.apply(context, args);
            } finally {
                isExecuting = false;
            }
        }, delay);
    };
};

// Application Loading Splash Manager
const AppLoadingSplash = {
    loadingSteps: [
        { text: 'Initializing application...', progress: 10 },
        { text: 'Loading templates...', progress: 25 },
        { text: 'Preparing interface...', progress: 40 },
        { text: 'Loading product data...', progress: 60 },
        { text: 'Processing tags...', progress: 75 },
        { text: 'Setting up filters...', progress: 90 },
        { text: 'Almost ready...', progress: 95 },
        { text: 'Welcome to Auto Generating Tag Designer!', progress: 100 }
    ],
    currentStep: 0,
    isVisible: true,
    autoAdvanceInterval: null,

    show() {
        this.isVisible = true;
        this.currentStep = 0;
        
        const splash = document.getElementById('appLoadingSplash');
        const mainContent = document.getElementById('mainContent');
        
        if (splash) {
            splash.style.display = 'flex';
            splash.classList.remove('fade-out');
        }
        
        if (mainContent) {
            mainContent.classList.remove('loaded');
            mainContent.style.opacity = '0';
        }
        
        this.updateProgress(0, 'Initializing application...');
        console.log('Splash screen shown');
    },

    updateProgress(progress, text) {
        const fillElement = document.getElementById('appLoadingFill');
        const textElement = document.getElementById('appLoadingText');
        const statusElement = document.getElementById('appLoadingStatus');
        
        if (fillElement) {
            fillElement.style.width = `${progress}%`;
        }
        
        if (textElement) {
            textElement.style.opacity = '0';
            setTimeout(() => {
                textElement.textContent = text;
                textElement.style.opacity = '1';
            }, 150);
        }
        
        if (statusElement) {
            statusElement.textContent = this.getStatusText(progress);
        }
        
        // Log progress for debugging
        console.log(`Splash progress: ${progress}% - ${text}`);
    },

    getStatusText(progress) {
        if (progress < 25) return 'Initializing';
        if (progress < 50) return 'Loading';
        if (progress < 75) return 'Processing';
        if (progress < 100) return 'Finalizing';
        return 'Ready';
    },

    nextStep() {
        if (this.currentStep < this.loadingSteps.length - 1) {
            this.currentStep++;
            const step = this.loadingSteps[this.currentStep];
            this.updateProgress(step.progress, step.text);
        }
    },

    complete() {
        this.updateProgress(100, 'Welcome to Auto Generating Tag Designer!');
        setTimeout(() => {
            this.hide();
        }, 1000);
    },

    hide() {
        this.isVisible = false;
        this.stopAutoAdvance();
        
        const splash = document.getElementById('appLoadingSplash');
        const mainContent = document.getElementById('mainContent');
        
        if (splash) {
            splash.classList.add('fade-out');
            setTimeout(() => {
                splash.style.display = 'none';
            }, 500);
        }
        
        if (mainContent) {
            setTimeout(() => {
                mainContent.classList.add('loaded');
                mainContent.style.opacity = '1';
            }, 100);
        }
        
        console.log('Splash screen hidden');
    },

    // Auto-advance steps for visual feedback
    startAutoAdvance() {
        this.stopAutoAdvance(); // Clear any existing interval
        this.autoAdvanceInterval = setInterval(() => {
            if (this.isVisible && this.currentStep < this.loadingSteps.length - 2) {
                this.nextStep();
            }
        }, 800);
    },

    stopAutoAdvance() {
        if (this.autoAdvanceInterval) {
            clearInterval(this.autoAdvanceInterval);
            this.autoAdvanceInterval = null;
        }
    },

    // Emergency hide function for debugging
    emergencyHide() {
        console.log('Emergency hiding splash screen');
        this.isVisible = false;
        this.stopAutoAdvance();
        
        const splash = document.getElementById('appLoadingSplash');
        const mainContent = document.getElementById('mainContent');
        
        if (splash) {
            splash.style.display = 'none';
        }
        
        if (mainContent) {
            mainContent.style.opacity = '1';
            mainContent.classList.add('loaded');
        }
    }
};

const TagManager = {
    state: {
        selectedTags: new Set(),
        persistentSelectedTags: new Set(), // New: persistent selected tags independent of filters
        initialized: false,
        filters: {},
        loading: false,
        brandCategories: new Map(),  // Add this for storing brand subcategories
        originalTags: [], // Store original tags separately
        originalFilterOptions: {}, // Store original filter options to preserve order
        lineageColors: {
            'SATIVA': 'var(--lineage-sativa)',
            'INDICA': 'var(--lineage-indica)',
            'HYBRID': 'var(--lineage-hybrid)',
            'HYBRID/SATIVA': 'var(--lineage-hybrid-sativa)',
            'HYBRID/INDICA': 'var(--lineage-hybrid-indica)',
            'CBD': 'var(--lineage-cbd)',
            'PARA': 'var(--lineage-para)',
            'MIXED': 'var(--lineage-mixed)',
            'CBD_BLEND': 'var(--lineage-cbd)'
        },
        filterCache: null,
        updateAvailableTagsTimer: null // Add timer tracking
    },
    isGenerating: false, // Add generation lock flag

    // Function to update brand filter label based on product type
    updateBrandFilterLabel() {
        const brandFilterLabel = document.querySelector('label[for="brandFilter"]');
        if (brandFilterLabel) {
            brandFilterLabel.textContent = 'Brand';
            brandFilterLabel.setAttribute('aria-label', 'Brand Filter');
        }
    },

    updateFilters(filters) {
        if (!filters) return;
        
        // Debug log for filters
        console.log('Updating filters with:', filters);
        
        // Store original filter options to preserve order
        if (!this.state.originalFilterOptions.vendor) {
            this.state.originalFilterOptions = { ...filters };
        }
        
        // Map of filter types to their HTML IDs (matching backend field names)
        const filterFieldMap = {
            vendor: 'vendorFilter',
            brand: 'brandFilter',
            productType: 'productTypeFilter', // Backend now returns 'productType'
            lineage: 'lineageFilter',
            weight: 'weightFilter',
            doh: 'dohFilter',
            highCbd: 'highCbdFilter'
            // Removed strain since there's no strainFilter dropdown in the HTML
        };
        
        // Update each filter dropdown
        Object.entries(filterFieldMap).forEach(([filterType, filterId]) => {
            const filterElement = document.getElementById(filterId);
            
            if (!filterElement) {
                console.warn(`Filter element not found: ${filterId}`);
                return;
            }
            
            // Get values for this filter type
            const fieldValues = filters[filterType] || [];
            const values = new Set();
            fieldValues.forEach(value => {
                if (value && value.trim() !== '') {
                    values.add(value.trim());
                }
            });
            
            // Sort values alphabetically for consistent ordering
            const sortedValues = Array.from(values).sort((a, b) => {
                // Special handling for lineage to maintain logical order
                if (filterType === 'lineage') {
                    const lineageOrder = ['SATIVA', 'INDICA', 'HYBRID', 'HYBRID/SATIVA', 'HYBRID/INDICA', 'CBD', 'CBD_BLEND', 'MIXED', 'PARA'];
                    const aIndex = lineageOrder.indexOf(a.toUpperCase());
                    const bIndex = lineageOrder.indexOf(b.toUpperCase());
                    if (aIndex !== -1 && bIndex !== -1) {
                        return aIndex - bIndex;
                    }
                }
                return a.localeCompare(b);
            });
            
            console.log(`Updating ${filterId} with values:`, sortedValues);
            
            // Special debug for weight filter
            if (filterType === 'weight') {
                console.log('Weight filter values (first 10):', sortedValues.slice(0, 10));
            }
            
            // Store current value
            const currentValue = filterElement.value;
            
            // Update the dropdown options with special formatting for RSO/CO2 Tanker
            filterElement.innerHTML = `
                <option value="">All</option>
                ${sortedValues.map(value => {
                    // Apply special font formatting for RSO/CO2 Tanker
                    if (value === 'rso/co2 tankers') {
                        return `<option value="${value}" style="font-weight: bold; font-style: italic; color: #a084e8;">RSO/CO2 Tanker</option>`;
                    }
                    return `<option value="${value}">${value}</option>`;
                }).join('')}
            `;
            
            // Try to restore the previous selection if it's still valid
            if (currentValue && sortedValues.includes(currentValue)) {
                filterElement.value = currentValue;
            } else {
                filterElement.value = '';
            }
        });
    },

    async updateFilterOptions() {
        try {
            // Get current filter values
            const currentFilters = {
                vendor: document.getElementById('vendorFilter')?.value || '',
                brand: document.getElementById('brandFilter')?.value || '',
                productType: document.getElementById('productTypeFilter')?.value || '',
                lineage: document.getElementById('lineageFilter')?.value || '',
                weight: document.getElementById('weightFilter')?.value || '',
                doh: document.getElementById('dohFilter')?.value || '',
                highCbd: document.getElementById('highCbdFilter')?.value || ''
            };

            // Only update filter options if we have original options
            if (!this.state.originalFilterOptions.vendor) {
                console.log('No original filter options available, skipping update');
                return;
            }

            // Get the currently filtered tags to determine available options
            const tagsToFilter = this.state.originalTags.length > 0 ? this.state.originalTags : this.state.tags;
            
            // Apply current filters to get the subset of tags that would be shown
            const filteredTags = tagsToFilter.filter(tag => {
                // Check vendor filter - only apply if not empty and not "All"
                if (currentFilters.vendor && currentFilters.vendor.trim() !== '' && currentFilters.vendor.toLowerCase() !== 'all') {
                    const tagVendor = (tag.vendor || '').trim();
                    if (tagVendor.toLowerCase() !== currentFilters.vendor.toLowerCase()) {
                        return false;
                    }
                }
                
                // Check brand filter - only apply if not empty and not "All"
                if (currentFilters.brand && currentFilters.brand.trim() !== '' && currentFilters.brand.toLowerCase() !== 'all') {
                    const tagBrand = (tag.productBrand || '').trim();
                    if (tagBrand.toLowerCase() !== currentFilters.brand.toLowerCase()) {
                        return false;
                    }
                }
                
                // Check product type filter - only apply if not empty and not "All"
                if (currentFilters.productType && currentFilters.productType.trim() !== '' && currentFilters.productType.toLowerCase() !== 'all') {
                    const tagProductType = (tag.productType || '').trim();
                    if (tagProductType.toLowerCase() !== currentFilters.productType.toLowerCase()) {
                        return false;
                    }
                }
                
                // Check lineage filter - only apply if not empty and not "All"
                if (currentFilters.lineage && currentFilters.lineage.trim() !== '' && currentFilters.lineage.toLowerCase() !== 'all') {
                    const tagLineage = (tag.lineage || '').trim();
                    if (tagLineage.toLowerCase() !== currentFilters.lineage.toLowerCase()) {
                        return false;
                    }
                }
                
                // Check weight filter - only apply if not empty and not "All"
                if (currentFilters.weight && currentFilters.weight.trim() !== '' && currentFilters.weight.toLowerCase() !== 'all') {
                    const tagWeightWithUnits = (tag.weightWithUnits || tag.weight || tag.WeightUnits || '').toString().trim().toLowerCase();
                    const filterWeight = currentFilters.weight.toString().trim().toLowerCase();
                    if (tagWeightWithUnits !== filterWeight) {
                        return false;
                    }
                }
                
                return true;
            });

            // Extract available options from filtered tags
            const availableOptions = {
                vendor: new Set(),
                brand: new Set(),
                productType: new Set(),
                lineage: new Set(),
                weight: new Set()
            };

            filteredTags.forEach(tag => {
                if (tag.vendor) availableOptions.vendor.add(tag.vendor.trim());
                if (tag.productBrand) availableOptions.brand.add(tag.productBrand.trim());
                if (tag.productType) availableOptions.productType.add(tag.productType.trim());
                if (tag.lineage) availableOptions.lineage.add(tag.lineage.trim());
                if (tag.weightWithUnits || tag.WeightUnits || tag.weight) {
                    // Always use the combined value for display and filtering
                    const combined = (tag.weightWithUnits || tag.WeightUnits || tag.weight).toString().trim();
                    if (combined) availableOptions.weight.add(combined);
                }
            });

            // Update each filter dropdown with available options
            const filterFieldMap = {
                vendor: 'vendorFilter',
                brand: 'brandFilter',
                productType: 'productTypeFilter',
                lineage: 'lineageFilter',
                weight: 'weightFilter'
            };

            Object.entries(filterFieldMap).forEach(([filterType, filterId]) => {
                const filterElement = document.getElementById(filterId);
                if (!filterElement) {
                    return;
                }

                const currentValue = filterElement.value;
                const newOptions = Array.from(availableOptions[filterType]);
                
                // Sort options consistently
                const sortedOptions = [...newOptions].sort((a, b) => {
                    // Special handling for lineage to maintain logical order
                    if (filterType === 'lineage') {
                        const lineageOrder = ['SATIVA', 'INDICA', 'HYBRID', 'HYBRID/SATIVA', 'HYBRID/INDICA', 'CBD', 'CBD_BLEND', 'MIXED', 'PARA'];
                        const aIndex = lineageOrder.indexOf(a.toUpperCase());
                        const bIndex = lineageOrder.indexOf(b.toUpperCase());
                        if (aIndex !== -1 && bIndex !== -1) {
                            return aIndex - bIndex;
                        }
                    }
                    return a.localeCompare(b);
                });
                
                // Only update if options have actually changed
                const currentOptions = Array.from(filterElement.options).map(opt => opt.value).filter(v => v !== '');
                const optionsChanged = currentOptions.length !== sortedOptions.length || 
                                     !currentOptions.every((opt, i) => opt === sortedOptions[i]);
                
                if (optionsChanged) {
                    // Create new options HTML with special formatting for RSO/CO2 Tanker
                    const optionsHtml = `
                        <option value="">All</option>
                        ${sortedOptions.map(value => {
                            // Apply special font formatting for RSO/CO2 Tanker
                            if (value === 'rso/co2 tankers') {
                                return `<option value="${value}" style="font-weight: bold; font-style: italic; color: #a084e8;">RSO/CO2 Tanker</option>`;
                            }
                            return `<option value="${value}">${value}</option>`;
                        }).join('')}
                    `;
                    
                    // Update the dropdown options
                    filterElement.innerHTML = optionsHtml;
                    
                    // Try to restore the previous selection if it's still valid
                    if (currentValue && sortedOptions.includes(currentValue)) {
                        filterElement.value = currentValue;
                    } else {
                        filterElement.value = '';
                    }
                }
            });

        } catch (error) {
            console.error('Error updating filter options:', error);
        }
    },

    applyFilters() {
        // Get current filter values
        const vendorFilter = document.getElementById('vendorFilter')?.value || '';
        const brandFilter = document.getElementById('brandFilter')?.value || '';
        const productTypeFilter = document.getElementById('productTypeFilter')?.value || '';
        const lineageFilter = document.getElementById('lineageFilter')?.value || '';
        const weightFilter = document.getElementById('weightFilter')?.value || '';
        const dohFilter = document.getElementById('dohFilter')?.value || '';
        const highCbdFilter = document.getElementById('highCbdFilter')?.value || '';
        
        // Store current filters in state for use by updateSelectedTags
        this.state.filters = {
            vendor: vendorFilter,
            brand: brandFilter,
            productType: productTypeFilter,
            lineage: lineageFilter,
            weight: weightFilter,
            doh: dohFilter,
            highCbd: highCbdFilter
        };
        
        // Create a filter key for caching
        const filterKey = `${vendorFilter}|${brandFilter}|${productTypeFilter}|${lineageFilter}|${weightFilter}|${dohFilter}|${highCbdFilter}`;
        
        // Check if we have cached results for this exact filter combination
        if (this.state.filterCache && this.state.filterCache.key === filterKey) {
            // Always pass original tags to preserve persistent selections
            this.debouncedUpdateAvailableTags(this.state.originalTags, this.state.filterCache.result);
            this.renderActiveFilters();
            return;
        }
        
        // Filter the tags based on current filter values using original tags
        const tagsToFilter = this.state.originalTags.length > 0 ? this.state.originalTags : this.state.tags;
        
        const filteredTags = tagsToFilter.filter(tag => {
            // Check vendor filter - only apply if not empty and not "All"
            if (vendorFilter && vendorFilter.trim() !== '' && vendorFilter.toLowerCase() !== 'all') {
                const tagVendor = (tag.vendor || '').trim();
                if (tagVendor.toLowerCase() !== vendorFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check brand filter - only apply if not empty and not "All"
            if (brandFilter && brandFilter.trim() !== '' && brandFilter.toLowerCase() !== 'all') {
                const tagBrand = (tag.productBrand || '').trim();
                if (tagBrand.toLowerCase() !== brandFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check product type filter - only apply if not empty and not "All"
            if (productTypeFilter && productTypeFilter.trim() !== '' && productTypeFilter.toLowerCase() !== 'all') {
                const tagProductType = (tag.productType || tag['Product Type*'] || '').trim();
                const normalizedTagProductType = normalizeProductType(tagProductType);
                if (normalizedTagProductType.toLowerCase() !== productTypeFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check lineage filter - only apply if not empty and not "All"
            if (lineageFilter && lineageFilter.trim() !== '' && lineageFilter.toLowerCase() !== 'all') {
                const tagLineage = (tag.lineage || '').trim();
                if (tagLineage.toLowerCase() !== lineageFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check weight filter - only apply if not empty and not "All"
            if (weightFilter && weightFilter.trim() !== '' && weightFilter.toLowerCase() !== 'all') {
                const tagWeightWithUnits = (tag.weightWithUnits || tag.weight || tag['Weight*'] || '').toString().trim().toLowerCase();
                const filterWeight = weightFilter.toString().trim().toLowerCase();
                if (tagWeightWithUnits !== filterWeight) {
                    return false;
                }
            }
            
            // Check DOH filter - only apply if not empty and not "All"
            if (dohFilter && dohFilter.trim() !== '' && dohFilter.toLowerCase() !== 'all') {
                const tagDoh = (tag.doh || tag.DOH || '').toString().trim().toUpperCase();
                const filterDoh = dohFilter.toString().trim().toUpperCase();
                if (tagDoh !== filterDoh) {
                    return false;
                }
            }
            
            // Check High CBD filter - only apply if not empty and not "All"
            if (highCbdFilter && highCbdFilter.trim() !== '' && highCbdFilter.toLowerCase() !== 'all') {
                const tagProductType = (tag.productType || tag['Product Type*'] || '').toString().trim().toLowerCase();
                const isHighCbd = tagProductType.startsWith('high cbd');
                
                if (highCbdFilter === 'High CBD Products' && !isHighCbd) {
                    return false;
                } else if (highCbdFilter === 'Non-High CBD Products' && isHighCbd) {
                    return false;
                }
            }
            
            return true;
        });
        
        // Cache the results
        this.state.filterCache = {
            key: filterKey,
            result: filteredTags
        };
        
        // Always pass original tags to preserve persistent selections, with filtered tags for display
        this.debouncedUpdateAvailableTags(this.state.originalTags, filteredTags);
        
        // Update selected tags to also respect the current filters
        const selectedTagObjects = this.state.persistentSelectedTags.map(name => {
            // First try to find in current tags (filtered view)
            let foundTag = this.state.tags.find(t => t['Product Name*'] === name);
            // If not found in current tags, try original tags
            if (!foundTag) {
                foundTag = this.state.originalTags.find(t => t['Product Name*'] === name);
            }
            // If still not found, create a minimal tag object (for JSON matched items)
            if (!foundTag) {
                console.warn(`Tag not found in state: ${name}, creating minimal tag object`);
                foundTag = {
                    'Product Name*': name,
                    'Product Brand': 'Unknown',
                    'Vendor': 'Unknown',
                    'Product Type*': 'Unknown',
                    'Lineage': 'MIXED'
                };
            }
            return foundTag;
        }).filter(Boolean);
        
        this.updateSelectedTags(selectedTagObjects);
        this.renderActiveFilters();
    },

    handleSearch(listId, searchInputId) {
        const searchInput = document.getElementById(searchInputId);
        const searchTerm = searchInput.value.toLowerCase().trim();

        // Choose which tags to filter
        let tags = [];
        if (listId === 'availableTags') {
            tags = this.state.originalTags || [];
        } else if (listId === 'selectedTags') {
            tags = Array.from(this.state.selectedTags).map(name =>
                this.state.originalTags.find(t => t['Product Name*'] === name)
            ).filter(Boolean);
        }

        if (!searchTerm) {
            // Restore full list
            if (listId === 'availableTags') {
                this.debouncedUpdateAvailableTags(this.state.originalTags, null);
            } else if (listId === 'selectedTags') {
                this.updateSelectedTags(tags);
            }
            searchInput.classList.remove('search-active');
            return;
        }

        // Filter tags: only match product name
        const filteredTags = tags.filter(tag => {
            const tagName = tag['Product Name*'] || '';
            return tagName.toLowerCase().includes(searchTerm);
        });

        // Update the list with only matching tags
        if (listId === 'availableTags') {
            this.debouncedUpdateAvailableTags(this.state.originalTags, filteredTags);
            // Scroll to top of available tags list after search
            setTimeout(() => {
                const availableTagsContainer = document.getElementById('availableTags');
                if (availableTagsContainer) {
                    availableTagsContainer.scrollTop = 0;
                }
            }, 50);
        } else if (listId === 'selectedTags') {
            this.updateSelectedTags(filteredTags);
            // Scroll to top of selected tags list after search
            setTimeout(() => {
                const selectedTagsContainer = document.getElementById('selectedTags');
                if (selectedTagsContainer) {
                    selectedTagsContainer.scrollTop = 0;
                }
            }, 50);
        }
        searchInput.classList.add('search-active');
    },

    handleAvailableTagsSearch(event) {
        this.handleSearch('availableTags', 'availableTagsSearch');
    },

    handleSelectedTagsSearch(event) {
        this.handleSearch('selectedTags', 'selectedTagsSearch');
    },

    extractBrand(tag) {
        // Try to get brand from Product Brand field first
        let brand = tag.productBrand || tag.brand || '';
        
        // If no brand found, try to extract from product name
        if (!brand) {
            const productName = tag['Product Name*'] || tag.ProductName || tag.Description || '';
            // Look for "by [Brand]" pattern
            const byMatch = productName.match(/by\s+([A-Za-z0-9\s]+)(?:\s|$)/i);
            if (byMatch) {
                brand = byMatch[1].trim();
            }
        }
        
        // If still no brand found, try to use the vendor as the brand
        if (!brand && tag.vendor) {
            brand = tag.vendor.trim();
        }
        
        return brand;
    },

    // Helper function to capitalize vendor names properly
    capitalizeVendorName(vendor) {
        if (!vendor) return '';
        
        // Handle common vendor name patterns
        const vendorLower = vendor.toLowerCase();
        
        // Known vendor name mappings
        const vendorMappings = {
            '1555 industrial llc': '1555 Industrial LLC',
            'dcz holdings inc': 'DCZ Holdings Inc.',
            'jsm llc': 'JSM LLC',
            'harmony farms': 'Harmony Farms',
            'hustler\'s ambition': 'Hustler\'s Ambition',
            'mama j\'s': 'Mama J\'s'
        };
        
        // Check if we have a known mapping
        if (vendorMappings[vendorLower]) {
            return vendorMappings[vendorLower];
        }
        
        // General capitalization for unknown vendors
        return vendor.split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    },

    // Helper function to capitalize brand names properly
    capitalizeBrandName(brand) {
        if (!brand) return '';
        
        // Handle common brand name patterns
        const brandLower = brand.toLowerCase();
        
        // Known brand name mappings
        const brandMappings = {
            'dank czar': 'Dank Czar',
            'omega': 'Omega',
            'airo pro': 'Airo Pro',
            'mama j\'s': 'Mama J\'s'
        };
        
        // Check if we have a known mapping
        if (brandMappings[brandLower]) {
            return brandMappings[brandLower];
        }
        
        // General capitalization for unknown brands
        return brand.split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(' ');
    },

    organizeBrandCategories(tags) {
        const vendorGroups = new Map();
        let skippedTags = 0;
        
        // Remove duplicates before organizing to prevent UI duplicates
        const seenProductNames = new Set();
        const uniqueTags = tags.filter(tag => {
            const productName = tag['Product Name*'] || tag.ProductName || tag.Description || '';
            if (seenProductNames.has(productName)) {
                console.debug(`Skipping duplicate product in organizeBrandCategories: ${productName}`);
                return false;
            }
            seenProductNames.add(productName);
            return true;
        });
        
        // Debug: Log the first few tags to see their structure
        if (uniqueTags.length > 0) {
            console.log('First tag structure:', uniqueTags[0]);
            console.log('Available keys in first tag:', Object.keys(uniqueTags[0]));
        }
        
        uniqueTags.forEach(tag => {
            // Use the correct field names from the tag object - check multiple possible field names
            let vendor = tag.vendor || tag['Vendor'] || tag['Vendor/Supplier*'] || tag['Vendor/Supplier'] || '';
            let brand = tag.productBrand || tag['Product Brand'] || tag['ProductBrand'] || this.extractBrand(tag) || '';
            const rawProductType = tag.productType || tag['Product Type*'] || tag['Product Type'] || '';
            const normalizedProductType = normalizeProductType(rawProductType.trim());
            const productType = VALID_PRODUCT_TYPES.includes(normalizedProductType.toLowerCase())
              ? normalizedProductType.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ')
              : 'Unknown Type';
            const lineage = tag.lineage || tag['Lineage'] || 'MIXED';
            const weight = tag.weight || tag['Weight*'] || tag['Weight'] || tag['WeightUnits'] || '';
            const weightWithUnits = tag.weightWithUnits || weight || tag['WeightUnits'] || '';

            // If no vendor found, try to extract from product name
            if (!vendor) {
                const productName = tag['Product Name*'] || tag.ProductName || tag.Description || '';
                // Look for "by [Brand]" pattern
                const byMatch = productName.match(/by\s+([A-Za-z0-9\s]+)(?:\s|$)/i);
                if (byMatch) {
                    vendor = byMatch[1].trim();
                }
            }

            // If still no vendor, use brand as vendor
            if (!vendor && brand) {
                vendor = brand;
            }

            // If still no vendor, use a default
            if (!vendor) {
                vendor = 'Unknown Vendor';
            }

            // Normalize the tag data
            const normalizedTag = {
                ...tag,
                vendor: this.capitalizeVendorName(vendor.trim()),
                brand: this.capitalizeBrandName(brand.trim()),
                productType: productType,
                lineage: (lineage || '').trim().toUpperCase(), // always uppercase for color
                weight: weight.trim(),
                weightWithUnits: weightWithUnits.trim(),
                displayName: tag['Product Name*'] || tag.ProductName || tag.Description || 'Unknown Product'
            };

            // Always create vendor group (even if vendor === brand)
            if (!vendorGroups.has(normalizedTag.vendor)) {
                vendorGroups.set(normalizedTag.vendor, new Map());
            }
            const brandGroups = vendorGroups.get(normalizedTag.vendor);

            // Always create brand group under vendor (even if vendor === brand)
            if (!brandGroups.has(normalizedTag.brand)) {
                brandGroups.set(normalizedTag.brand, new Map());
            }
            const productTypeGroups = brandGroups.get(normalizedTag.brand);

            // Create product type group if it doesn't exist
            if (!productTypeGroups.has(normalizedTag.productType)) {
                productTypeGroups.set(normalizedTag.productType, new Map());
            }
            const weightGroups = productTypeGroups.get(normalizedTag.productType);

            // Create weight group if it doesn't exist - use weightWithUnits as the key
            if (!weightGroups.has(normalizedTag.weightWithUnits)) {
                weightGroups.set(normalizedTag.weightWithUnits, []);
            }
            weightGroups.get(normalizedTag.weightWithUnits).push(normalizedTag);
        });

        if (skippedTags > 0) {
            console.info(`Skipped ${skippedTags} tags due to missing vendor information`);
        }

        return vendorGroups;
    },

    // Debounced version of updateAvailableTags to prevent multiple rapid calls
    debouncedUpdateAvailableTags: debounce(function(originalTags, filteredTags = null) {
        // Show action splash for tag population
        this.showActionSplash('Populating tags...');
        
        // Use requestAnimationFrame to ensure the splash shows before heavy DOM work
        requestAnimationFrame(() => {
            this._updateAvailableTags(originalTags, filteredTags);
            
            // Hide splash after a short delay to ensure smooth transition
            setTimeout(() => {
                this.hideActionSplash();
            }, 100);
        });
    }, 100),

    // Internal function that actually updates the available tags
    _updateAvailableTags(originalTags, filteredTags = null) {
        if (!originalTags || !Array.isArray(originalTags)) {
            console.warn('updateAvailableTags called with invalid originalTags:', originalTags);
            return;
        }
        
        console.time('updateAvailableTags');
        
        const container = document.getElementById('availableTags');
        if (!container) {
            console.error('availableTags container not found');
            return;
        }

        // Store original tags in state for later use
        this.state.originalTags = [...originalTags];
        
        // Use filtered tags for display if provided, otherwise use original tags
        let tagsToDisplay = filteredTags || originalTags;
        
        // Remove duplicates based on product name to prevent UI duplicates
        const seenProductNames = new Set();
        tagsToDisplay = tagsToDisplay.filter(tag => {
            const productName = tag['Product Name*'] || tag.ProductName || tag.Description || '';
            if (seenProductNames.has(productName)) {
                console.debug(`Skipping duplicate product in UI: ${productName}`);
                return false;
            }
            seenProductNames.add(productName);
            return true;
        });
        
        // Filter out selected tags from available tags display
        const selectedTagNames = new Set(this.state.persistentSelectedTags);
        tagsToDisplay = tagsToDisplay.filter(tag => !selectedTagNames.has(tag['Product Name*']));
        
        this.state.tags = [...tagsToDisplay];
        
        // Store original tags if this is the first time loading
        if (this.state.originalTags.length === 0) {
            this.state.originalTags = [...originalTags];
        }
        
        // Store the select all containers before clearing
        const selectAllAvailableContainer = container.querySelector('.select-all-container');
        const selectAllAvailableCheckbox = document.getElementById('selectAllAvailable');
        
        // Clear existing content but preserve the select all container
        container.innerHTML = '';
        
        // Re-add the select all container if it existed
        if (selectAllAvailableContainer) {
            container.insertBefore(selectAllAvailableContainer, container.firstChild);
        } else {
            // Create select all container if it doesn't exist
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'd-flex align-items-center gap-3 mb-2';
            selectAllContainer.innerHTML = `
                <label class="d-flex align-items-center gap-2 cursor-pointer mb-0 select-all-container">
                    <input type="checkbox" id="selectAllAvailable" class="custom-checkbox">
                    <span class="text-secondary fw-semibold">Select All Available</span>
                </label>
            `;
            container.insertBefore(selectAllContainer, container.firstChild);
        }

        // Add global select all checkbox - only add event listener once
        const topSelectAll = document.getElementById('selectAllAvailable');
        console.log('Select All Available checkbox found:', topSelectAll);
        if (topSelectAll && !topSelectAll.hasAttribute('data-listener-added')) {
            console.log('Adding event listener to Select All Available checkbox');
            topSelectAll.setAttribute('data-listener-added', 'true');
            topSelectAll.addEventListener('change', (e) => {
                console.log('Select All Available checkbox changed:', e.target.checked);
                const isChecked = e.target.checked;
                const tagCheckboxes = document.querySelectorAll('#availableTags .tag-checkbox');
                console.log('Found available tag checkboxes:', tagCheckboxes.length);
                tagCheckboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                    if (tag) {
                        if (isChecked) {
                            if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            }
                        } else {
                            const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            }
                        }
                    }
                });
                // Update the regular selectedTags set to match persistent ones
                this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                
                // Update the selected tags display
                const selectedTagObjects = this.state.persistentSelectedTags.map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean);
                this.updateSelectedTags(selectedTagObjects);
                
                // Efficiently update available tags display
                this.efficientlyUpdateAvailableTagsDisplay();
            });
        }

        // If no tags, just return
        if (tagsToDisplay.length === 0) {
            return;
        }

        // Assign a unique tagId to each tag (use index for uniqueness)
        tagsToDisplay.forEach((tag, idx) => {
            tag.tagId = tag['Product Name*'] + '___' + idx;
        });

        // Organize tags into hierarchical groups
        const groupedTags = this.organizeBrandCategories(tagsToDisplay);

        // Sort vendors alphabetically
        const sortedVendors = Array.from(groupedTags.entries())
            .sort(([a], [b]) => (a || '').localeCompare(b || ''));

        // Create vendor sections
        sortedVendors.forEach(([vendor, brandGroups]) => {
            const vendorSection = document.createElement('div');
            vendorSection.className = 'vendor-section mb-3';
            // Remove vendor label
            // Create vendor header with integrated checkbox
            const vendorHeader = document.createElement('h5');
            vendorHeader.className = 'vendor-header mb-2 d-flex align-items-center';
            
            const vendorCheckbox = document.createElement('input');
            vendorCheckbox.type = 'checkbox';
            vendorCheckbox.className = 'select-all-checkbox me-2';
            vendorCheckbox.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                // Select all descendant checkboxes (including subcategories and tags)
                const checkboxes = vendorSection.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                    // Only update persistentSelectedTags for tag-checkboxes
                    if (checkbox.classList.contains('tag-checkbox')) {
                        const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                        if (tag) {
                            if (isChecked) {
                                if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                    this.state.persistentSelectedTags.push(tag['Product Name*']);
                                }
                            } else {
                                const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                                if (index > -1) {
                                    this.state.persistentSelectedTags.splice(index, 1);
                                }
                            }
                        }
                    }
                });
                // Update the regular selectedTags set to match persistent ones
                this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                
                // Update the selected tags display
                const selectedTagObjects = this.state.persistentSelectedTags.map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean);
                this.updateSelectedTags(selectedTagObjects);
                
                // Use efficient update instead of rebuilding entire DOM
                this.efficientlyUpdateAvailableTagsDisplay();
            });
            vendorHeader.appendChild(vendorCheckbox);
            vendorHeader.appendChild(document.createTextNode(vendor));
            vendorSection.appendChild(vendorHeader);

            // Create brand sections
            const sortedBrands = Array.from(brandGroups.entries())
                .sort(([a], [b]) => (a || '').localeCompare(b || ''));

            sortedBrands.forEach(([brand, productTypeGroups]) => {
                const brandSection = document.createElement('div');
                brandSection.className = 'brand-section ms-3 mb-2';
                // Remove brand label
                // Create brand header with integrated checkbox
                const brandHeader = document.createElement('h6');
                brandHeader.className = 'brand-header mb-2 d-flex align-items-center';
                
                const brandCheckbox = document.createElement('input');
                brandCheckbox.type = 'checkbox';
                brandCheckbox.className = 'select-all-checkbox me-2';
                brandCheckbox.addEventListener('change', (e) => {
                    const isChecked = e.target.checked;
                    // Select all descendant checkboxes (including subcategories and tags)
                    const checkboxes = brandSection.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = isChecked;
                        // Only update persistentSelectedTags for tag-checkboxes
                        if (checkbox.classList.contains('tag-checkbox')) {
                            const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                            if (tag) {
                                if (isChecked) {
                                    if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                    this.state.persistentSelectedTags.push(tag['Product Name*']);
                                }
                                } else {
                                    const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                                if (index > -1) {
                                    this.state.persistentSelectedTags.splice(index, 1);
                                }
                                }
                            }
                        }
                    });
                    // Update the regular selectedTags set to match persistent ones
                    this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                    
                    // Update the selected tags display
                    const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                        this.state.tags.find(t => t['Product Name*'] === name)
                    ).filter(Boolean);
                    this.updateSelectedTags(selectedTagObjects);
                    
                    // Use efficient update instead of rebuilding entire DOM
                    this.efficientlyUpdateAvailableTagsDisplay();
                });
                brandHeader.appendChild(brandCheckbox);
                brandHeader.appendChild(document.createTextNode(brand));
                brandSection.appendChild(brandHeader);

                // Create product type sections
                const sortedProductTypes = Array.from(productTypeGroups.entries())
                    .sort(([a], [b]) => (a || '').localeCompare(b || ''));

                sortedProductTypes.forEach(([productType, weightGroups]) => {
                    const productTypeSection = document.createElement('div');
                    productTypeSection.className = 'product-type-section ms-3 mb-2';
                    // Remove type label
                    // Create product type header
                    const typeHeader = document.createElement('div');
                    typeHeader.className = 'product-type-header mb-2 d-flex align-items-center';
                    
                    const productTypeCheckbox = document.createElement('input');
                    productTypeCheckbox.type = 'checkbox';
                    productTypeCheckbox.className = 'select-all-checkbox me-2';
                    productTypeCheckbox.addEventListener('change', (e) => {
                        const isChecked = e.target.checked;
                        // Select all descendant checkboxes (including subcategories and tags)
                        const checkboxes = productTypeSection.querySelectorAll('input[type="checkbox"]');
                        checkboxes.forEach(checkbox => {
                            checkbox.checked = isChecked;
                            // Only update persistentSelectedTags for tag-checkboxes
                            if (checkbox.classList.contains('tag-checkbox')) {
                                const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                if (tag) {
                                    if (isChecked) {
                                        if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                                    } else {
                                        const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                                    }
                                }
                            }
                        });
                        // Update the regular selectedTags set to match persistent ones
                        this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                        
                        // Update the selected tags display
                        const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                            this.state.tags.find(t => t['Product Name*'] === name)
                        ).filter(Boolean);
                        this.updateSelectedTags(selectedTagObjects);
                        
                        // Use efficient update instead of rebuilding entire DOM
                        this.efficientlyUpdateAvailableTagsDisplay();
                    });
                    typeHeader.appendChild(productTypeCheckbox);
                    typeHeader.appendChild(document.createTextNode(productType));
                    productTypeSection.appendChild(typeHeader);

                    // Create weight sections
                    const sortedWeights = Array.from(weightGroups.entries())
                        .sort(([a], [b]) => (a || '').localeCompare(b || ''));

                    sortedWeights.forEach(([weight, tags]) => {
                        const weightSection = document.createElement('div');
                        weightSection.className = 'weight-section ms-3 mb-1';
                        // Remove weight label
                        // Create weight header
                        const weightHeader = document.createElement('div');
                        weightHeader.className = 'weight-header mb-1 d-flex align-items-center';
                        
                        const weightCheckbox = document.createElement('input');
                        weightCheckbox.type = 'checkbox';
                        weightCheckbox.className = 'select-all-checkbox me-2';
                        weightCheckbox.addEventListener('change', (e) => {
                            const isChecked = e.target.checked;
                            // Select all descendant checkboxes (including subcategories and tags)
                            const checkboxes = weightSection.querySelectorAll('input[type="checkbox"]');
                            checkboxes.forEach(checkbox => {
                                checkbox.checked = isChecked;
                                // Only update persistentSelectedTags for tag-checkboxes
                                if (checkbox.classList.contains('tag-checkbox')) {
                                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                    if (tag) {
                                        if (isChecked) {
                                            if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                                        } else {
                                            const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                                        }
                                    }
                                }
                            });
                            // Update the regular selectedTags set to match persistent ones
                            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                            
                            // Update the selected tags display
                            const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                                this.state.tags.find(t => t['Product Name*'] === name)
                            ).filter(Boolean);
                            this.updateSelectedTags(selectedTagObjects);
                            
                            // Use efficient update instead of rebuilding entire DOM
                            this.efficientlyUpdateAvailableTagsDisplay();
                        });
                        weightHeader.appendChild(weightCheckbox);
                        weightHeader.appendChild(document.createTextNode(weight));
                        weightSection.appendChild(weightHeader);
                        // Always render tags as leaf nodes - sort alphabetically by product name
                        if (tags && tags.length > 0) {
                            // Sort tags alphabetically by product name
                            const sortedTags = tags.sort((a, b) => {
                                const nameA = (a['Product Name*'] || a.ProductName || a.Description || '').toLowerCase();
                                const nameB = (b['Product Name*'] || b.ProductName || b.Description || '').toLowerCase();
                                return nameA.localeCompare(nameB);
                            });
                            
                            sortedTags.forEach(tag => {
                                const tagElement = this.createTagElement(tag);
                                tagElement.querySelector('.tag-checkbox').checked = this.state.persistentSelectedTags.includes(tag['Product Name*']);
                                weightSection.appendChild(tagElement);
                            });
                        }
                        productTypeSection.appendChild(weightSection);
                    });
                    brandSection.appendChild(productTypeSection);
                });
                vendorSection.appendChild(brandSection);
            });
            container.appendChild(vendorSection);
        });

        this.updateTagCount('available', tagsToDisplay.length);
        console.timeEnd('updateAvailableTags');
        
        // Reinitialize drag and drop for new tags
        if (window.dragAndDropManager) {
            window.dragAndDropManager.reinitializeTagDragAndDrop();
            // Update indicators for new tags
            setTimeout(() => {
                window.dragAndDropManager.updateIndicators();
            }, 100);
        }
        
        // Scroll to top of available tags list after filter application
        if (filteredTags !== null) {  // Only scroll when filters are applied (not initial load)
            setTimeout(() => {
                const availableTagsContainer = document.getElementById('availableTags');
                if (availableTagsContainer) {
                    availableTagsContainer.scrollTop = 0;
                }
            }, 50);  // Small delay to ensure DOM is updated
        }
    },

    createTagElement(tag, isForSelectedTags = false) {
        // Create the row container
        const row = document.createElement('div');
        row.className = 'tag-row d-flex align-items-center';

        // Checkbox (leftmost)
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'tag-checkbox me-2';
        checkbox.value = tag['Product Name*'];
        checkbox.checked = this.state.persistentSelectedTags.includes(tag['Product Name*']);
        checkbox.addEventListener('change', (e) => this.handleTagSelection(e, tag));

        // Tag entry (colored)
        const tagElement = document.createElement('div');
        tagElement.className = 'tag-item d-flex align-items-center p-1 mb-1';
        
        // Add special styling for JSON matched tags
        if (tag.Source === 'JSON Match') {
          tagElement.classList.add('json-matched-tag');
          tagElement.style.border = '2px solid #28a745';
          tagElement.style.backgroundColor = 'rgba(40, 167, 69, 0.1)';
          tagElement.style.borderRadius = '8px';
        }
        
        // Set data-lineage attribute for CSS coloring
        const lineage = tag.lineage || tag.Lineage || 'MIXED';
        if (lineage) {
          console.log(`Setting lineage for ${tag['Product Name*']}: ${lineage} -> ${lineage.toUpperCase()}`);
          tagElement.dataset.lineage = lineage.toUpperCase();
        } else {
          console.log(`No lineage found for ${tag['Product Name*']}, using MIXED`);
          tagElement.dataset.lineage = 'MIXED';
        }
        tagElement.dataset.tagId = tag.tagId;
        tagElement.dataset.vendor = tag.vendor;
        tagElement.dataset.brand = tag.brand;
        tagElement.dataset.productType = tag.productType;
        tagElement.dataset.weight = tag.weight;

        // Make the entire tag element clickable to toggle checkbox (but only for available tags)
        // For selected tags, only allow checkbox clicking to toggle selection
        if (!isForSelectedTags) {
            tagElement.style.cursor = 'pointer';
            tagElement.addEventListener('click', (e) => {
                try {
                    // Don't trigger if clicking on the checkbox itself or lineage dropdown
                    if (e.target === checkbox || e.target.classList.contains('lineage-select') || 
                        e.target.closest('.lineage-select')) {
                        return;
                    }
                    // Toggle the checkbox
                    checkbox.checked = !checkbox.checked;
                    // Trigger the change event
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                } catch (error) {
                    console.error('Error in tag element click handler:', error);
                    // Prevent the error from causing the page to exit
                    e.preventDefault();
                    e.stopPropagation();
                }
            });
        } else {
            // For selected tags, only allow checkbox clicking to toggle selection
            tagElement.style.cursor = 'default';
        }

        const tagInfo = document.createElement('div');
        tagInfo.className = 'tag-info flex-grow-1 d-flex align-items-center';
        const tagName = document.createElement('div');
        tagName.className = 'tag-name d-inline-block me-2';
        // Use displayName with fallback
        let displayName = tag.displayName || tag['Product Name*'] || tag.ProductName || tag.Description || 'Unnamed Product';
        // Remove 'by ...' up to the hyphen
        let cleanedName = displayName.replace(/ by [^-]+(?= -)/i, '');
        cleanedName = cleanedName.replace(/-/g, '\u2011');
        tagName.textContent = cleanedName;
        tagInfo.appendChild(tagName);
        
        // Add DOH and High CBD images if applicable
        const dohValue = (tag.DOH || '').toString().toUpperCase();
        const productType = (tag['Product Type*'] || '').toString().toLowerCase();
        
        if (dohValue === 'YES' || dohValue === 'Y') {
            // Check if it's a High CBD product
            if (productType.startsWith('high cbd')) {
                // Add High CBD image
                const highCbdImg = document.createElement('img');
                highCbdImg.src = '/static/img/HighCBD.png';
                highCbdImg.alt = 'High CBD';
                highCbdImg.title = 'High CBD Product';
                highCbdImg.style.height = '24px';
                highCbdImg.style.width = 'auto';
                highCbdImg.style.marginLeft = '6px';
                highCbdImg.style.verticalAlign = 'middle';
                tagInfo.appendChild(highCbdImg);
            } else if (displayName.toLowerCase().includes('high thc')) {
                // Add High THC image
                const highThcImg = document.createElement('img');
                highThcImg.src = '/static/img/HighTHC.png';
                highThcImg.alt = 'High THC';
                highThcImg.title = 'High THC Product';
                highThcImg.style.height = '24px';
                highThcImg.style.width = 'auto';
                highThcImg.style.marginLeft = '6px';
                highThcImg.style.verticalAlign = 'middle';
                tagInfo.appendChild(highThcImg);
            } else {
                // Add regular DOH image
                const dohImg = document.createElement('img');
                dohImg.src = '/static/img/DOH.png';
                dohImg.alt = 'DOH Compliant';
                dohImg.title = 'DOH Compliant Product';
                dohImg.style.height = '24px';
                dohImg.style.width = 'auto';
                dohImg.style.marginLeft = '6px';
                dohImg.style.verticalAlign = 'middle';
                tagInfo.appendChild(dohImg);
            }
        }
        
        // Add JSON match indicator if this tag came from JSON matching
        if (tag.Source === 'JSON Match') {
          const jsonBadge = document.createElement('span');
          jsonBadge.className = 'badge bg-success me-2';
          jsonBadge.style.fontSize = '0.7rem';
          jsonBadge.style.padding = '2px 6px';
          jsonBadge.textContent = 'JSON';
          jsonBadge.title = 'This item was matched from JSON data';
          tagInfo.appendChild(jsonBadge);
        }
        // Create lineage dropdown
        const lineageSelect = document.createElement('select');
        lineageSelect.className = 'form-select form-select-sm lineage-select lineage-dropdown lineage-dropdown-mini';
        lineageSelect.style.height = '28px';
        lineageSelect.style.backgroundColor = 'rgba(255, 255, 255, 0.15)';
        lineageSelect.style.border = '1px solid rgba(255, 255, 255, 0.2)';
        lineageSelect.style.borderRadius = '6px';
        lineageSelect.style.cursor = 'pointer';
        lineageSelect.style.color = '#fff';
        lineageSelect.style.backdropFilter = 'blur(10px)';
        lineageSelect.style.transition = 'all 0.2s ease';
        lineageSelect.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
        // Style the dropdown options
        const style = document.createElement('style');
        style.textContent = `
            .lineage-select option {
                background-color: rgba(30, 30, 30, 0.95);
                color: #fff;
                padding: 8px;
            }
            .lineage-select:hover {
                background-color: rgba(255, 255, 255, 0.2);
                border-color: rgba(255, 255, 255, 0.3);
            }
            .lineage-select:focus {
                background-color: rgba(255, 255, 255, 0.25);
                border-color: rgba(255, 255, 255, 0.4);
                box-shadow: 0 0 0 0.2rem rgba(255, 255, 255, 0.1);
            }
        `;
        document.head.appendChild(style);
        // Add lineage options
        const uniqueLineages = [
            { value: 'SATIVA', label: 'S' },
            { value: 'INDICA', label: 'I' },
            { value: 'HYBRID', label: 'H' },
            { value: 'HYBRID/INDICA', label: 'H/I' },
            { value: 'HYBRID/SATIVA', label: 'H/S' },
            { value: 'CBD', label: 'CBD' },
            { value: 'PARA', label: 'P' },
            { value: 'MIXED', label: 'THC' }
        ];
        uniqueLineages.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.label;
            if ((lineage === option.value) || (option.value === 'CBD' && lineage === 'CBD_BLEND')) {
                optionElement.selected = true;
            }
            lineageSelect.appendChild(optionElement);
        });
        lineageSelect.value = lineage;
        if (tag.productType === 'Paraphernalia' || tag['Product Type*'] === 'Paraphernalia') {
            lineageSelect.disabled = true;
            lineageSelect.style.opacity = '0.7';
        }
        lineageSelect.addEventListener('change', async (e) => {
            const newLineage = e.target.value;
            const prevValue = lineage;
            lineageSelect.disabled = true;
            // Show temporary 'Saving...' option
            const savingOption = document.createElement('option');
            savingOption.value = '';
            savingOption.textContent = 'Saving...';
            savingOption.selected = true;
            savingOption.disabled = true;
            lineageSelect.appendChild(savingOption);
            try {
                await this.updateLineageOnBackend(tag['Product Name*'], newLineage);
                // On success, update tag lineage in state
                tag.lineage = newLineage;
                tag.Lineage = newLineage;
                lineageSelect.value = newLineage;
                // Update the data-lineage attribute
                tagElement.dataset.lineage = newLineage.toUpperCase();
            } catch (err) {
                // On error, revert to previous value
                lineageSelect.value = prevValue;
                console.error('Failed to update lineage');
            } finally {
                // Remove 'Saving...' option and re-enable
                Array.from(lineageSelect.options).forEach(opt => { if (opt.textContent === 'Saving...') opt.remove(); });
                lineageSelect.disabled = false;
            }
        });
        tagElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            if (window.lineageEditor) {
                window.lineageEditor.openEditor(tag['Product Name*'], tag.lineage);
            }
        });
        tagInfo.appendChild(lineageSelect);
        tagElement.appendChild(checkbox);
        tagElement.appendChild(tagInfo);
        row.appendChild(tagElement);
        return row;
    },

    getLineageBadgeLabel(lineage) {
        const map = {
            'SATIVA': 'S',
            'INDICA': 'I',
            'HYBRID': 'H',
            'HYBRID/SATIVA': 'H/S',
            'HYBRID/INDICA': 'H/I',
            'CBD': 'CBD',
            'PARA': 'P',
            'MIXED': 'THC',
            'CBD_BLEND': 'CBD'
        };
        return map[(lineage || '').toUpperCase()] || '';
    },

    handleTagSelection(e, tag) {
        // Ignore changes during drag-and-drop reordering
        if (e.target.hasAttribute('data-reordering')) {
            console.log('Ignoring tag selection change during reordering');
            return;
        }
        
        const isChecked = e.target.checked;
        console.log('Tag selection changed:', tag['Product Name*'], 'checked:', isChecked);
        
        if (isChecked) {
            if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
        } else {
            const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
        }
        
        // Update the regular selectedTags set to match persistent ones
        this.state.selectedTags = new Set(this.state.persistentSelectedTags);
        
        console.log('Persistent selected tags after change:', this.state.persistentSelectedTags);
        
        // Update the selected tags display with ALL persistent selected tags
        const selectedTagObjects = this.state.persistentSelectedTags.map(name => {
            // First try to find in current tags (filtered view)
            let foundTag = this.state.tags.find(t => t['Product Name*'] === name);
            // If not found in current tags, try original tags
            if (!foundTag) {
                foundTag = this.state.originalTags.find(t => t['Product Name*'] === name);
            }
            return foundTag;
        }).filter(Boolean);
        
        this.updateSelectedTags(selectedTagObjects);
        
        // If tag was checked in available list, hide it from available display
        if (isChecked && e.target.closest('#availableTags')) {
            const tagElement = e.target.closest('.tag-item');
            if (tagElement) {
                tagElement.style.display = 'none';
            }
        }
        
        // If tag was unchecked in selected list, show it in available display
        if (!isChecked && e.target.closest('#selectedTags')) {
            // Find and show the tag in available list
            const availableTagElement = document.querySelector(`#availableTags .tag-checkbox[value="${tag['Product Name*']}"]`);
            if (availableTagElement) {
                const tagElement = availableTagElement.closest('.tag-item');
                if (tagElement) {
                    tagElement.style.display = 'block';
                }
            }
        }
    },

    updateTagLineage(tag, lineage) {
        // Update the lineage in the tag object
        tag.lineage = lineage;
        
        // Update the color based on the new lineage
        const newColor = this.getLineageColor(lineage);
        this.updateTagColor(tag, newColor);
    },

    handleLineageChange(tagName, newLineage) {
        const tag = this.state.tags.find(t => t['Product Name*'] === tagName);
        if (tag) {
            // Update the lineage in the tag object
            tag.lineage = newLineage;
            
            // Update the color based on the new lineage
            const newColor = this.getLineageColor(newLineage);
            this.updateTagColor(tag, newColor);
            
            // Send update to backend
            this.updateLineageOnBackend(tagName, newLineage);
        }
    },

    async updateLineageOnBackend(tagName, newLineage) {
        try {
            const payload = {
                tag_name: tagName,
                "Product Name*": tagName,
                lineage: newLineage
            };
            const response = await fetch('/api/update-lineage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update lineage');
            }

            // Update the tag in original tags as well
            const originalTag = this.state.originalTags.find(t => t['Product Name*'] === tagName);
            if (originalTag) {
                originalTag.lineage = newLineage;
            }

            // Update the tag in current tags list
            const currentTag = this.state.tags.find(t => t['Product Name*'] === tagName);
            if (currentTag) {
                currentTag.lineage = newLineage;
            }

            // Optimized: Only update the specific tag elements instead of rebuilding everything
            this.updateTagLineageInUI(tagName, newLineage);

            // Refresh available tags from backend to ensure UI shows updated lineage
            try {
                console.log('Refreshing available tags to show updated lineage...');
                await this.fetchAndUpdateAvailableTags();
                console.log('Available tags refreshed successfully');
            } catch (refreshError) {
                console.warn('Failed to refresh available tags:', refreshError);
                // Don't fail the lineage update if refresh fails
            }

        } catch (error) {
            console.error('Error updating lineage:', error);
            if (window.Toast) {
                console.error('Failed to update lineage:', error.message);
            }
        }
    },

    // Optimized function to update only the specific tag's lineage in the UI
    updateTagLineageInUI(tagName, newLineage) {
        // Update lineage badge in available tags
        const availableTagElement = document.querySelector(`#availableTags [data-tag-name="${tagName}"]`);
        if (availableTagElement) {
            const lineageBadge = availableTagElement.querySelector('.lineage-badge');
            if (lineageBadge) {
                lineageBadge.textContent = newLineage;
                lineageBadge.className = `badge lineage-badge ${this.getLineageColor(newLineage)}`;
            }
        }

        // Update lineage badge in selected tags
        const selectedTagElement = document.querySelector(`#selectedTags [data-tag-name="${tagName}"]`);
        if (selectedTagElement) {
            const lineageBadge = selectedTagElement.querySelector('.lineage-badge');
            if (lineageBadge) {
                lineageBadge.textContent = newLineage;
                lineageBadge.className = `badge lineage-badge ${this.getLineageColor(newLineage)}`;
            }
        }
    },

    updateSelectedTags(tags) {
        if (!tags || !Array.isArray(tags)) {
            console.warn('updateSelectedTags called with invalid tags:', tags);
            tags = [];
        }
        
        // Dispatch event to notify drag and drop manager that tag updates are starting
        document.dispatchEvent(new CustomEvent('updateSelectedTags'));
        
        console.time('updateSelectedTags');
        console.log('updateSelectedTags called with tags:', tags);
        const container = document.getElementById('selectedTags');
        if (!container) {
            console.error('Selected tags container not found');
            return;
        }

        // Clear existing content
        container.innerHTML = '';

        // For JSON matched items, we want to keep them even if they don't exist in Excel data
        // So we'll be more permissive with validation
        const validTags = [];
        const invalidTags = [];
        
        for (const tag of tags) {
            if (tag && tag['Product Name*']) {
                // Check if this tag exists in the original tags (Excel data)
                const existsInExcel = this.state.originalTags.some(excelTag => 
                    excelTag['Product Name*'] === tag['Product Name*']
                );
                
                if (existsInExcel) {
                    validTags.push(tag);
                } else {
                    // For JSON matched items, we'll keep them but mark them as "external"
                    console.log(`Tag not found in Excel data (likely JSON matched): ${tag['Product Name*']}`);
                    // Don't add to invalidTags - we'll keep these
                    validTags.push(tag);
                }
            }
        }

        // Update the regular selectedTags set to match persistent ones
        this.state.selectedTags = new Set(this.state.persistentSelectedTags);

        // Use all tags for display (including JSON matched ones)
        // IMPORTANT: For selected tags, we want to preserve the exact order from the backend
        // This is crucial for drag-and-drop reordering to work properly
        tags = validTags;
        
        // NOTE: We do NOT apply filtering to selected tags to preserve the order
        // The backend already returns the tags in the correct order, and we want to maintain that
        // Filtering is only applied to available tags, not selected tags
        console.log('Displaying selected tags in backend order (no filtering applied):', tags);
        
        // Store the select all containers before clearing
        const selectAllSelectedContainer = container.querySelector('.select-all-container');
        
        // Clear existing content but preserve the select all container
        container.innerHTML = '';
        
        // Re-add the select all container if it existed
        if (selectAllSelectedContainer) {
            container.appendChild(selectAllSelectedContainer);
        } else {
            // Create select all container if it doesn't exist
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'd-flex align-items-center gap-3 mb-2';
            selectAllContainer.innerHTML = `
                <label class="d-flex align-items-center gap-2 cursor-pointer mb-0 select-all-container">
                    <input type="checkbox" id="selectAllSelected" class="custom-checkbox">
                    <span class="text-secondary fw-semibold">SELECT ALL</span>
                </label>
            `;
            container.appendChild(selectAllContainer);
        }

        // Add global select all checkbox
        const topSelectAll = document.getElementById('selectAllSelected');
        if (topSelectAll && !topSelectAll.hasAttribute('data-listener-added')) {
            topSelectAll.setAttribute('data-listener-added', 'true');
            topSelectAll.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                const tagCheckboxes = document.querySelectorAll('#selectedTags .tag-checkbox');
                tagCheckboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                    if (tag) {
                        if (isChecked) {
                            if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                        } else {
                            const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                        }
                    }
                });
                // Update the regular selectedTags set to match persistent ones
                this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                
                this.updateSelectedTags(this.state.persistentSelectedTags.map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean));
                
                // Rebuild available tags display to reflect selection changes
                const updatedAvailableTags = this.state.originalTags.filter(tag => 
                    !this.state.persistentSelectedTags.includes(tag['Product Name*'])
                );
                this._updateAvailableTags(this.state.originalTags, updatedAvailableTags);
            });
        }

        // Handle new tags being passed in (e.g., from JSON matching)
        // Add new tags to persistentSelectedTags without clearing existing ones
        if (tags.length > 0) {
            console.log('Adding new tags to persistentSelectedTags:', tags);
            tags.forEach(tag => {
                if (tag && tag['Product Name*']) {
                    if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                        this.state.persistentSelectedTags.push(tag['Product Name*']);
                    }
                }
            });
            // Update the regular selectedTags set to match persistent ones
            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
        }

        // Use the tags passed from the backend to preserve the exact order
        // This is crucial for drag-and-drop reordering to work properly
        let fullTags = tags;
        
        // If backend returned tags, use them and update persistent state
        if (tags && tags.length > 0) {
            console.log('Using backend tags for display (preserving order):', fullTags);
            // Update persistentSelectedTags to match the backend order
            this.state.persistentSelectedTags = tags.map(tag => tag['Product Name*']);
            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
        } else {
            // If no backend tags, use persistent tags from frontend state
            console.log('No backend tags, using persistent frontend tags');
            
            // Safety check: ensure persistentSelectedTags is an array
            if (!Array.isArray(this.state.persistentSelectedTags)) {
                console.warn('persistentSelectedTags is not an array, initializing as empty array');
                this.state.persistentSelectedTags = [];
            }
            
            fullTags = this.state.persistentSelectedTags.map(name => {
                // First try to find in current tags (filtered view)
                let foundTag = this.state.tags.find(t => t['Product Name*'] === name);
                // If not found in current tags, try original tags
                if (!foundTag) {
                    foundTag = this.state.originalTags.find(t => t['Product Name*'] === name);
                }
                // If still not found, create a minimal tag object (for JSON matched items)
                if (!foundTag) {
                    console.warn(`Tag not found in state: ${name}, creating minimal tag object`);
                    foundTag = {
                        'Product Name*': name,
                        'Product Brand': 'Unknown',
                        'Vendor': 'Unknown',
                        'Product Type*': 'Unknown',
                        'Lineage': 'MIXED'
                    };
                }
                return foundTag;
            }).filter(Boolean);
        }
        
        // If no tags, just return
        if (!fullTags || fullTags.length === 0) {
            console.log('No tags to display in selected tags');
            this.updateTagCount('selected', 0);
            console.timeEnd('updateSelectedTags');
            return;
        }

        // Organize tags into hierarchical groups
        const groupedTags = this.organizeBrandCategories(fullTags);
        console.log('Grouped tags:', groupedTags);

        // Sort vendors alphabetically
        const sortedVendors = Array.from(groupedTags.entries())
            .sort(([a], [b]) => (a || '').localeCompare(b || ''));

        // Create vendor sections
        sortedVendors.forEach(([vendor, brandGroups]) => {
            console.log('Processing vendor:', vendor, 'with brand groups:', brandGroups);
            
            const vendorSection = document.createElement('div');
            vendorSection.className = 'vendor-section mb-3';
            
            // Remove vendor label
            // Create vendor header with integrated checkbox
            const vendorHeader = document.createElement('h5');
            vendorHeader.className = 'vendor-header mb-2 d-flex align-items-center';
            
            const vendorCheckbox = document.createElement('input');
            vendorCheckbox.type = 'checkbox';
            vendorCheckbox.className = 'select-all-checkbox me-2';
            vendorCheckbox.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                // Select all descendant checkboxes (including subcategories and tags)
                const checkboxes = vendorSection.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                    // Only update persistentSelectedTags for tag-checkboxes
                    if (checkbox.classList.contains('tag-checkbox')) {
                        const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                        if (tag) {
                            if (isChecked) {
                                if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                            } else {
                                const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                            }
                        }
                    }
                });
                // Update the regular selectedTags set to match persistent ones
                this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                
                this.updateSelectedTags(Array.from(this.state.persistentSelectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean));
                
                // Rebuild available tags display to reflect selection changes
                const updatedAvailableTags = this.state.originalTags.filter(tag => 
                    !this.state.persistentSelectedTags.includes(tag['Product Name*'])
                );
                this._updateAvailableTags(this.state.originalTags, updatedAvailableTags);
            });
            
            vendorHeader.appendChild(vendorCheckbox);
            vendorHeader.appendChild(document.createTextNode(vendor));
            vendorSection.appendChild(vendorHeader);

            // Create brand sections
            const sortedBrands = Array.from(brandGroups.entries())
                .sort(([a], [b]) => (a || '').localeCompare(b || ''));

            sortedBrands.forEach(([brand, productTypeGroups]) => {
                const brandSection = document.createElement('div');
                brandSection.className = 'brand-section ms-3 mb-2';
                
                // Remove brand label
                // Create brand header with integrated checkbox
                const brandHeader = document.createElement('h6');
                brandHeader.className = 'brand-header mb-2 d-flex align-items-center';
                
                const brandCheckbox = document.createElement('input');
                brandCheckbox.type = 'checkbox';
                brandCheckbox.className = 'select-all-checkbox me-2';
                brandCheckbox.addEventListener('change', (e) => {
                    const isChecked = e.target.checked;
                    // Select all descendant checkboxes (including subcategories and tags)
                    const checkboxes = brandSection.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = isChecked;
                        // Only update persistentSelectedTags for tag-checkboxes
                        if (checkbox.classList.contains('tag-checkbox')) {
                            const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                            if (tag) {
                                if (isChecked) {
                                    if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                                } else {
                                    const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                                }
                            }
                        }
                    });
                    // Update the regular selectedTags set to match persistent ones
                    this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                    
                    this.updateSelectedTags(Array.from(this.state.persistentSelectedTags).map(name =>
                        this.state.tags.find(t => t['Product Name*'] === name)
                    ).filter(Boolean));
                });
                
                brandHeader.appendChild(brandCheckbox);
                brandHeader.appendChild(document.createTextNode(brand));
                brandSection.appendChild(brandHeader);

                // Create product type sections
                const sortedProductTypes = Array.from(productTypeGroups.entries())
                    .sort(([a], [b]) => (a || '').localeCompare(b || ''));

                sortedProductTypes.forEach(([productType, weightGroups]) => {
                    const productTypeSection = document.createElement('div');
                    productTypeSection.className = 'product-type-section ms-3 mb-2';
                    
                    // Remove type label
                    // Create product type header
                    const typeHeader = document.createElement('div');
                    typeHeader.className = 'product-type-header mb-2 d-flex align-items-center';
                    
                    const productTypeCheckbox = document.createElement('input');
                    productTypeCheckbox.type = 'checkbox';
                    productTypeCheckbox.className = 'select-all-checkbox me-2';
                    productTypeCheckbox.addEventListener('change', (e) => {
                        const isChecked = e.target.checked;
                        // Select all descendant checkboxes (including subcategories and tags)
                        const checkboxes = productTypeSection.querySelectorAll('input[type="checkbox"]');
                        checkboxes.forEach(checkbox => {
                            checkbox.checked = isChecked;
                            // Only update persistentSelectedTags for tag-checkboxes
                            if (checkbox.classList.contains('tag-checkbox')) {
                                const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                if (tag) {
                                    if (isChecked) {
                                        if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                                    } else {
                                        const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                                    }
                                }
                            }
                        });
                        // Update the regular selectedTags set to match persistent ones
                        this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                        
                        this.updateSelectedTags(Array.from(this.state.persistentSelectedTags).map(name =>
                            this.state.tags.find(t => t['Product Name*'] === name)
                        ).filter(Boolean));
                    });
                    
                    typeHeader.appendChild(productTypeCheckbox);
                    typeHeader.appendChild(document.createTextNode(productType));
                    productTypeSection.appendChild(typeHeader);

                    // Create weight sections
                    const sortedWeights = Array.from(weightGroups.entries())
                        .sort(([a], [b]) => (a || '').localeCompare(b || ''));

                    sortedWeights.forEach(([weight, tags]) => {
                        const weightSection = document.createElement('div');
                        weightSection.className = 'weight-section ms-3 mb-1';
                        
                        // Remove weight label
                        // Create weight header
                        const weightHeader = document.createElement('div');
                        weightHeader.className = 'weight-header mb-1 d-flex align-items-center';
                        
                        const weightCheckbox = document.createElement('input');
                        weightCheckbox.type = 'checkbox';
                        weightCheckbox.className = 'select-all-checkbox me-2';
                        weightCheckbox.addEventListener('change', (e) => {
                            const isChecked = e.target.checked;
                            // Select all descendant checkboxes (including subcategories and tags)
                            const checkboxes = weightSection.querySelectorAll('input[type="checkbox"]');
                            checkboxes.forEach(checkbox => {
                                checkbox.checked = isChecked;
                                // Only update persistentSelectedTags for tag-checkboxes
                                if (checkbox.classList.contains('tag-checkbox')) {
                                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                    if (tag) {
                                        if (isChecked) {
                                            if (!this.state.persistentSelectedTags.includes(tag['Product Name*'])) {
                                this.state.persistentSelectedTags.push(tag['Product Name*']);
                            };
                                        } else {
                                            const index = this.state.persistentSelectedTags.indexOf(tag['Product Name*']);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
                                        }
                                    }
                                }
                            });
                            // Update the regular selectedTags set to match persistent ones
                            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
                            
                            // Update the selected tags display
                            const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                                this.state.tags.find(t => t['Product Name*'] === name)
                            ).filter(Boolean);
                            this.updateSelectedTags(selectedTagObjects);
                            
                            // Use efficient update instead of rebuilding entire DOM
                            this.efficientlyUpdateAvailableTagsDisplay();
                        });
                        
                        weightHeader.appendChild(weightCheckbox);
                        weightHeader.appendChild(document.createTextNode(weight));
                        weightSection.appendChild(weightHeader);
                        
                        // Always render tags as leaf nodes - sort alphabetically by product name
                        if (tags && tags.length > 0) {
                            // Sort tags alphabetically by product name
                            const sortedTags = tags.sort((a, b) => {
                                const nameA = (a['Product Name*'] || a.ProductName || a.Description || '').toLowerCase();
                                const nameB = (b['Product Name*'] || b.ProductName || b.Description || '').toLowerCase();
                                return nameA.localeCompare(nameB);
                            });
                            
                            sortedTags.forEach(tag => {
                                const tagElement = this.createTagElement(tag, true); // true = isForSelectedTags
                                tagElement.querySelector('.tag-checkbox').checked = this.state.persistentSelectedTags.includes(tag['Product Name*']);
                                weightSection.appendChild(tagElement);
                            });
                        }
                        productTypeSection.appendChild(weightSection);
                    });

                    brandSection.appendChild(productTypeSection);
                });

                vendorSection.appendChild(brandSection);
            });

            container.appendChild(vendorSection);
        });

        this.updateTagCount('selected', fullTags.length);
        console.timeEnd('updateSelectedTags');

        // After rendering, update all select-all checkboxes to reflect the state of their descendant tag checkboxes
        // Helper to set select-all checkbox state
        function updateSelectAllCheckboxState(section) {
            const selectAll = section.querySelector('.select-all-checkbox');
            if (!selectAll) return;
            const tagCheckboxes = section.querySelectorAll('.tag-checkbox');
            if (tagCheckboxes.length === 0) {
                selectAll.checked = false;
                selectAll.indeterminate = false;
                return;
            }
            const checkedCount = Array.from(tagCheckboxes).filter(cb => cb.checked).length;
            if (checkedCount === tagCheckboxes.length) {
                selectAll.checked = true;
                selectAll.indeterminate = false;
            } else if (checkedCount === 0) {
                selectAll.checked = false;
                selectAll.indeterminate = false;
            } else {
                selectAll.checked = false;
                selectAll.indeterminate = true;
            }
        }
        // Update all group-level select all checkboxes
        container.querySelectorAll('.vendor-section, .brand-section, .product-type-section, .weight-section').forEach(section => {
            updateSelectAllCheckboxState(section);
        });
        // Update the top-level select all
        updateSelectAllCheckboxState(container);
        
        // Dispatch event to notify drag and drop manager that tag updates are complete
        document.dispatchEvent(new CustomEvent('updateSelectedTagsComplete'));
    },

    updateTagCount(type, count) {
        const countElement = document.getElementById(`${type}TagsCount`);
        if (countElement) {
            countElement.textContent = `(${count})`;
        }
    },

    addCheckboxListeners(containerId) {
        document.querySelectorAll(`${containerId} input[type="checkbox"]`).forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                if (this.checked) {
                    if (!TagManager.state.persistentSelectedTags.includes(this.value)) {
                    TagManager.state.persistentSelectedTags.push(this.value);
                };
                } else {
                    const index = TagManager.state.persistentSelectedTags.indexOf(this.value);
                if (index > -1) {
                    TagManager.state.persistentSelectedTags.splice(index, 1);
                };
                }
                // Update the regular selectedTags set to match persistent ones
                TagManager.state.selectedTags = new Set(TagManager.state.persistentSelectedTags);
                TagManager.updateTagCheckboxes();
            });
        });
    },

    updateTagCheckboxes() {
        // Update available tags checkboxes
        document.querySelectorAll('#availableTags input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = TagManager.state.persistentSelectedTags.includes(checkbox.value);
        });
    },

    async fetchAndUpdateAvailableTags() {
        try {
            console.log('Fetching available tags...');
            const timestamp = Date.now();
            const response = await fetch(`/api/available-tags?t=${timestamp}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const tags = await response.json();
            
            if (!tags || !Array.isArray(tags) || tags.length === 0) {
                console.error('No tags loaded from backend or invalid response format');
                return false;
            }
            
            console.log(`Fetched ${tags.length} available tags`);
            
            // Debug: Check lineage data for first few tags
            console.log('Sample lineage data:');
            tags.slice(0, 5).forEach(tag => {
                console.log(`  ${tag['Product Name*']}: lineage=${tag.lineage}, Lineage=${tag.Lineage}`);
            });
            
            this.state.tags = tags;
            this.state.originalTags = [...tags]; // Store original tags for validation
            
            // Only validate selected tags if we don't have JSON matched tags
            // This prevents clearing tags that were just added via JSON matching
            if (this.state.persistentSelectedTags.length === 0) {
                this.validateSelectedTags();
            } else {
                console.log('Skipping selected tags validation to preserve JSON matched tags');
            }
            
            this._updateAvailableTags(tags);
            return true;
        } catch (error) {
            console.error('Error fetching available tags:', error);
            return false;
        }
    },

    async fetchAndUpdateSelectedTags() {
        try {
            console.log('Fetching selected tags...');
            const timestamp = Date.now();
            const response = await fetch(`/api/selected-tags?t=${timestamp}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const selectedTags = await response.json();
            
            if (!selectedTags || !Array.isArray(selectedTags)) {
                console.warn('No selected tags found - data may not be loaded yet');
                this.updateSelectedTags([]);
                return true;
            }
            
            console.log(`Fetched ${selectedTags.length} selected tags:`, selectedTags.map(tag => tag['Product Name*']));
            this.updateSelectedTags(selectedTags);
            return true;
        } catch (error) {
            console.error('Error fetching selected tags:', error);
            this.updateSelectedTags([]);
            return false;
        }
    },

    async fetchAndPopulateFilters() {
        try {
            // Use the filter options API with cache refresh and timestamp to ensure updated weight formatting
            const timestamp = Date.now();
            const response = await fetch(`/api/filter-options?refresh=true&t=${timestamp}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                throw new Error('Failed to fetch filter options');
            }
            const filterOptions = await response.json();
            console.log('Fetched filter options:', filterOptions);
            this.updateFilters(filterOptions);
        } catch (error) {
            console.error('Error fetching filter options:', error);
            alert('Failed to load filter options');
        }
    },

    async downloadExcel() {
        // Collect filter values from dropdowns (adjust IDs as needed)
        const filters = {
            vendor: document.getElementById('vendorFilter')?.value || null,
            brand: document.getElementById('brandFilter')?.value || null,
            productType: document.getElementById('productTypeFilter')?.value || null,
            lineage: document.getElementById('lineageFilter')?.value || null,
            weight: document.getElementById('weightFilter')?.value || null,
        };

        // Remove null/empty values
        Object.keys(filters).forEach(key => {
            if (!filters[key] || filters[key] === '') {
                delete filters[key];
            }
        });

        // Collect selected tags from the persistent selected tags
        const allTags = Array.from(this.state.persistentSelectedTags);

        try {
            const response = await fetch('/api/download-processed-excel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filters,
                    selected_tags: allTags
                })
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to download Excel');
            }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            // Let the server set the filename via Content-Disposition header
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading Excel:', error);
            alert(error.message || 'Failed to download Excel');
        }
    },

    // Initialize the tag manager
    init() {
        console.log('TagManager initialized');
        
        // Show application splash screen
        AppLoadingSplash.show();
        AppLoadingSplash.startAutoAdvance();
        
        // Initialize empty state first
        this.initializeEmptyState();
        AppLoadingSplash.nextStep(); // Templates loaded
        
        // Check if there's already data loaded (e.g., from a previous session or default file)
        this.checkForExistingData();
        
        // Ensure all filters default to 'All' on page load
        this.state.filters = {
            vendor: 'All',
            brand: 'All',
            productType: 'All',
            lineage: 'All',
            weight: 'All'
        };
        // Set each filter dropdown to 'All' (or '')
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter', 'dohFilter', 'highCbdFilter'];
        filterIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        // Show all tags by default
        this.applyFilters();
        
        // Add filter change event listeners for cascading filters after filters are populated
        setTimeout(() => {
            this.setupFilterEventListeners();
        }, 500);
        
        // Add search event listeners
        this.setupSearchEventListeners();
        
        // Update table header if TagsTable is available
        setTimeout(() => {
            // Also update table header if TagsTable is available
            if (typeof TagsTable !== 'undefined' && TagsTable.updateTableHeader) {
                TagsTable.updateTableHeader();
            }
        }, 100);

        // Initialize drag and drop manager
        setTimeout(() => {
            if (window.dragAndDropManager) {
                window.dragAndDropManager.setupTagDragAndDrop();
            }
        }, 200);

        // JSON matching is now handled by the modal - removed old above-tags-list logic
    },

    // Show a simple loading indicator
    showLoadingIndicator() {
        const availableTagsContainer = document.getElementById('availableTags');
        if (availableTagsContainer) {
            availableTagsContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2 text-muted">Loading product data...</p>
                </div>
            `;
        }
    },

    // Hide loading indicator
    hideLoadingIndicator() {
        const availableTagsContainer = document.getElementById('availableTags');
        if (availableTagsContainer) {
            // Check if we have any tags loaded
            if (this.state.tags && this.state.tags.length > 0) {
                // Data is loaded, no need to show upload prompt
                return;
            }
            
            // No data loaded, show upload prompt
            availableTagsContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="upload-prompt">
                        <i class="fas fa-cloud-upload-alt fa-3x text-muted mb-3"></i>
                        <h5 class="text-muted">No product data loaded</h5>
                        <p class="text-muted">Upload an Excel file to get started</p>
                        <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">
                            <i class="fas fa-upload me-2"></i>Upload Excel File
                        </button>
                    </div>
                </div>
            `;
        }
    },

    // Initialize with empty state to prevent undefined errors
    initializeEmptyState() {
        console.log('Initializing empty state...');
        
        // Initialize with empty arrays to prevent undefined errors
        this.state.tags = [];
        this.state.originalTags = [];
        this.state.selectedTags = new Set();
        this.state.persistentSelectedTags = []; // Changed from Set to Array to preserve order
        
        // Clear any persistent storage
        if (window.localStorage) {
            localStorage.removeItem('selectedTags');
            localStorage.removeItem('selected_tags');
        }
        if (window.sessionStorage) {
            sessionStorage.removeItem('selectedTags');
            sessionStorage.removeItem('selected_tags');
        }
        
        // Update UI with empty state
        this.debouncedUpdateAvailableTags([], null);
        this.updateSelectedTags([]);
        
        // Initialize filters with empty options
        const emptyFilters = {
            vendor: [],
            brand: [],
            productType: [],
            lineage: [],
            weight: []
        };
        this.updateFilters(emptyFilters);
        
        console.log('Empty state initialized');
    },

    // Check if there's existing data and load it
    async checkForExistingData() {
        console.log('Checking for existing data...');
        
        try {
            // Use the new initial-data endpoint for faster loading
            const response = await fetch('/api/initial-data');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.available_tags && Array.isArray(data.available_tags) && data.available_tags.length > 0) {
                    console.log(`Found ${data.available_tags.length} existing tags, loading data...`);
                    
                    // Update splash progress for data loading
                    AppLoadingSplash.updateProgress(60, 'Loading product data...');
                    
                    // Show action splash for initial tag population
                    this.showActionSplash('Loading product tags...');
                    
                    // Update available tags
                    AppLoadingSplash.updateProgress(75, 'Processing tags...');
                    this.debouncedUpdateAvailableTags(data.available_tags, null);
                    
                    // Don't restore selected tags on page reload - start with empty selection
                    AppLoadingSplash.updateProgress(85, 'Initializing selections...');
                    this.state.persistentSelectedTags = [];
                    this.state.selectedTags = new Set();
                    this.updateSelectedTags([]);
                    
                    // Update filters
                    AppLoadingSplash.updateProgress(90, 'Setting up filters...');
                    this.updateFilters(data.filters || {
                        vendor: [],
                        brand: [],
                        productType: [],
                        lineage: [],
                        weight: []
                    });
                    
                    // Update file info text to show the loaded filename
                    if (data.filename) {
                        const fileInfoText = document.getElementById('fileInfoText');
                        if (fileInfoText) {
                            fileInfoText.textContent = data.filename;
                        }
                    }
                    
                    // Complete splash loading
                    AppLoadingSplash.stopAutoAdvance();
                    AppLoadingSplash.complete();
                    
                    // Hide action splash after a short delay to ensure smooth transition
                    setTimeout(() => {
                        this.hideActionSplash();
                    }, 200);
                    
                    console.log('Initial data loaded successfully');
                    return;
                } else {
                    console.log('No initial data available:', data.message || 'No data found');
                    // Complete splash loading even if no data
                    AppLoadingSplash.stopAutoAdvance();
                    AppLoadingSplash.complete();
                }
            }
        } catch (error) {
            console.log('Error loading initial data:', error.message);
            // Complete splash loading on error
            AppLoadingSplash.stopAutoAdvance();
            AppLoadingSplash.complete();
        }
        
        console.log('No existing data found, waiting for file upload...');
        // Complete splash loading if no data found
        AppLoadingSplash.stopAutoAdvance();
        AppLoadingSplash.complete();
    },

    // Debounced version of the label generation logic
    debouncedGenerate: debounce(async function() {
        // Check if tags are loaded before attempting generation
        if (!this.state.tags || !Array.isArray(this.state.tags) || this.state.tags.length === 0) {
            console.error('Cannot generate: No tags loaded. Please upload a file first.');
            return;
        }
        
        console.time('debouncedGenerate');
        const generateBtn = document.getElementById('generateBtn');
        const splashModal = document.getElementById('generationSplashModal');
        const splashCanvas = document.getElementById('generation-splash-canvas');
        
        // Add generation lock to prevent multiple simultaneous requests
        if (this.isGenerating) {
            console.log('Generation already in progress, ignoring duplicate request');
            return;
        }
        this.isGenerating = true;
        
        try {
            // Get checked tags from the DOM in the correct visual order
            const container = document.querySelector('#selectedTags');
            let checkedTags = [];
            
            if (container) {
                // Walk through the DOM tree in visual order to collect tags
                const walkDOMInOrder = (element) => {
                    const children = Array.from(element.children);
                    for (const child of children) {
                        // If this child is a tag-row, collect its checkbox value
                        if (child.classList.contains('tag-row')) {
                            const checkbox = child.querySelector('.tag-checkbox');
                            if (checkbox && checkbox.value && checkbox.checked) {
                                checkedTags.push(checkbox.value);
                            }
                        } else {
                            // Recursively walk through child elements
                            walkDOMInOrder(child);
                        }
                    }
                };
                
                walkDOMInOrder(container);
            } else {
                // Fallback to persistent selected tags if DOM is not available
                checkedTags = [...this.state.persistentSelectedTags];
            }
            
            console.log('Generation request - DOM order collected:', checkedTags);
            console.log('Generation request - persistentSelectedTags fallback:', Array.from(this.state.persistentSelectedTags));
            if (checkedTags.length === 0) {
                console.error('Please select at least one tag to generate');
                return;
            }
            
            // Get template, scale, and format info
            const templateType = document.getElementById('templateSelect')?.value || 'horizontal';
            const scaleFactor = parseFloat(document.getElementById('scaleInput')?.value) || 1.0;
            
            // Show enhanced generation splash
            this.showEnhancedGenerationSplash(checkedTags.length, templateType);
            
            // Disable button and show loading spinner
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
            // Always use DOCX generation
            const apiEndpoint = '/api/generate';
            
            const response = await fetch(apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_tags: checkedTags,
                    template_type: templateType,
                    scale_factor: scaleFactor
                })
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to generate labels');
            }
            const blob = await response.blob();
            
            // Extract filename from Content-Disposition header
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'labels.docx'; // Default filename
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                }
            }
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename; // Set the filename for download
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error generating labels:', error);
        } finally {
            // Hide enhanced generation splash
            this.hideEnhancedGenerationSplash();
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate Tags';
            this.isGenerating = false; // Release generation lock
            console.timeEnd('debouncedGenerate');
        }
    }, 2000), // 2-second debounce delay

    updateTagColor(tag, color) {
        const tagElement = document.querySelector(`[data-tag-id="${tag.id}"]`);
        if (tagElement) {
            // Update the color in the tag object
            tag.color = color;
            
            // Update the color in the UI
            tagElement.style.backgroundColor = color;
            
            // Update the color in the tag list
            const tagListItem = document.querySelector(`[data-tag-id="${tag.id}"]`);
            if (tagListItem) {
                tagListItem.style.backgroundColor = color;
            }
            
            // Update the color in the tag editor if it's open
            const tagEditor = document.getElementById('tagEditor');
            if (tagEditor && tagEditor.dataset.tagId === tag.id) {
                const colorInput = tagEditor.querySelector('#tagColor');
                if (colorInput) {
                    colorInput.value = color;
                }
            }
        }
    },

    getLineageColor(lineage) {
        return this.state.lineageColors[lineage] || 'var(--lineage-mixed)';
    },

    async moveToSelected() {
        // Get checked tags in availableTags
        const checked = Array.from(document.querySelectorAll('#availableTags input[type="checkbox"].tag-checkbox:checked')).map(cb => cb.value);
        if (checked.length === 0) {
            console.error('No tags selected to move');
            return;
        }
        
        try {
            // Show action splash for better UX
            this.showActionSplash('Moving tags to selected...');
            
            // Add tags to persistent selected tags (independent of filters)
            checked.forEach(tagName => {
                if (!this.state.persistentSelectedTags.includes(tagName)) {
                                this.state.persistentSelectedTags.push(tagName);
                            };
            });
            
            // Update the regular selectedTags set to match persistent ones
            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
            
            // Get the full tag objects for the selected tags
            const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                this.state.tags.find(t => t['Product Name*'] === name)
            ).filter(Boolean);
            
            // Update the selected tags display
            this.updateSelectedTags(selectedTagObjects);
            
            // Hide selected tags from available tags display for better performance
            checked.forEach(tagName => {
                const tagElement = document.querySelector(`#availableTags .tag-checkbox[value="${tagName}"]`);
                if (tagElement) {
                    const tagItem = tagElement.closest('.tag-item');
                    if (tagItem) {
                        tagItem.style.display = 'none';
                    }
                }
            });
            
            // Successfully moved tags to selected
            console.log(`Moved ${checked.length} tags to selected list. Total selected: ${this.state.persistentSelectedTags.length}`);
        } catch (error) {
            console.error('Failed to move tags:', error.message);
        } finally {
            // Hide action splash
            setTimeout(() => {
                this.hideActionSplash();
            }, 300);
        }
    },

    async moveToAvailable() {
        // Get checked tags in selectedTags
        const checked = Array.from(document.querySelectorAll('#selectedTags input[type="checkbox"].tag-checkbox:checked')).map(cb => cb.value);
        if (checked.length === 0) {
            console.error('No tags selected to move');
            return;
        }
        
        try {
            // Show action splash for better UX
            this.showActionSplash('Moving tags to available...');
            
            // Remove tags from persistent selected tags
            checked.forEach(tagName => {
                const index = this.state.persistentSelectedTags.indexOf(tagName);
                            if (index > -1) {
                                this.state.persistentSelectedTags.splice(index, 1);
                            };
            });
            
            // Update the regular selectedTags set to match persistent ones
            this.state.selectedTags = new Set(this.state.persistentSelectedTags);
            
            // Get the full tag objects for the remaining selected tags
            const selectedTagObjects = Array.from(this.state.persistentSelectedTags).map(name =>
                this.state.tags.find(t => t['Product Name*'] === name)
            ).filter(Boolean);
            
            // Update the selected tags display
            this.updateSelectedTags(selectedTagObjects);
            
            // Get the tag objects for the moved back tags and add them to available tags
            const movedBackTags = checked.map(tagName => 
                this.state.originalTags.find(t => t['Product Name*'] === tagName)
            ).filter(Boolean);
            
            // Show moved back tags in available tags display for better performance
            checked.forEach(tagName => {
                const tagElement = document.querySelector(`#availableTags .tag-checkbox[value="${tagName}"]`);
                if (tagElement) {
                    const tagItem = tagElement.closest('.tag-item');
                    if (tagItem) {
                        tagItem.style.display = 'block';
                    }
                }
            });
            
            // Successfully moved tags to available
            console.log(`Moved ${checked.length} tags to available list. Total selected: ${this.state.persistentSelectedTags.length}`);
        } catch (error) {
            console.error('Failed to move tags:', error.message);
        } finally {
            // Hide action splash
            setTimeout(() => {
                this.hideActionSplash();
            }, 300);
        }
    },

    // Helper functions removed - now using _updateAvailableTags for proper tag management

    async undoMove() {
        try {
            // Show loading splash
            this.showActionSplash('Undoing last action...');
            
            // Call the backend API to undo the last move
            const response = await fetch('/api/undo-move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    // Update the persistent selected tags with the restored state
                    this.state.persistentSelectedTags = data.selected_tags;
                    this.state.selectedTags = new Set(data.selected_tags);
                    
                    // Update the selected tags display immediately
                    this.updateSelectedTags(data.selected_tags.map(tagName => 
                        this.state.tags.find(t => t['Product Name*'] === tagName)
                    ).filter(Boolean));
                    
                    // Update available tags with optimized approach
                    this.updateAvailableTagsOptimized(data.available_tags);
                    
                    console.log('Undo completed - restored previous state');
                } else {
                    console.error('Failed to undo move:', data.error);
                }
            } else {
                const errorData = await response.json();
                if (response.status === 400 && errorData.error === 'Nothing to undo') {
                    console.log('Nothing to undo');
                } else {
                    console.error('Failed to undo move on server:', errorData.error);
                }
            }
        } catch (error) {
            console.error('Failed to undo move:', error.message);
        } finally {
            // Hide loading splash
            this.hideActionSplash();
        }
    },

    async clearSelected() {
        try {
            // Show loading splash
            this.showActionSplash('Clearing selected tags...');
            
            // Call the backend API to clear selected tags
            const response = await fetch('/api/clear-filters', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Clear persistent selected tags
                this.state.persistentSelectedTags = [];
                this.state.selectedTags.clear();
                
                // Update the selected tags display immediately
                this.updateSelectedTags([]);
                
                // Use efficient DOM update instead of rebuilding entire structure
                this.efficientlyUpdateAvailableTagsDisplay();
                
                console.log('Cleared all selected tags');
            } else {
                console.error('Failed to clear selected tags on server');
            }
        } catch (error) {
            console.error('Failed to clear selected tags:', error.message);
        } finally {
            // Hide loading splash
            this.hideActionSplash();
        }
    },

    showExcelLoadingSplash(filename) {
        const splash = document.getElementById('excelLoadingSplash');
        const filenameElement = document.getElementById('excelLoadingFilename');
        const statusElement = document.getElementById('excelLoadingStatus');
        const progressFill = document.getElementById('excelLoadingFill');
        
        if (splash && filenameElement && statusElement && progressFill) {
            filenameElement.textContent = filename;
            statusElement.textContent = 'Initializing...';
            progressFill.style.width = '0%';
            splash.style.display = 'flex';
            
            // Start progress animation
            this.excelLoadingProgress = 0;
            this.excelLoadingInterval = setInterval(() => {
                this.excelLoadingProgress += Math.random() * 15;
                if (this.excelLoadingProgress > 90) {
                    this.excelLoadingProgress = 90; // Don't go to 100% until actually done
                }
                progressFill.style.width = this.excelLoadingProgress + '%';
            }, 500);
        }
    },

    hideExcelLoadingSplash() {
        const splash = document.getElementById('excelLoadingSplash');
        const progressFill = document.getElementById('excelLoadingFill');
        
        if (splash && progressFill) {
            // Complete the progress bar
            progressFill.style.width = '100%';
            
            // Clear the progress interval
            if (this.excelLoadingInterval) {
                clearInterval(this.excelLoadingInterval);
                this.excelLoadingInterval = null;
            }
            
            // Hide splash after a short delay
            setTimeout(() => {
                splash.style.display = 'none';
                progressFill.style.width = '0%';
            }, 500);
        }
    },

    updateExcelLoadingStatus(status) {
        const statusElement = document.getElementById('excelLoadingStatus');
        if (statusElement) {
            statusElement.textContent = status;
        }
    },

    // Action splash screen for clear/undo operations
    showActionSplash(message) {
        // Create splash if it doesn't exist
        let splash = document.getElementById('actionSplash');
        if (!splash) {
            splash = document.createElement('div');
            splash.id = 'actionSplash';
            splash.className = 'action-splash';
            splash.innerHTML = `
                <div class="action-splash-content">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="action-splash-message">${message}</div>
                </div>
            `;
            document.body.appendChild(splash);
        } else {
            const messageElement = splash.querySelector('.action-splash-message');
            if (messageElement) {
                messageElement.textContent = message;
            }
        }
        
        splash.style.display = 'flex';
    },

    hideActionSplash() {
        const splash = document.getElementById('actionSplash');
        if (splash) {
            splash.style.display = 'none';
        }
    },

    showEnhancedGenerationSplash(labelCount, templateType, retryCount = 0) {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.showEnhancedGenerationSplash(labelCount, templateType, retryCount);
            });
            return;
        }
        
        const splashModal = document.getElementById('generationSplashModal');
        
        if (!splashModal) {
            console.error('Generation splash modal not found');
            return;
        }
        
        // Show the modal with loading splash style
        splashModal.style.display = 'flex';
        splashModal.innerHTML = `
            <div class="background-pattern"></div>
            
            <div id="splash-container" style="position: relative; width: 500px; height: 350px; border-radius: 24px; overflow: hidden; background: rgba(22, 33, 62, 0.95); border: 1px solid rgba(0, 212, 170, 0.2); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 212, 170, 0.1); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); z-index: 2;">
                <div class="splash-content" style="position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; color: white; text-align: center;">
                    <div class="logo-container" style="position: relative; margin-bottom: 20px;">
                        <div class="logo-icon" style="width: 60px; height: 60px; background: linear-gradient(135deg, #00d4aa, #0099cc); border-radius: 15px; display: flex; align-items: center; justify-content: center; font-size: 28px; box-shadow: 0 15px 35px rgba(0, 212, 170, 0.3), 0 0 0 1px rgba(0, 212, 170, 0.2); animation: logo-float 3s ease-in-out infinite; position: relative;">🏷️</div>
                    </div>
                    
                    <h1 class="app-title" style="font-size: 32px; font-weight: 800; margin-bottom: 8px; background: linear-gradient(135deg, #00d4aa, #ffffff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; letter-spacing: -0.5px; text-shadow: 0 2px 8px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.3), 0 1px 2px rgba(160,132,232,0.3), 0 0 20px rgba(160,132,232,0.2); filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));">AUTO GENERATING TAG DESIGNER</h1>
                    <p class="app-subtitle" style="font-size: 14px; font-weight: 600; opacity: 1; margin-bottom: 25px; letter-spacing: 1px; text-transform: uppercase; text-shadow: 0 2px 6px rgba(0,0,0,0.4), 0 3px 12px rgba(0,0,0,0.3), 0 1px 2px rgba(139,92,246,0.3), 0 0 15px rgba(139,92,246,0.2); filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));">Generating Labels...</p>
                    
                    <div class="loading-container" style="width: 100%; max-width: 300px; margin-bottom: 20px;">
                        <div class="loading-bar" style="width: 100%; height: 6px; background: rgba(255, 255, 255, 0.1); border-radius: 3px; overflow: hidden; margin-bottom: 15px; position: relative;">
                            <div class="loading-progress" style="height: 100%; background: linear-gradient(90deg, #00d4aa, #0099cc, #00d4aa); border-radius: 3px; animation: loading-animation 3s ease-in-out infinite; position: relative;"></div>
                        </div>
                        <div class="loading-text" style="font-size: 14px; font-weight: 500; opacity: 0.8; margin-bottom: 15px; transition: opacity 0.3s ease;">Template: ${templateType.toUpperCase()}</div>
                        <div class="loading-text" style="font-size: 14px; font-weight: 500; opacity: 0.8; margin-bottom: 15px; transition: opacity 0.3s ease;">Labels: ${labelCount}</div>
                    </div>
                    
                    <div class="loading-dots" style="display: flex; gap: 6px; justify-content: center; margin-bottom: 15px;">
                        <div class="dot" style="width: 6px; height: 6px; border-radius: 50%; background: rgba(0, 212, 170, 0.6); animation: dot-pulse 1.6s ease-in-out infinite both;"></div>
                        <div class="dot" style="width: 6px; height: 6px; border-radius: 50%; background: rgba(0, 212, 170, 0.6); animation: dot-pulse 1.6s ease-in-out infinite both; animation-delay: -0.16s;"></div>
                        <div class="dot" style="width: 6px; height: 6px; border-radius: 50%; background: rgba(0, 212, 170, 0.6); animation: dot-pulse 1.6s ease-in-out infinite both; animation-delay: -0.32s;"></div>
                    </div>
                    
                    <div class="features" style="display: flex; gap: 20px; margin-top: 10px;">
                        <div class="feature" style="text-align: center; opacity: 0.6;">
                            <div class="feature-icon" style="font-size: 16px; margin-bottom: 4px;">⚡</div>
                            <div class="feature-text" style="font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Fast</div>
                        </div>
                        <div class="feature" style="text-align: center; opacity: 0.6;">
                            <div class="feature-icon" style="font-size: 16px; margin-bottom: 4px;">🎯</div>
                            <div class="feature-text" style="font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Precise</div>
                        </div>
                        <div class="feature" style="text-align: center; opacity: 0.6;">
                            <div class="feature-icon" style="font-size: 16px; margin-bottom: 4px;">🛡️</div>
                            <div class="feature-text" style="font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">Reliable</div>
                        </div>
                    </div>
                </div>
                
                <div class="version-badge" style="position: absolute; top: 15px; right: 15px; background: rgba(0, 212, 170, 0.15); padding: 4px 8px; border-radius: 8px; font-size: 10px; font-weight: 600; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(0, 212, 170, 0.2); color: #00d4aa;">v2.0.0</div>
                <div class="status-indicator" style="position: absolute; top: 15px; left: 15px; display: flex; align-items: center; gap: 4px; background: rgba(0, 212, 170, 0.15); padding: 4px 8px; border-radius: 8px; font-size: 10px; font-weight: 600; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(0, 212, 170, 0.2); color: #00d4aa;">
                    <div class="status-dot" style="width: 4px; height: 4px; border-radius: 50%; background: #00d4aa; animation: status-pulse 2s ease-in-out infinite;"></div>
                    <span>Processing</span>
                </div>
                <button id="exitGenerationBtn" onclick="TagManager.hideEnhancedGenerationSplash()" style="position: absolute; bottom: 15px; right: 15px; background: rgba(220, 53, 69, 0.8); border: 1px solid rgba(220, 53, 69, 0.8); color: white; padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); box-shadow: 0 2px 8px rgba(220, 53, 69, 0.3);" onmouseover="this.style.background='rgba(220, 53, 69, 1)'; this.style.transform='scale(1.05)'" onmouseout="this.style.background='rgba(220, 53, 69, 0.8)'; this.style.transform='scale(1)'">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px;">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Exit
                </button>
            </div>
            
            <style>
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
                
                @keyframes logo-float {
                    0%, 100% { 
                        transform: translateY(0px) scale(1);
                    }
                    50% { 
                        transform: translateY(-6px) scale(1.02);
                    }
                }
                
                @keyframes loading-animation {
                    0% { width: 0%; }
                    50% { width: 100%; }
                    100% { width: 0%; }
                }
                
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
                
                @keyframes status-pulse {
                    0%, 100% { opacity: 0.5; }
                    50% { opacity: 1; }
                }
            </style>
        `;
        
        // Start animated loading text
        const loadingTexts = [
            'Preparing templates...',
            'Processing data...',
            'Generating labels...',
            'Finalizing output...'
        ];
        
        let textIndex = 0;
        const loadingTextElements = splashModal.querySelectorAll('.loading-text');
        
        function updateLoadingText() {
            if (loadingTextElements[1]) {
                loadingTextElements[1].style.opacity = '0';
                setTimeout(() => {
                    loadingTextElements[1].textContent = loadingTexts[textIndex];
                    loadingTextElements[1].style.opacity = '1';
                    textIndex = (textIndex + 1) % loadingTexts.length;
                }, 300);
            }
        }
        
        // Update text every 1.5 seconds
        this._loadingTextInterval = setInterval(updateLoadingText, 1500);
        updateLoadingText(); // Start immediately
    },

    hideEnhancedGenerationSplash() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.hideEnhancedGenerationSplash();
            });
            return;
        }
        
        // Clear the loading text interval
        if (this._loadingTextInterval) {
            clearInterval(this._loadingTextInterval);
            this._loadingTextInterval = null;
        }
        
        const splashModal = document.getElementById('generationSplashModal');
        if (splashModal) {
            splashModal.style.display = 'none';
            console.log('Generation splash hidden successfully');
        } else {
            console.warn('Generation splash modal not found when trying to hide');
        }
    },

    showSimpleGenerationSplash(labelCount, templateType) {
        const splashModal = document.getElementById('generationSplashModal');
        if (!splashModal) {
            console.error('Cannot show simple splash - modal not found');
            return;
        }
        
        // Show a simple text-based splash
        splashModal.style.display = 'flex';
        splashModal.innerHTML = `
            <div class="generation-splash-popup" style="background: rgba(22, 33, 62, 0.95); border-radius: 24px; padding: 40px; text-align: center; color: white; border: 1px solid rgba(0, 212, 170, 0.2); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(0, 212, 170, 0.1);">
                <h2 style="color: #00d4aa; margin-bottom: 20px;">AUTO GENERATING TAG DESIGNER</h2>
                <p style="margin-bottom: 15px;">Generating Labels...</p>
                <p style="margin-bottom: 15px;">Template: ${templateType.toUpperCase()}</p>
                <p style="margin-bottom: 20px;">Labels: ${labelCount}</p>
                <div style="margin: 20px 0;">
                    <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px;">
                        <div style="width: 100%; height: 100%; background: linear-gradient(90deg, #00d4aa, #0099cc); border-radius: 3px; animation: progress 2s ease-in-out infinite;"></div>
                    </div>
                </div>
                <button onclick="TagManager.hideEnhancedGenerationSplash()" style="background: rgba(220, 53, 69, 0.8); border: 1px solid rgba(220, 53, 69, 0.8); color: white; padding: 8px 16px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; margin-top: 15px;" onmouseover="this.style.background='rgba(220, 53, 69, 1)'; this.style.transform='scale(1.05)'" onmouseout="this.style.background='rgba(220, 53, 69, 0.8)'; this.style.transform='scale(1)'">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: middle;">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Exit Generation
                </button>
                <style>
                    @keyframes progress { 0% { width: 0%; } 50% { width: 100%; } 100% { width: 0%; } }
                </style>
            </div>
        `;
    },

    // Optimized version of updateAvailableTags that skips complex DOM manipulation
    updateAvailableTagsOptimized(availableTags) {
        if (!availableTags || !Array.isArray(availableTags)) {
            console.warn('updateAvailableTagsOptimized called with invalid availableTags:', availableTags);
            return;
        }
        
        console.time('updateAvailableTagsOptimized');
        
        // Show action splash for optimized tag updates
        this.showActionSplash('Updating tags...');
        
        // Use requestAnimationFrame for smooth performance
        requestAnimationFrame(() => {
            // Filter out selected tags from available tags for better UX
            const selectedTagNames = new Set(this.state.persistentSelectedTags);
            const filteredAvailableTags = availableTags.filter(tag => !selectedTagNames.has(tag['Product Name*']));
            
            // Update state with filtered tags
            this.state.tags = [...filteredAvailableTags];
            
            // Rebuild the available tags display with filtered tags
            this._updateAvailableTags(this.state.originalTags, filteredAvailableTags);
            
            console.timeEnd('updateAvailableTagsOptimized');
            
            // Hide splash after a short delay
            setTimeout(() => {
                this.hideActionSplash();
            }, 50);
        });
    },

    // Efficient helper to update available tags display without DOM rebuilding
    efficientlyUpdateAvailableTagsDisplay() {
        const selectedTagNames = new Set(this.state.persistentSelectedTags);
        const availableTagElements = document.querySelectorAll('#availableTags .tag-item');
        
        availableTagElements.forEach(tagElement => {
            const checkbox = tagElement.querySelector('.tag-checkbox');
            if (checkbox) {
                const tagName = checkbox.value;
                if (selectedTagNames.has(tagName)) {
                    tagElement.style.display = 'none';
                } else {
                    tagElement.style.display = 'block';
                }
            }
        });
        
        // Update select all checkbox states after hiding/showing tags
        this.updateSelectAllCheckboxes();
    },

    // Update select all checkboxes state
    updateSelectAllCheckboxes() {
        const availableCheckboxes = document.querySelectorAll('#availableTags .tag-checkbox:not([style*="display: none"])');
        const checkedCheckboxes = document.querySelectorAll('#availableTags .tag-checkbox:checked:not([style*="display: none"])');
        
        // Update global select all
        const selectAllAvailable = document.getElementById('selectAllAvailable');
        if (selectAllAvailable && availableCheckboxes.length > 0) {
            selectAllAvailable.checked = checkedCheckboxes.length === availableCheckboxes.length;
            selectAllAvailable.indeterminate = checkedCheckboxes.length > 0 && checkedCheckboxes.length < availableCheckboxes.length;
        }
        
        // Update vendor and brand select all checkboxes
        const vendorSections = document.querySelectorAll('#availableTags .vendor-section');
        vendorSections.forEach(vendorSection => {
            const vendorCheckboxes = vendorSection.querySelectorAll('.tag-checkbox:not([style*="display: none"])');
            const vendorChecked = vendorSection.querySelectorAll('.tag-checkbox:checked:not([style*="display: none"])');
            const vendorSelectAll = vendorSection.querySelector('.select-all-checkbox');
            
            if (vendorSelectAll && vendorCheckboxes.length > 0) {
                vendorSelectAll.checked = vendorChecked.length === vendorCheckboxes.length;
                vendorSelectAll.indeterminate = vendorChecked.length > 0 && vendorChecked.length < vendorCheckboxes.length;
            }
        });
        
        const brandSections = document.querySelectorAll('#availableTags .brand-section');
        brandSections.forEach(brandSection => {
            const brandCheckboxes = brandSection.querySelectorAll('.tag-checkbox:not([style*="display: none"])');
            const brandChecked = brandSection.querySelectorAll('.tag-checkbox:checked:not([style*="display: none"])');
            const brandSelectAll = brandSection.querySelector('.select-all-checkbox');
            
            if (brandSelectAll && brandCheckboxes.length > 0) {
                brandSelectAll.checked = brandChecked.length === brandCheckboxes.length;
                brandSelectAll.indeterminate = brandChecked.length > 0 && brandChecked.length < brandCheckboxes.length;
            }
        });
    },

    async uploadFile(file) {
        const maxRetries = 2;
        let retryCount = 0;
        
        while (retryCount <= maxRetries) {
            try {
                console.log(`Starting file upload (attempt ${retryCount + 1}):`, file.name, 'Size:', file.size, 'bytes');
                
                // Show Excel loading splash screen
                this.showExcelLoadingSplash(file.name);
                
                // Show loading state
                this.updateUploadUI(`Uploading ${file.name}...`);
                
                const formData = new FormData();
                formData.append('file', file);
                
                console.log('Sending upload request...');
                
                // Create AbortController for timeout
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
                
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                console.log('Upload response status:', response.status);
                
                let data;
                try {
                    data = await response.json();
                    console.log('Upload response data:', data);
                } catch (jsonError) {
                    console.error('Error parsing JSON response:', jsonError);
                    throw new Error('Invalid server response');
                }
                
                if (response.ok && data.filename) {
                    // Poll for processing status
                    this.updateUploadUI(`Processing ${file.name}...`);
                    await this.pollUploadStatusAndUpdateUI(data.filename, file.name);
                    return; // Success, exit retry loop
                } else if (response.ok) {
                    // Fallback for legacy response
                    this.updateUploadUI(file.name, 'File uploaded successfully', 'success');
                    // File uploaded successfully
                    return; // Success, exit retry loop
                } else {
                    console.error('Upload failed:', data.error);
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI('No file selected');
                    console.error('Upload failed:', data.error);
                    return; // Don't retry on server errors
                }
            } catch (error) {
                console.error(`Upload error (attempt ${retryCount + 1}):`, error);
                
                if (retryCount === maxRetries) {
                    // Final attempt failed
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI('No file selected');
                    let errorMessage = 'Upload failed';
                    if (error.name === 'AbortError') {
                        errorMessage = 'Upload timed out - please try again';
                    } else if (error.message.includes('Failed to fetch')) {
                        errorMessage = 'Network error - please check your connection';
                    } else if (error.message.includes('Invalid server response')) {
                        errorMessage = 'Server error - please try again';
                    } else if (error.message) {
                        errorMessage = error.message;
                    }
                    console.error('Upload error:', errorMessage);
                    return;
                } else {
                    // Retry after a short delay
                    console.log(`Retrying upload in 2 seconds... (${retryCount + 1}/${maxRetries})`);
                    this.updateUploadUI(`Retrying upload... (${retryCount + 1}/${maxRetries})`);
                    await new Promise(resolve => setTimeout(resolve, 2000));
                }
            }
            
            retryCount++;
        }
    },

    async pollUploadStatusAndUpdateUI(filename, displayName) {
        console.log(`Polling upload status for: ${filename}`);
        
        const maxAttempts = 120; // 6 minutes max (3 seconds * 120 = 6 minutes)
        let attempts = 0;
        let consecutiveErrors = 0;
        const maxConsecutiveErrors = 3;
        
        // Add debug logging for upload processing
        console.log(`[UPLOAD DEBUG] Starting status polling for: ${filename}`);
        
        while (attempts < maxAttempts) {
            try {
                const response = await fetch(`/api/upload-status?filename=${encodeURIComponent(filename)}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                const status = data.status;
                const age = data.age_seconds || 0;
                const totalFiles = data.total_processing_files || 0;
                
                console.log(`Upload status: ${status} (age: ${age}s, total files: ${totalFiles})`);
                consecutiveErrors = 0; // Reset error counter on successful response
                
                if (status === 'ready' || status === 'done') {
                    // File is ready for basic operations
                    console.log(`[UPLOAD DEBUG] File marked as ready: ${filename}`);
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI(displayName, 'File ready!', 'success');
                    // Toast.show('success', 'File uploaded and ready!'); // Removed notification
                    
                    // Load the data - ensure all operations complete successfully
                    // Force a small delay to ensure backend processing is complete
                    console.log(`[UPLOAD DEBUG] Waiting 1 second before finalizing...`);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    // Show action splash for upload completion
                    console.log(`[UPLOAD DEBUG] Starting finalization process...`);
                    this.showActionSplash('Finalizing upload...');
                    
                    // Clear any cached data to force fresh data from backend
                    try {
                        await fetch('/api/clear-cache', { method: 'POST' });
                        console.log('Cleared backend cache after upload');
                    } catch (cacheError) {
                        console.warn('Failed to clear cache:', cacheError);
                    }
                    
                    console.log(`[UPLOAD DEBUG] Loading available tags...`);
                    const availableTagsLoaded = await this.fetchAndUpdateAvailableTags();
                    console.log(`[UPLOAD DEBUG] Available tags loaded: ${availableTagsLoaded}`);
                    
                    console.log(`[UPLOAD DEBUG] Loading selected tags...`);
                    const selectedTagsLoaded = await this.fetchAndUpdateSelectedTags();
                    console.log(`[UPLOAD DEBUG] Selected tags loaded: ${selectedTagsLoaded}`);
                    
                    console.log(`[UPLOAD DEBUG] Loading filter options...`);
                    await this.fetchAndPopulateFilters();
                    console.log(`[UPLOAD DEBUG] Filter options loaded`);
                    
                    // Force refresh lineage colors by re-rendering tags
                    if (availableTagsLoaded && this.state.tags && this.state.tags.length > 0) {
                        console.log('[UPLOAD DEBUG] Forcing lineage color refresh after upload...');
                        this._updateAvailableTags(this.state.tags);
                    }
                    
                    if (!availableTagsLoaded) {
                        console.error('[UPLOAD DEBUG] Failed to load available tags after upload');
                        console.error('Failed to load product data. Please try refreshing the page.');
                        return;
                    }
                    
                    console.log('[UPLOAD DEBUG] Upload processing complete');
                    return;
                } else if (status === 'processing') {
                    // Still processing, show progress
                    this.updateUploadUI(`Processing ${displayName}...`);
                    this.updateExcelLoadingStatus('Processing Excel data...');
                    
                } else if (status === 'not_found') {
                    // File not found in processing status - might be a race condition
                    console.warn(`File not found in processing status: ${filename} (age: ${age}s, total files: ${totalFiles})`);
                    
                    // If we've had a successful 'ready' status before, the file might have been processed
                    // Try to load the data anyway to see if it's available
                    if (attempts > 5) {
                        console.log('Attempting to load data despite not_found status...');
                        try {
                            const availableTagsLoaded = await this.fetchAndUpdateAvailableTags();
                            if (availableTagsLoaded && this.state.tags && this.state.tags.length > 0) {
                                console.log('Data loaded successfully despite not_found status');
                                this.hideExcelLoadingSplash();
                                this.updateUploadUI(displayName, 'File ready!', 'success');
                                return;
                            }
                        } catch (loadError) {
                            console.warn('Failed to load data despite not_found status:', loadError);
                        }
                    }
                    
                    if (attempts < 20) { // Give it more attempts for race conditions (increased from 15)
                        this.updateUploadUI(`Processing ${displayName}...`);
                        this.updateExcelLoadingStatus('Waiting for processing to start...');
                    } else {
                        this.hideExcelLoadingSplash();
                        this.updateUploadUI('Upload failed', 'File processing status lost', 'error');
                        console.error('Upload failed: Processing status lost. Please try again.');
                        return;
                    }
                    
                } else {
                    console.warn(`Unknown status: ${status}`);
                }
                
            } catch (error) {
                console.error('Error polling upload status:', error);
                consecutiveErrors++;
                
                if (consecutiveErrors >= maxConsecutiveErrors) {
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI('Upload failed', 'Network error', 'error');
                    console.error('Upload failed: Network error. Please try again.');
                    return;
                }
                
                // Continue polling but with longer delay on errors
                await new Promise(resolve => setTimeout(resolve, 3000));
                continue;
            }
            
            attempts++;
            await new Promise(resolve => setTimeout(resolve, 3000)); // Poll every 3 seconds
        }
        
        // Timeout
        this.hideExcelLoadingSplash();
        this.updateUploadUI('Upload timed out', 'Processing took too long', 'error');
                            console.error('Upload timed out. Please try again.');
    },

    updateUploadUI(fileName, statusMessage, statusType) {
        const currentFileInfo = document.getElementById('currentFileInfo');
        const fileInfoText = document.getElementById('fileInfoText');
        
        if (currentFileInfo) {
            // Keep the default filename instead of showing the uploaded file name
            // Only show status messages, not the uploaded filename
            if (statusMessage && statusType) {
                // Show status message temporarily
                const originalText = currentFileInfo.textContent;
                currentFileInfo.textContent = statusMessage;
                currentFileInfo.classList.add(statusType);
                setTimeout(() => {
                    currentFileInfo.textContent = originalText;
                    currentFileInfo.classList.remove(statusType);
                }, 3000);
            } else if (statusMessage && !statusType) {
                // This is likely an error or "No file selected" message
                currentFileInfo.textContent = statusMessage;
            }
            // Don't update the filename for successful uploads - keep the default filename
        }
        
        // Update the file info text if a filename is provided
        if (fileName && fileInfoText) {
            fileInfoText.textContent = fileName;
        }
    },

    moveToSelected: function(tagsToMove) {
        tagsToMove.forEach(tag => {
            // Remove from available, add to selected
            // (implement your logic here)
            this.state.selectedTags.add(tag);
            // Optionally, remove from availableTags set/list
        });
        // Refresh UI
        this.fetchAndUpdateAvailableTags();
        this.fetchAndUpdateSelectedTags();
    },

    onTagsLoaded: function(tags) {
        TagsTable.updateTagsList('availableTags', tags);
        autocheckAllAvailableTags();
    },

    setupFilterEventListeners() {
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter', 'dohFilter', 'highCbdFilter'];
        
        console.log('Setting up filter event listeners...');
        
        // Create a debounced version of the filter update function
        const debouncedFilterUpdate = debounce(async (filterType, value) => {
            console.log('Filter changed:', filterType, value);
            
            // Update table header if TagsTable is available
            if (filterType === 'productType' && typeof TagsTable !== 'undefined' && TagsTable.updateTableHeader) {
                TagsTable.updateTableHeader();
            }
            
            // Update filter options for cascading behavior
            await this.updateFilterOptions();
            
            // Apply the filters to the tag lists
            this.applyFilters();
            this.renderActiveFilters();
        }, 150); // 150ms debounce delay
        
        filterIds.forEach(filterId => {
            const filterElement = document.getElementById(filterId);
            console.log(`Filter element ${filterId}:`, filterElement);
            
            if (filterElement) {
                filterElement.addEventListener('change', (event) => {
                    const filterType = this.getFilterTypeFromId(filterId);
                    const value = event.target.value;
                    
                    // For immediate feedback, apply filters right away
                    this.applyFilters();
                    
                    // Then debounce the cascading filter updates
                    debouncedFilterUpdate(filterType, value);
                });
                console.log(`Event listener attached to ${filterId}`);
            } else {
                console.warn(`Filter element ${filterId} not found`);
            }
        });
    },

    setupSearchEventListeners() {
        console.log('Setting up search event listeners...');
        
        // Add search event listeners for available tags
        const availableTagsSearch = document.getElementById('availableTagsSearch');
        if (availableTagsSearch) {
            availableTagsSearch.removeEventListener('input', this.handleAvailableTagsSearch.bind(this));
            availableTagsSearch.addEventListener('input', this.handleAvailableTagsSearch.bind(this));
            console.log('Added event listener to availableTagsSearch');
        } else {
            console.warn('Available tags search element not found');
        }
        
        // Add search event listeners for selected tags
        const selectedTagsSearch = document.getElementById('selectedTagsSearch');
        if (selectedTagsSearch) {
            selectedTagsSearch.removeEventListener('input', this.handleSelectedTagsSearch.bind(this));
            selectedTagsSearch.addEventListener('input', this.handleSelectedTagsSearch.bind(this));
            console.log('Added event listener to selectedTagsSearch');
        } else {
            console.warn('Selected tags search element not found');
        }
    },

    getFilterTypeFromId(filterId) {
        const idToType = {
            'vendorFilter': 'vendor',
            'brandFilter': 'brand',
            'productTypeFilter': 'productType',
            'lineageFilter': 'lineage',
            'weightFilter': 'weight',
            'dohFilter': 'doh',
            'highCbdFilter': 'highCbd'
        };
        return idToType[filterId] || filterId;
    },

    // Add this function to render active filters above the Available list
    renderActiveFilters() {
        const filterIds = [
            { id: 'vendorFilter', label: 'Vendor' },
            { id: 'brandFilter', label: 'Brand' },
            { id: 'productTypeFilter', label: 'Type' },
            { id: 'lineageFilter', label: 'Lineage' },
            { id: 'weightFilter', label: 'Weight' },
            { id: 'dohFilter', label: 'DOH' },
            { id: 'highCbdFilter', label: 'High CBD' }
        ];
        let container = document.getElementById('activeFiltersContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'activeFiltersContainer';
            container.style.display = 'flex';
            container.style.gap = '0.5rem';
            container.style.marginBottom = '0.5rem';
            container.style.alignItems = 'center';
            container.style.flexWrap = 'wrap';
            const availableTags = document.getElementById('availableTags');
            if (availableTags && availableTags.parentNode) {
                availableTags.parentNode.insertBefore(container, availableTags);
            }
        }
        container.innerHTML = '';
        
        // Add "Clear All Filters" button if any filters are active
        const activeFilters = filterIds.filter(({ id }) => {
            const select = document.getElementById(id);
            return select && select.value && select.value !== '' && select.value.toLowerCase() !== 'all';
        });
        
        if (activeFilters.length > 0) {
            const clearAllBtn = document.createElement('button');
            clearAllBtn.textContent = 'Clear All Filters';
            clearAllBtn.style.background = 'rgba(255,255,255,0.1)';
            clearAllBtn.style.border = '1px solid rgba(255,255,255,0.3)';
            clearAllBtn.style.borderRadius = '6px';
            clearAllBtn.style.padding = '4px 8px';
            clearAllBtn.style.fontSize = '0.8em';
            clearAllBtn.style.color = '#fff';
            clearAllBtn.style.cursor = 'pointer';
            clearAllBtn.style.marginRight = '0.5rem';
            clearAllBtn.addEventListener('click', () => {
                this.clearAllFilters();
            });
            container.appendChild(clearAllBtn);
        }
        
        filterIds.forEach(({ id, label }) => {
            const select = document.getElementById(id);
            if (select && select.value && select.value !== '' && select.value.toLowerCase() !== 'all') {
                const filterDiv = document.createElement('div');
                filterDiv.style.display = 'flex';
                filterDiv.style.alignItems = 'center';
                filterDiv.style.background = 'rgba(255,255,255,0.08)';
                filterDiv.style.borderRadius = '8px';
                filterDiv.style.padding = '2px 8px';
                filterDiv.style.fontSize = '0.85em';
                filterDiv.style.color = '#fff';
                filterDiv.style.fontWeight = '500';
                filterDiv.style.gap = '0.25em';
                filterDiv.innerHTML = `${label}: ${select.value}`;
                const closeBtn = document.createElement('span');
                closeBtn.textContent = '×';
                closeBtn.style.cursor = 'pointer';
                closeBtn.style.marginLeft = '4px';
                closeBtn.style.fontSize = '1em';
                closeBtn.setAttribute('aria-label', `Clear ${label} filter`);
                closeBtn.addEventListener('click', () => {
                    select.value = '';
                    // Trigger change event to update filters
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                });
                filterDiv.appendChild(closeBtn);
                container.appendChild(filterDiv);
            }
        });
    },

    // Add function to clear all filters at once
    clearAllFilters() {
        console.log('Clearing all filters...');
        
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter', 'dohFilter', 'highCbdFilter'];
        
        // Clear each filter dropdown
        filterIds.forEach(filterId => {
            const filterElement = document.getElementById(filterId);
            if (filterElement) {
                filterElement.value = '';
            }
        });
        
        // Apply the cleared filters
        this.applyFilters();
        this.renderActiveFilters();
        
        // Show success message
        if (window.Toast) {
            window.Toast.show('All filters cleared successfully', 'success');
        }
        
        // Add visual feedback to the button
        const clearBtn = document.getElementById('clearFiltersBtn');
        if (clearBtn) {
            clearBtn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                clearBtn.style.transform = 'scale(1)';
            }, 150);
        }
        
        console.log('All filters cleared successfully');
    },

    // Emergency function to clear stuck upload UI
    forceClearUploadUI() {
        console.log('Force clearing upload UI state...');
        
        // Hide any loading splash
        this.hideExcelLoadingSplash();
        
        // Clear the file info display
        const currentFileInfo = document.getElementById('currentFileInfo');
        const fileInfoText = document.getElementById('fileInfoText');
        
        if (currentFileInfo) {
            currentFileInfo.textContent = 'No file selected';
            currentFileInfo.className = ''; // Remove any status classes
        }
        
        if (fileInfoText) {
            fileInfoText.textContent = '';
        }
        
        // Force refresh the data
        this.fetchAndUpdateAvailableTags();
        this.fetchAndUpdateSelectedTags();
        this.fetchAndPopulateFilters();
        
        console.log('Upload UI state cleared');
    },

    // Validate and clean up selected tags against current Excel data
    validateSelectedTags() {
        // Add safeguard to prevent clearing tags that were just added via JSON matching
        const hasJsonMatchedTags = this.state.persistentSelectedTags.length > 0;
        
        if (!this.state.originalTags || this.state.originalTags.length === 0) {
            // No Excel data loaded, but don't clear if we have JSON matched tags
            if (!hasJsonMatchedTags) {
                this.state.persistentSelectedTags = [];
                this.state.selectedTags.clear();
            } else {
                console.log('Preserving JSON matched tags even though no Excel data is loaded yet');
            }
            return;
        }

        // Create case-insensitive lookup maps
        const validProductNamesLower = new Map();
        this.state.originalTags.forEach(tag => {
            const name = tag['Product Name*'];
            if (name) {
                validProductNamesLower.set(name.toLowerCase(), name); // Store original case
            }
        });

        const invalidTags = [];
        const validTags = [];
        const correctedTags = new Set();

        // Check each selected tag with case-insensitive comparison
        for (const tagName of this.state.persistentSelectedTags) {
            const tagNameLower = tagName.toLowerCase();
            const originalName = validProductNamesLower.get(tagNameLower);
            
            if (originalName) {
                // Tag exists, use the original case from Excel data
                validTags.push(originalName);
                correctedTags.add(originalName);
            } else {
                invalidTags.push(tagName);
            }
        }

        // Only clear and update if we actually found invalid tags
        if (invalidTags.length > 0) {
            // Remove invalid tags and update with corrected case
            this.state.persistentSelectedTags = [];
            correctedTags.forEach(tagName => {
                if (!this.state.persistentSelectedTags.includes(tagName)) {
                                this.state.persistentSelectedTags.push(tagName);
                            };
            });

            // Update the regular selectedTags set
            this.state.selectedTags = new Set(this.state.persistentSelectedTags);

            // Show warning if invalid tags were found
            console.warn(`Removed ${invalidTags.length} tags that don't exist in current Excel data:`, invalidTags);
            if (window.Toast) {
                window.Toast.show(`Removed ${invalidTags.length} tags that don't exist in current data`, 'warning');
            }

            // Update the UI to reflect the cleaned selections
            const validTagObjects = validTags.map(name => 
                this.state.originalTags.find(t => t['Product Name*'] === name)
            ).filter(Boolean);
            
            this.updateSelectedTags(validTagObjects);
        }
    },
};

// Expose TagManager to global scope
window.TagManager = TagManager;
window.updateAvailableTags = TagManager.debouncedUpdateAvailableTags.bind(TagManager);
window.updateFilters = TagManager.updateFilters.bind(TagManager);
window.fetchAndUpdateSelectedTags = TagManager.fetchAndUpdateSelectedTags.bind(TagManager);

function attachSelectedTagsCheckboxListeners() {
    const container = document.getElementById('selectedTags');
    if (!container) return;

    // Parent checkboxes
    container.querySelectorAll('.select-all-checkbox').forEach(parentCheckbox => {
        parentCheckbox.disabled = false;
        const newCheckbox = parentCheckbox.cloneNode(true);
        parentCheckbox.parentNode.replaceChild(newCheckbox, parentCheckbox);

        newCheckbox.addEventListener('change', function(e) {
            console.log('Parent checkbox clicked in selected tags', this);
            const isChecked = e.target.checked;
            // Find the closest section (vendor, brand, product type, or weight)
            const parentSection = newCheckbox.closest('.vendor-section, .brand-section, .product-type-section, .weight-section');
            if (!parentSection) {
                console.warn('No parent section found for parent checkbox in selected tags', this);
                return;
            }
            const checkboxes = parentSection.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                if (checkbox.classList.contains('tag-checkbox')) {
                    const tag = TagManager.state.tags.find(t => t['Product Name*'] === checkbox.value);
                    if (tag) {
                        if (isChecked) {
                            TagManager.state.selectedTags.add(tag['Product Name*']);
                        } else {
                            TagManager.state.selectedTags.delete(tag['Product Name*']);
                        }
                    }
                }
            });
            TagManager.updateSelectedTags(Array.from(TagManager.state.selectedTags).map(name =>
                TagManager.state.tags.find(t => t['Product Name*'] === name)
            ));
        });
        console.log('Attached parent checkbox listener in selected tags', newCheckbox);
    });

    // Child tag checkboxes
    container.querySelectorAll('input[type="checkbox"].tag-checkbox').forEach(checkbox => {
        const newCheckbox = checkbox.cloneNode(true);
        checkbox.parentNode.replaceChild(newCheckbox, checkbox);

        newCheckbox.addEventListener('change', function() {
            if (this.checked) {
                TagManager.state.selectedTags.add(this.value);
            } else {
                TagManager.state.selectedTags.delete(this.value);
            }
            // Only update selected tags panel
            TagManager.updateSelectedTags(Array.from(TagManager.state.selectedTags).map(name =>
                TagManager.state.tags.find(t => t['Product Name*'] === name)
            ));
        });
    });
}

TagManager.state.selectedTags.clear();
TagManager.debouncedUpdateAvailableTags(TagManager.state.originalTags, TagManager.state.tags);
TagManager.updateSelectedTags([]);

console.log('Original tags:', TagManager.state.originalTags);

// Lineage abbreviation mapping (matching Python version)
const ABBREVIATED_LINEAGE = {
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

// When populating the lineage filter dropdown, use abbreviated lineage names
function populateLineageFilterOptions(options) {
  const lineageFilter = document.getElementById('lineageFilter');
  if (!lineageFilter) return;
  lineageFilter.innerHTML = '';
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'All Lineages';
  lineageFilter.appendChild(defaultOption);
  options.forEach(opt => {
    const option = document.createElement('option');
    option.value = opt;
    const displayName = ABBREVIATED_LINEAGE[opt] || opt;
    option.textContent = displayName;
    lineageFilter.appendChild(option);
  });
}

function hyphenNoBreakBeforeQuantity(text) {
    // Replace " - 1g" with " -\u00A01g"
    return text.replace(/ - (\d[\w.]*)/g, ' -\u00A0$1');
}

// Only add event listener if the button exists
const addSelectedTagsBtn = document.getElementById('addSelectedTagsBtn');
if (addSelectedTagsBtn) {
    addSelectedTagsBtn.addEventListener('click', function() {
        // Get all checked checkboxes in the available tags container
        const checked = document.querySelectorAll('#availableTags .tag-checkbox:checked');
        const tagsToMove = Array.from(checked).map(cb => cb.value);
        TagManager.moveToSelected(tagsToMove);
    });
}

function autocheckAllAvailableTags() {
  // Select all checkboxes in the available tags container
  document.querySelectorAll('#availableTags .tag-checkbox').forEach(cb => {
    cb.checked = true;
    // Optionally, update your state if needed:
    TagManager.state.selectedTags.add(cb.value);
  });
  // Optionally, update any UI or state that depends on checked tags
  TagManager.updateTagCheckboxes && TagManager.updateTagCheckboxes();
}

// Only update if filteredTags is defined
if (typeof filteredTags !== 'undefined' && filteredTags) {
    TagsTable.updateTagsList('availableTags', filteredTags);
}
autocheckAllAvailableTags();

// Test function for Select All functionality
window.testSelectAll = function() {
  console.log('Testing Select All functionality...');
  
  // Test Available Select All
  const selectAllAvailable = document.getElementById('selectAllAvailable');
  console.log('Select All Available checkbox:', selectAllAvailable);
  if (selectAllAvailable) {
    console.log('Available checkbox checked state:', selectAllAvailable.checked);
    console.log('Available checkbox visible:', selectAllAvailable.offsetParent !== null);
    console.log('Available checkbox style:', window.getComputedStyle(selectAllAvailable));
    
    // Manually trigger the change event
    selectAllAvailable.checked = !selectAllAvailable.checked;
    selectAllAvailable.dispatchEvent(new Event('change', { bubbles: true }));
    console.log('Manually triggered Available change event');
  } else {
    console.error('Select All Available checkbox not found!');
  }
  
  // Test Selected Select All
  const selectAllSelected = document.getElementById('selectAllSelected');
  console.log('Select All Selected checkbox:', selectAllSelected);
  if (selectAllSelected) {
    console.log('Selected checkbox checked state:', selectAllSelected.checked);
    console.log('Selected checkbox visible:', selectAllSelected.offsetParent !== null);
    console.log('Selected checkbox style:', window.getComputedStyle(selectAllSelected));
    
    // Manually trigger the change event
    selectAllSelected.checked = !selectAllSelected.checked;
    selectAllSelected.dispatchEvent(new Event('change', { bubbles: true }));
    console.log('Manually triggered Selected change event');
  } else {
    console.error('Select All Selected checkbox not found!');
  }
};

async function handleJsonPasteInput(input) {
    let jsonText = input.trim();
    let json;
    // If input looks like a URL, fetch the JSON
    if (jsonText.startsWith('http')) {
        try {
            const response = await fetch(jsonText);
            jsonText = await response.text();
        } catch (e) {
            console.error('Failed to fetch JSON from URL.');
            return;
        }
    }
    try {
        json = JSON.parse(jsonText);
    } catch (e) {
        console.error('Invalid JSON format. Please paste valid JSON.');
        return;
    }
    // ... continue with your matching logic ...
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Show splash screen immediately
    AppLoadingSplash.show();
    
    // Initialize TagManager (which will handle the splash loading)
    TagManager.init();
    
    // Initialize sticky filter bar behavior
    initializeStickyFilterBar();

    // Add event listener for the clear button
    const clearButton = document.getElementById('clear-filters-btn');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            if (window.TagManager && TagManager.clearSelected) {
                TagManager.clearSelected();
            }
        });
        console.log('Clear button event listener attached');
    } else {
        console.error('Clear button not found');
    }

    // Add event listener for the undo button
    const undoButton = document.getElementById('undo-move-btn');
    if (undoButton) {
        undoButton.addEventListener('click', function() {
            if (window.TagManager && TagManager.undoMove) {
                TagManager.undoMove();
            }
        });
        console.log('Undo button event listener attached');
    } else {
        console.error('Undo button not found');
    }

    // Note: Select All event listeners are now handled in the TagManager._updateAvailableTags and updateSelectedTags methods
    // to ensure proper state management and prevent duplicate listeners
    
    // Fallback: ensure splash screen completes even if there are issues
    setTimeout(() => {
        if (AppLoadingSplash.isVisible) {
            console.log('Fallback: completing splash screen after timeout');
            AppLoadingSplash.stopAutoAdvance();
            AppLoadingSplash.complete();
        }
    }, 10000); // 10 second fallback
});

// Global functions for debugging
window.AppLoadingSplash = AppLoadingSplash;
window.emergencyHideSplash = () => AppLoadingSplash.emergencyHide();

// Function to clear stuck uploads
async function clearStuckUploads() {
    try {
        console.log('Clearing stuck uploads...');
        const response = await fetch('/api/clear-upload-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Upload status cleared:', result.message);
            
            // Show a toast notification
            if (window.Toast) {
                Toast.show('success', result.message);
            } else {
                alert(result.message);
            }
            
            // Refresh the page to reset the UI state
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            console.error('Failed to clear upload status:', response.statusText);
            alert('Failed to clear stuck uploads. Please try again.');
        }
    } catch (error) {
        console.error('Error clearing stuck uploads:', error);
        alert('Error clearing stuck uploads. Please try again.');
    }
}

// Initialize sticky filter bar behavior
function initializeStickyFilterBar() {
    const stickyFilterBar = document.querySelector('.sticky-filter-bar');
    const tagList = document.getElementById('availableTags');
    
    if (stickyFilterBar && tagList) {
        // Add scroll event listener to the tag list
        tagList.addEventListener('scroll', function() {
            const rect = stickyFilterBar.getBoundingClientRect();
            const cardHeader = document.querySelector('.card-header');
            
            if (cardHeader) {
                const headerRect = cardHeader.getBoundingClientRect();
                
                // Check if the filter bar should be sticky
                if (headerRect.bottom <= 0) {
                    stickyFilterBar.classList.add('is-sticky');
                } else {
                    stickyFilterBar.classList.remove('is-sticky');
                }
            }
        });
        
        // Also listen for window scroll for better cross-browser compatibility
        window.addEventListener('scroll', function() {
            const rect = stickyFilterBar.getBoundingClientRect();
            const cardHeader = document.querySelector('.card-header');
            
            if (cardHeader) {
                const headerRect = cardHeader.getBoundingClientRect();
                
                if (headerRect.bottom <= 0) {
                    stickyFilterBar.classList.add('is-sticky');
                } else {
                    stickyFilterBar.classList.remove('is-sticky');
                }
            }
        });
    }
}

function clearUIState() {
    // Clear selected tags
    if (window.TagManager && TagManager.clearSelected) TagManager.clearSelected();
    // Clear search fields
    document.querySelectorAll('input[type="text"]').forEach(el => el.value = '');
    // Reset filters
    document.querySelectorAll('select').forEach(el => el.selectedIndex = 0);
    // Clear checkboxes
    document.querySelectorAll('input[type="checkbox"]').forEach(el => el.checked = false);
    // Clear localStorage/sessionStorage
    if (window.localStorage) localStorage.clear();
    if (window.sessionStorage) sessionStorage.clear();
}

// Call clearUIState after export or upload success
// Example: after successful AJAX response for export/upload
// clearUIState();

// Removed conflicting file info text initialization - now handled by checkForExistingData()

// Global function to clear stuck upload UI (can be called from browser console)
window.clearStuckUploadUI = function() {
    if (typeof TagManager !== 'undefined' && TagManager.forceClearUploadUI) {
        TagManager.forceClearUploadUI();
        console.log('Stuck upload UI cleared via global function');
    } else {
        console.error('TagManager not available');
    }
};

// Global function to check upload status
window.checkUploadStatus = function(filename) {
    fetch(`/api/upload-status?filename=${encodeURIComponent(filename)}`)
        .then(response => response.json())
        .then(data => {
            console.log('Upload status:', data);
        })
        .catch(error => {
            console.error('Error checking upload status:', error);
        });
};

// Event listeners for drag-and-drop reordering
document.addEventListener('selectedTagsReordered', function(event) {
    console.log('selectedTagsReordered event received:', event.detail);
    // This event is triggered when tags are reordered via drag-and-drop
    // The UI refresh is handled by the drag-and-drop manager
});

document.addEventListener('forceRefreshSelectedTags', function(event) {
    console.log('forceRefreshSelectedTags event received');
    // Force refresh the selected tags display
    if (window.TagManager && window.TagManager.fetchAndUpdateSelectedTags) {
        console.log('Forcing refresh of selected tags...');
        window.TagManager.fetchAndUpdateSelectedTags();
    }
});

// JSON Matching Function - Global function for JSON product matching
window.performJsonMatch = function() {
    const jsonUrlInput = document.getElementById('jsonUrlInput');
    const matchBtn = document.querySelector('#jsonMatchModal .btn-modern2');
    const resultsDiv = document.getElementById('jsonMatchResults');
    const matchCount = document.getElementById('matchCount');
    const matchedProductsList = document.getElementById('matchedProductsList');
    
    if (!jsonUrlInput || !matchBtn) {
        console.error('JSON match modal elements not found');
        return;
    }
    
    let jsonUrl = jsonUrlInput.value.trim();
    if (!jsonUrl) {
        console.error('Please enter a JSON URL first.');
        return;
    }

    // Validate URL format
    if (!/^https?:\/\//i.test(jsonUrl)) {
        console.error('Please enter a valid URL starting with http:// or https://');
        return;
    }

    // Show loading state
    matchBtn.disabled = true;
    matchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
    
    // Show progress message
    resultsDiv.classList.remove('d-none');
    matchCount.textContent = 'Processing...';
    matchedProductsList.innerHTML = '<div class="text-info">Matching products from JSON URL. This may take up to 10 minutes for large datasets. Progress will be logged in the browser console.</div>';

    // Add timeout to prevent hanging
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minutes timeout
    
    // Use the json-match endpoint
    fetch('/api/json-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: String(jsonUrl) }),
        signal: controller.signal
    })
    .then(response => {
        if (!response.ok) {
            // Clone the response so we can read it multiple times if needed
            const responseClone = response.clone();
            return response.json().then(error => {
                // Handle both string and object error responses
                const errorMessage = typeof error === 'string' ? error : (error.error || 'JSON matching failed');
                throw new Error(errorMessage);
            }).catch(jsonError => {
                // If JSON parsing fails, try to get text response from the cloned response
                return responseClone.text().then(text => {
                    throw new Error(`Server error: ${text || 'Unknown error'}`);
                });
            });
        }
        return response.json().catch(jsonError => {
            throw new Error('Invalid JSON response from server');
        });
    })
    .then(matchResult => {
        // Safety check: ensure matchResult is an object
        if (typeof matchResult !== 'object' || matchResult === null) {
            console.error('Invalid matchResult:', matchResult);
            throw new Error('Invalid response format from server');
        }
        
        // Show results
        matchCount.textContent = matchResult.matched_count || 0;
        
        // Populate matched products list with note about where they were added
        if (matchResult.matched_names && matchResult.matched_names.length > 0) {
            matchedProductsList.innerHTML = `
                <div class="alert alert-success mb-3">
                    <strong>Success!</strong> ${matchResult.matched_count} products were matched and added to the <strong>Available Tags</strong> list.
                    <br>Please review the available tags and select the items you need.
                </div>
                <div class="mb-2"><strong>Matched Products:</strong></div>
                ${matchResult.matched_names
                    .map(product => `<div class="mb-1">• ${product}</div>`)
                    .join('')}
            `;
        } else {
            matchedProductsList.innerHTML = '<div class="text-muted">No specific product details available</div>';
        }
        
        resultsDiv.classList.remove('d-none');
        
        // Successfully matched products from JSON URL
        
        // Clear the input
        jsonUrlInput.value = '';
        
        // Refresh the UI with new data
        if (typeof TagManager !== 'undefined') {
            console.log('JSON matched products added to available tags for manual selection');
            console.log('Matched names:', matchResult.matched_names);
            console.log('JSON matched tags:', matchResult.json_matched_tags);
            
            // Don't automatically add to selected tags - let users choose
            // Instead, update the available tags with the new JSON matched items
            
            // Use TagManager's method to update available tags
            TagManager._updateAvailableTags(matchResult.available_tags);
            
            // Show a notification to the user
            const notificationDiv = document.createElement('div');
            notificationDiv.className = 'alert alert-info alert-dismissible fade show';
            notificationDiv.innerHTML = `
                <strong>JSON Matching Complete!</strong> 
                ${matchResult.matched_count} products were matched and added to the available tags list. 
                Please review and select the items you need.
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            // Insert the notification at the top of the page
            const container = document.querySelector('.container-fluid') || document.querySelector('.container');
            if (container) {
                container.insertBefore(notificationDiv, container.firstChild);
                
                // Auto-dismiss after 10 seconds
                setTimeout(() => {
                    if (notificationDiv.parentNode) {
                        notificationDiv.remove();
                    }
                }, 10000);
            }
        }
        
        console.log('Available tags updated with JSON matched items');
    })
    .catch(error => {
        console.error('JSON matching error:', error);
        
        // Show error message to user
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show';
        errorDiv.innerHTML = `
            <strong>JSON Matching Error!</strong> 
            ${error.message || 'An error occurred during JSON matching. Please try again.'}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert the error at the top of the page
        const container = document.querySelector('.container-fluid') || document.querySelector('.container');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
            
            // Auto-dismiss after 10 seconds
            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.remove();
                }
            }, 10000);
        }
        
        // Reset UI state
        matchCount.textContent = '0';
        matchedProductsList.innerHTML = '<div class="text-muted">No products matched</div>';
        resultsDiv.classList.add('d-none');
    })
    .finally(() => {
        // Reset button state
        matchBtn.disabled = false;
        matchBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="me-2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            Match Products
        `;
    });
};

// Global error handler to prevent page from exiting
window.addEventListener('error', function(e) {
    console.error('Global error caught:', e.error);
    // Prevent the error from causing the page to exit
    e.preventDefault();
    return false;
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
    // Prevent the error from causing the page to exit
    e.preventDefault();
});

// Initialize TagManager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    TagManager.init();
});