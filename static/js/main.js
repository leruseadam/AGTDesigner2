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
const VALID_PRODUCT_TYPES = [
  "flower", "pre-roll", "infused pre-roll", "concentrate", "solventless concentrate", "vape cartridge",
  "edible (solid)", "edible (liquid)", "high cbd edible liquid", "tincture", "topical", "capsule", "paraphernalia"
];

const debounce = (func, delay) => {
    let timeoutId;
    return function(...args) {
        const context = this;
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(context, args);
        }, delay);
    };
};

// Global clear file function
function clearFile() {
    const fileInput = document.getElementById('fileInput');
    const currentFileInfo = document.getElementById('currentFileInfo');
    const fileDropZone = document.getElementById('fileDropZone');
    
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

const TagManager = {
    state: {
        selectedTags: new Set(),
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
            'HYBRID/INDICA': 'var(--lineage-hybrid-indica)',
            'HYBRID/SATIVA': 'var(--lineage-hybrid-sativa)',
            'CBD': 'var(--lineage-cbd)',
            'CBD_BLEND': 'var(--lineage-cbd)',  // Use same yellow as CBD
            'MIXED': 'var(--lineage-mixed)',
            'PARA': 'var(--lineage-para)'
        },
        filterCache: null,
        updateAvailableTagsTimer: null // Add timer tracking
    },

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
            weight: 'weightFilter'
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
            
            // Store current value
            const currentValue = filterElement.value;
            
            // Update the dropdown options
            filterElement.innerHTML = `
                <option value="">All</option>
                ${sortedValues.map(value => `<option value="${value}">${value}</option>`).join('')}
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
                weight: document.getElementById('weightFilter')?.value || ''
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
                    const tagWeightWithUnits = (tag.weightWithUnits || tag.weight || '').toString().trim().toLowerCase();
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
                if (tag.weightWithUnits || tag.weight) availableOptions.weight.add((tag.weightWithUnits || tag.weight).toString().trim());
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
                    // Create new options HTML
                    const optionsHtml = `
                        <option value="">All</option>
                        ${sortedOptions.map(value => `<option value="${value}">${value}</option>`).join('')}
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
        
        // Create a filter key for caching
        const filterKey = `${vendorFilter}|${brandFilter}|${productTypeFilter}|${lineageFilter}|${weightFilter}`;
        
        // Check if we have cached results for this exact filter combination
        if (this.state.filterCache && this.state.filterCache.key === filterKey) {
            this.debouncedUpdateAvailableTags(this.state.filterCache.result);
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
                const tagProductType = (tag.productType || '').trim();
                if (tagProductType.toLowerCase() !== productTypeFilter.toLowerCase()) {
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
                const tagWeightWithUnits = (tag.weightWithUnits || tag.weight || '').toString().trim().toLowerCase();
                const filterWeight = weightFilter.toString().trim().toLowerCase();
                if (tagWeightWithUnits !== filterWeight) {
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
        
        // Update the available tags display with filtered results
        this.debouncedUpdateAvailableTags(filteredTags);
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
                this.debouncedUpdateAvailableTags(this.state.originalTags);
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
            this.debouncedUpdateAvailableTags(filteredTags);
        } else if (listId === 'selectedTags') {
            this.updateSelectedTags(filteredTags);
        }
        searchInput.classList.add('search-active');
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

    organizeBrandCategories(tags) {
        const vendorGroups = new Map();
        let skippedTags = 0;
        
        // Debug: Log the first few tags to see their structure
        if (tags.length > 0) {
            console.log('First tag structure:', tags[0]);
            console.log('Available keys in first tag:', Object.keys(tags[0]));
        }
        
        tags.forEach(tag => {
            // Use the correct field names from the tag object - check multiple possible field names
            let vendor = tag.vendor || tag['Vendor'] || tag['Vendor/Supplier*'] || tag['Vendor/Supplier'] || '';
            let brand = tag.productBrand || tag['Product Brand'] || tag['ProductBrand'] || this.extractBrand(tag) || '';
            const rawProductType = tag.productType || tag['Product Type*'] || tag['Product Type'] || '';
            const productType = VALID_PRODUCT_TYPES.includes(rawProductType.trim().toLowerCase())
              ? rawProductType.trim()
              : 'Unknown Type';
            const lineage = tag.lineage || tag['Lineage'] || 'MIXED';
            const weight = tag.weight || tag['Weight*'] || tag['Weight'] || '';
            const weightWithUnits = tag.weightWithUnits || weight || '';

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
                vendor: vendor.trim(),
                brand: brand.trim(),
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
    debouncedUpdateAvailableTags: debounce(function(tags) {
        this._updateAvailableTags(tags);
    }, 100),

    // Internal function that actually updates the available tags
    _updateAvailableTags(tags) {
        if (!tags || !Array.isArray(tags)) {
            console.warn('updateAvailableTags called with invalid tags:', tags);
            return;
        }
        
        console.time('updateAvailableTags');
        
        const container = document.getElementById('availableTags');
        if (!container) {
            console.error('availableTags container not found');
            return;
        }

        // Store tags in state for later use
        this.state.tags = tags;
        
        // Store original tags if this is the first time loading
        if (this.state.originalTags.length === 0) {
            this.state.originalTags = [...tags];
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
                            this.state.selectedTags.add(tag['Product Name*']);
                        } else {
                            this.state.selectedTags.delete(tag['Product Name*']);
                        }
                    }
                });
                this.debouncedUpdateAvailableTags(this.state.tags);
                this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ));
            });
        }

        // If no tags, just return
        if (tags.length === 0) {
            return;
        }

        // Assign a unique tagId to each tag (use index for uniqueness)
        tags.forEach((tag, idx) => {
            tag.tagId = tag['Product Name*'] + '___' + idx;
        });

        // Organize tags into hierarchical groups
        const groupedTags = this.organizeBrandCategories(tags);

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
                    // Only update selectedTags for tag-checkboxes
                    if (checkbox.classList.contains('tag-checkbox')) {
                        const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                        if (tag) {
                            if (isChecked) {
                                this.state.selectedTags.add(tag['Product Name*']);
                            } else {
                                this.state.selectedTags.delete(tag['Product Name*']);
                            }
                        }
                    }
                });
                this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean));
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
                        // Only update selectedTags for tag-checkboxes
                        if (checkbox.classList.contains('tag-checkbox')) {
                            const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                            if (tag) {
                                if (isChecked) {
                                    this.state.selectedTags.add(tag['Product Name*']);
                                } else {
                                    this.state.selectedTags.delete(tag['Product Name*']);
                                }
                            }
                        }
                    });
                    this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
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
                            // Only update selectedTags for tag-checkboxes
                            if (checkbox.classList.contains('tag-checkbox')) {
                                const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                if (tag) {
                                    if (isChecked) {
                                        this.state.selectedTags.add(tag['Product Name*']);
                                    } else {
                                        this.state.selectedTags.delete(tag['Product Name*']);
                                    }
                                }
                            }
                        });
                        this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                            this.state.tags.find(t => t['Product Name*'] === name)
                        ).filter(Boolean));
                    });
                    typeHeader.appendChild(productTypeCheckbox);
                    typeHeader.appendChild(document.createTextNode(productType));
                    productTypeSection.appendChild(typeHeader);

                    // Create weight sections
                    const sortedWeights = Array.from(weightGroups.entries())
                        .sort(([a], [b]) => parseWeight(a) - parseWeight(b));

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
                                // Only update selectedTags for tag-checkboxes
                                if (checkbox.classList.contains('tag-checkbox')) {
                                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                    if (tag) {
                                        if (isChecked) {
                                            this.state.selectedTags.add(tag['Product Name*']);
                                        } else {
                                            this.state.selectedTags.delete(tag['Product Name*']);
                                        }
                                    }
                                }
                            });
                            this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                                this.state.tags.find(t => t['Product Name*'] === name)
                            ).filter(Boolean));
                        });
                        weightHeader.appendChild(weightCheckbox);
                        weightHeader.appendChild(document.createTextNode(weight));
                        weightSection.appendChild(weightHeader);
                        // Always render tags as leaf nodes
                        if (tags && tags.length > 0) {
                            // Sort tags alphabetically by Product Name*
                            const tagsSorted = tags.slice().sort((a, b) => {
                                const nameA = (a['Product Name*'] || '').toLowerCase();
                                const nameB = (b['Product Name*'] || '').toLowerCase();
                                return nameA.localeCompare(nameB);
                            });
                            tagsSorted.forEach(tag => {
                                const tagElement = this.createTagElement(tag);
                                tagElement.querySelector('.tag-checkbox').checked = this.state.selectedTags.has(tag['Product Name*']);
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

        this.updateTagCount('available', tags.length);
        console.timeEnd('updateAvailableTags');
        
        // Reinitialize drag and drop for new tags
        if (window.dragAndDropManager) {
            window.dragAndDropManager.reinitializeTagDragAndDrop();
        }
    },

    createTagElement(tag) {
        // Create the row container
        const row = document.createElement('div');
        row.className = 'tag-row d-flex align-items-center';

        // Checkbox (leftmost)
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'tag-checkbox me-2';
        checkbox.value = tag['Product Name*'];
        checkbox.checked = this.state.selectedTags.has(tag['Product Name*']);
        checkbox.addEventListener('change', (e) => this.handleTagSelection(e, tag));

        // Tag entry (colored)
        const tagElement = document.createElement('div');
        tagElement.className = 'tag-item d-flex align-items-center p-1 mb-1';
        // Set data-lineage attribute for CSS coloring
        if (tag.lineage) {
          tagElement.dataset.lineage = tag.lineage.toUpperCase();
        }
        tagElement.dataset.tagId = tag.tagId;
        tagElement.dataset.vendor = tag.vendor;
        tagElement.dataset.brand = tag.brand;
        tagElement.dataset.productType = tag.productType;
        tagElement.dataset.lineage = tag.lineage;
        tagElement.dataset.weight = tag.weight;

        // Make the entire tag element clickable to toggle checkbox
        tagElement.style.cursor = 'pointer';
        tagElement.addEventListener('click', (e) => {
            // Don't trigger if clicking on the checkbox itself or lineage dropdown
            if (e.target === checkbox || e.target.classList.contains('lineage-select') || 
                e.target.closest('.lineage-select')) {
                return;
            }
            // Toggle the checkbox
            checkbox.checked = !checkbox.checked;
            // Trigger the change event
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        });

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
        // Only show the dropdown, not the badge
        tagInfo.appendChild(tagName);
        // Create lineage dropdown
        const lineageSelect = document.createElement('select');
        lineageSelect.className = 'form-select form-select-sm lineage-select lineage-dropdown lineage-dropdown-mini';
        lineageSelect.style.height = '28px';
        lineageSelect.style.cursor = 'pointer';
        lineageSelect.style.transition = 'all 0.2s ease';
        // Style the dropdown options
        const style = document.createElement('style');
        style.textContent = `
            .lineage-select option {
                background-color: #2d223a !important;
                color: #fff !important;
                padding: 8px !important;
                text-align: center !important;
            }
            .lineage-select:hover {
                background-color: rgba(255, 255, 255, 0.13) !important;
                border-color: #a084e8 !important;
            }
            .lineage-select:focus {
                background-color: rgba(255, 255, 255, 0.15) !important;
                border-color: #a084e8 !important;
                box-shadow: 0 0 0 2px rgba(160, 132, 232, 0.18) !important;
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
            if ((tag.lineage === option.value) || (option.value === 'CBD' && tag.lineage === 'CBD_BLEND')) {
                optionElement.selected = true;
            }
            lineageSelect.appendChild(optionElement);
        });
        lineageSelect.value = tag.lineage;
        if (tag.productType === 'Paraphernalia') {
            lineageSelect.disabled = true;
            lineageSelect.style.opacity = '0.7';
        }
        lineageSelect.addEventListener('change', async (e) => {
            const newLineage = e.target.value;
            const prevValue = tag.lineage;
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
                lineageSelect.value = newLineage;
            } catch (err) {
                // On error, revert to previous value
                lineageSelect.value = prevValue;
                if (window.Toast) Toast.show('error', 'Failed to update lineage');
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
        const isChecked = e.target.checked;
        console.log('Tag selection changed:', tag['Product Name*'], 'checked:', isChecked);
        
        if (isChecked) {
            this.state.selectedTags.add(tag['Product Name*']);
        } else {
            this.state.selectedTags.delete(tag['Product Name*']);
        }
        
        console.log('Selected tags after change:', Array.from(this.state.selectedTags));
        
        // Update the selected tags display
        const selectedTagObjects = Array.from(this.state.selectedTags).map(name =>
            this.state.tags.find(t => t['Product Name*'] === name)
        ).filter(Boolean);
        
        this.updateSelectedTags(selectedTagObjects);
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

            // Refresh the tag lists in the GUI
                            this.debouncedUpdateAvailableTags(this.state.tags);
            this.updateSelectedTags(
                Array.from(this.state.selectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean)
            );

        } catch (error) {
            console.error('Error updating lineage:', error);
            if (window.Toast) {
                Toast.show('error', error.message || 'Failed to update lineage');
            }
        }
    },

    updateSelectedTags(tags) {
        if (!tags || !Array.isArray(tags)) {
            console.warn('updateSelectedTags called with invalid tags:', tags);
            tags = [];
        }
        
        console.time('updateSelectedTags');
        console.log('updateSelectedTags called with tags:', tags);
        const container = document.getElementById('selectedTags');
        if (!container) {
            console.error('selectedTags container not found');
            console.timeEnd('updateSelectedTags');
            return;
        }

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
                    <span class="text-secondary fw-semibold">Select All Selected</span>
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
                            this.state.selectedTags.add(tag['Product Name*']);
                        } else {
                            this.state.selectedTags.delete(tag['Product Name*']);
                        }
                    }
                });
                this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean));
            });
        }

        // If no tags, just return
        if (!tags || tags.length === 0) {
            console.log('No tags to display in selected tags');
            this.updateTagCount('selected', 0);
            console.timeEnd('updateSelectedTags');
            return;
        }

        // Handle case where tags might be just strings (from JSON matching)
        // Convert to full tag objects if needed
        let fullTags = tags;
        if (tags.length > 0 && typeof tags[0] === 'string') {
            console.log('Converting string tags to full tag objects');
            fullTags = tags.map(tagName => {
                const fullTag = this.state.tags.find(t => t['Product Name*'] === tagName);
                if (!fullTag) {
                    console.warn(`Tag not found in state: ${tagName}`);
                    // Create a minimal tag object if not found
                    return {
                        'Product Name*': tagName,
                        'Product Brand': 'Unknown',
                        'Vendor': 'Unknown',
                        'Product Type*': 'Unknown',
                        'Lineage': 'Unknown'
                    };
                }
                return fullTag;
            }).filter(Boolean);
            
            // Update the selectedTags state with the new tag names
            this.state.selectedTags.clear();
            fullTags.forEach(tag => {
                this.state.selectedTags.add(tag['Product Name*']);
            });
        } else {
            // Update the selectedTags state with the new tag names
            this.state.selectedTags.clear();
            fullTags.forEach(tag => {
                this.state.selectedTags.add(tag['Product Name*']);
            });
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
                    // Only update selectedTags for tag-checkboxes
                    if (checkbox.classList.contains('tag-checkbox')) {
                        const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                        if (tag) {
                            if (isChecked) {
                                this.state.selectedTags.add(tag['Product Name*']);
                            } else {
                                this.state.selectedTags.delete(tag['Product Name*']);
                            }
                        }
                    }
                });
                this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                    this.state.tags.find(t => t['Product Name*'] === name)
                ).filter(Boolean));
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
                        // Only update selectedTags for tag-checkboxes
                        if (checkbox.classList.contains('tag-checkbox')) {
                            const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                            if (tag) {
                                if (isChecked) {
                                    this.state.selectedTags.add(tag['Product Name*']);
                                } else {
                                    this.state.selectedTags.delete(tag['Product Name*']);
                                }
                            }
                        }
                    });
                    this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
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
                            // Only update selectedTags for tag-checkboxes
                            if (checkbox.classList.contains('tag-checkbox')) {
                                const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                if (tag) {
                                    if (isChecked) {
                                        this.state.selectedTags.add(tag['Product Name*']);
                                    } else {
                                        this.state.selectedTags.delete(tag['Product Name*']);
                                    }
                                }
                            }
                        });
                        this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                            this.state.tags.find(t => t['Product Name*'] === name)
                        ).filter(Boolean));
                    });
                    
                    typeHeader.appendChild(productTypeCheckbox);
                    typeHeader.appendChild(document.createTextNode(productType));
                    productTypeSection.appendChild(typeHeader);

                    // Create weight sections
                    const sortedWeights = Array.from(weightGroups.entries())
                        .sort(([a], [b]) => parseWeight(a) - parseWeight(b));

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
                                // Only update selectedTags for tag-checkboxes
                                if (checkbox.classList.contains('tag-checkbox')) {
                                    const tag = this.state.tags.find(t => t['Product Name*'] === checkbox.value);
                                    if (tag) {
                                        if (isChecked) {
                                            this.state.selectedTags.add(tag['Product Name*']);
                                        } else {
                                            this.state.selectedTags.delete(tag['Product Name*']);
                                        }
                                    }
                                }
                            });
                            this.updateSelectedTags(Array.from(this.state.selectedTags).map(name =>
                                this.state.tags.find(t => t['Product Name*'] === name)
                            ).filter(Boolean));
                        });
                        
                        weightHeader.appendChild(weightCheckbox);
                        weightHeader.appendChild(document.createTextNode(weight));
                        weightSection.appendChild(weightHeader);
                        
                        // Always render tags as leaf nodes
                        if (tags && tags.length > 0) {
                            // Sort tags alphabetically by Product Name*
                            const tagsSorted = tags.slice().sort((a, b) => {
                                const nameA = (a['Product Name*'] || '').toLowerCase();
                                const nameB = (b['Product Name*'] || '').toLowerCase();
                                return nameA.localeCompare(nameB);
                            });
                            tagsSorted.forEach(tag => {
                                const tagElement = this.createTagElement(tag);
                                tagElement.querySelector('.tag-checkbox').checked = this.state.selectedTags.has(tag['Product Name*']);
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

        this.updateTagCount('selected', tags.length);
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
        
        // Reinitialize drag and drop for new tags
        if (window.dragAndDropManager) {
            window.dragAndDropManager.reinitializeTagDragAndDrop();
        }
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
                    TagManager.state.selectedTags.add(this.value);
                } else {
                    TagManager.state.selectedTags.delete(this.value);
                }
                TagManager.updateTagCheckboxes();
            });
        });
    },

    updateTagCheckboxes() {
        // Update available tags checkboxes
        document.querySelectorAll('#availableTags input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = TagManager.state.selectedTags.has(checkbox.value);
        });
    },

    async fetchAndUpdateAvailableTags() {
        try {
            console.log('Fetching available tags...');
            const response = await fetch('/api/available-tags');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const tags = await response.json();
            
            if (!tags || !Array.isArray(tags) || tags.length === 0) {
                console.error('No tags loaded from backend or invalid response format');
                Toast.show('error', 'Failed to load product data. Please try uploading again.');
                return false;
            }
            
            console.log(`Fetched ${tags.length} available tags`);
            this.state.tags = tags;
            this._updateAvailableTags(tags);
            return true;
        } catch (error) {
            console.error('Error fetching available tags:', error);
            Toast.show('error', 'Failed to load product data. Please try uploading again.');
            return false;
        }
    },

    async fetchAndUpdateSelectedTags() {
        try {
            console.log('Fetching selected tags...');
            const response = await fetch('/api/selected-tags');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const selectedTags = await response.json();
            
            if (!selectedTags || !Array.isArray(selectedTags)) {
                console.warn('No selected tags found - data may not be loaded yet');
                this.updateSelectedTags([]);
                return true;
            }
            
            console.log(`Fetched ${selectedTags.length} selected tags`);
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
            // Use the filter options API
            const response = await fetch('/api/filter-options', {
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

        // Collect selected tags from the selected tags container
        const selectedTagsContainer = document.getElementById('selectedTags');
        const allCheckboxes = selectedTagsContainer.querySelectorAll('input[type="checkbox"].tag-checkbox');
        const allTags = Array.from(allCheckboxes).map(cb => cb.value);

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
            a.download = 'filtered_data.xlsx';
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
        console.log('TagManager.init() called');
        
        // Get DOM elements
        const fileInput = document.getElementById('fileInput');
        const fileDropZone = document.getElementById('fileDropZone');
        const generateBtn = document.getElementById('generateBtn');
        const btnMoveToSelected = document.getElementById('btnMoveToSelected');
        const btnMoveToAvailable = document.getElementById('btnMoveToAvailable');
        const undoMoveBtn = document.getElementById('undo-move-btn');
        const clearFiltersBtn = document.getElementById('clear-filters-btn');
        const availableTagsSearch = document.getElementById('availableTagsSearch');
        const selectedTagsSearch = document.getElementById('selectedTagsSearch');

        console.log('DOM elements found:', {
            fileInput: !!fileInput,
            fileDropZone: !!fileDropZone,
            generateBtn: !!generateBtn,
            btnMoveToSelected: !!btnMoveToSelected,
            btnMoveToAvailable: !!btnMoveToAvailable
        });

        if (fileInput) {
            console.log('Setting up file input event listener');
            fileInput.addEventListener('change', (event) => {
                console.log('File input change event triggered');
                const file = event.target.files[0];
                if (file) {
                    console.log('File selected:', file.name, file.size);
                    this.uploadFile(file);
                } else {
                    console.log('No file selected');
                }
            });
        } else {
            console.error('File input element not found!');
        }

        if (fileDropZone) {
            // Enhanced drag and drop is handled by enhanced-ui.js
            // This ensures compatibility with the new drag and drop zone
            fileDropZone.addEventListener('dragover', (event) => {
                event.preventDefault();
                event.target.classList.add('dragover');
            });

            fileDropZone.addEventListener('dragleave', (event) => {
                event.target.classList.remove('dragover');
            });

            fileDropZone.addEventListener('drop', (event) => {
                event.preventDefault();
                event.target.classList.remove('dragover');
                const file = event.dataTransfer.files[0];
                if (file) {
                    this.uploadFile(file);
                }
            });
        }

        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.debouncedGenerate());
        }
        if (btnMoveToSelected) {
            btnMoveToSelected.addEventListener('click', () => this.moveToSelected());
        }
        if (btnMoveToAvailable) {
            btnMoveToAvailable.addEventListener('click', () => this.moveToAvailable());
        }
        if (undoMoveBtn) {
            undoMoveBtn.addEventListener('click', () => this.undoMove());
        }
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => this.clearSelected());
        }

        if (availableTagsSearch) {
            availableTagsSearch.addEventListener('input', debounce(() => this.handleSearch('availableTags', 'availableTagsSearch'), 300));
        }
        if (selectedTagsSearch) {
            selectedTagsSearch.addEventListener('input', debounce(() => this.handleSearch('selectedTags', 'selectedTagsSearch'), 300));
        }

        // Initialize with empty state first, then check if data exists
        this.initializeEmptyState();
        
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
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter'];
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
        
        // Update table header if TagsTable is available
        setTimeout(() => {
            // Also update table header if TagsTable is available
            if (typeof TagsTable !== 'undefined' && TagsTable.updateTableHeader) {
                TagsTable.updateTableHeader();
            }
        }, 100);

        // JSON matching is now handled by the modal - removed old above-tags-list logic

        // --- Robust Tag Loading: Always fetch tags after init ---
        this.fetchAndUpdateAvailableTags();
        this.fetchAndUpdateSelectedTags();
    },

    // Initialize with empty state to prevent undefined errors
    initializeEmptyState() {
        console.log('Initializing empty state...');
        
        // Initialize with empty arrays to prevent undefined errors
        this.state.tags = [];
        this.state.originalTags = [];
        this.state.selectedTags = new Set();
        
        // Update UI with empty state
        this.debouncedUpdateAvailableTags([]);
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
            // Check if there are any available tags
            const response = await fetch('/api/available-tags');
            if (response.ok) {
                const tags = await response.json();
                if (tags && Array.isArray(tags) && tags.length > 0) {
                    console.log(`Found ${tags.length} existing tags, loading data...`);
                    
                    // Check if this is a default file being loaded
                    const initialDataElement = document.getElementById('initialData');
                    if (initialDataElement) {
                        try {
                            const initialData = JSON.parse(initialDataElement.getAttribute('data-initial'));
                            if (initialData && initialData.filename && initialData.filepath) {
                                // Show splash screen for default file loading
                                this.showExcelLoadingSplash(initialData.filename);
                                this.updateExcelLoadingStatus('Loading default file...');
                            }
                        } catch (e) {
                            console.log('No initial data found or error parsing:', e.message);
                        }
                    }
                    
                    // Load existing data with status updates
                    this.updateExcelLoadingStatus('Loading product data...');
                    await this.fetchAndUpdateAvailableTags();
                    
                    this.updateExcelLoadingStatus('Loading selected tags...');
                    await this.fetchAndUpdateSelectedTags();
                    
                    this.updateExcelLoadingStatus('Loading filters...');
                    await this.fetchAndPopulateFilters();
                    
                    // Final status update and hide splash screen
                    this.updateExcelLoadingStatus('Ready!');
                    setTimeout(() => {
                        this.hideExcelLoadingSplash();
                    }, 500);
                    
                    console.log('Existing data loaded successfully');
                    return;
                }
            }
        } catch (error) {
            console.log('No existing data found or error loading:', error.message);
        }
        
        console.log('No existing data found, waiting for file upload...');
    },

    // Debounced version of the label generation logic
    debouncedGenerate: debounce(async function() {
        // Check if tags are loaded before attempting generation
        if (!this.state.tags || !Array.isArray(this.state.tags) || this.state.tags.length === 0) {
            console.error('Cannot generate: No tags loaded. Please upload a file first.');
            Toast.show('error', 'No product data loaded. Please upload a file first.');
            return;
        }
        
        console.time('debouncedGenerate');
        const generateBtn = document.getElementById('generateBtn');
        const splashModal = document.getElementById('generationSplashModal');
        const splashCanvas = document.getElementById('generation-splash-canvas');
        if (!window._activeSplashInstance) window._activeSplashInstance = null;
        let splashInstance = null;
        try {
            // Get checked tags in lineage order from the selectedTags container
            const selectedTagsContainer = document.getElementById('selectedTags');
            const allCheckboxes = selectedTagsContainer.querySelectorAll('input[type="checkbox"].tag-checkbox');
            // Robust: always use canonical ProductName from state
            const checkedTags = Array.from(allCheckboxes)
              .filter(cb => cb.checked)
              .map(cb => {
                const tagObj = this.state.tags.find(
                  t => t['Product Name*'] === cb.value || t.ProductName === cb.value
                );
                return tagObj ? (tagObj.ProductName || tagObj['Product Name*']) : cb.value;
              });
            if (checkedTags.length === 0) {
                Toast.show('error', 'Please select at least one tag to generate');
                return;
            }
            // Get template, scale, and format info
            const templateType = document.getElementById('templateSelect')?.value || 'horizontal';
            const scaleFactor = parseFloat(document.getElementById('scaleInput')?.value) || 1.0;
            const outputFormat = document.getElementById('formatSelect')?.value || 'docx';
            if (window._activeSplashInstance && window._activeSplashInstance.stop) {
                window._activeSplashInstance.stop();
                window._activeSplashInstance = null;
            }
            if (splashCanvas) {
                const ctx = splashCanvas.getContext('2d');
                ctx && ctx.clearRect(0, 0, splashCanvas.width, splashCanvas.height);
                splashCanvas.style.display = 'block';
            }
            // Show generation splash modal
            if (splashModal && splashCanvas) {
                splashModal.style.display = 'flex';
                if (window.GenerationSplash) {
                    splashInstance = new window.GenerationSplash('generation-splash-canvas', {
                        width: 500,
                        height: 350,
                        labelCount: checkedTags.length,
                        templateType: templateType
                    });
                    window._activeSplashInstance = splashInstance;
                }
            }
            // Disable button and show loading spinner
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
            // Choose API endpoint based on format
            const apiEndpoint = outputFormat === 'pdf' ? '/api/generate-pdf' : '/api/generate';
            
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
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `generated_labels.${outputFormat}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error generating labels:', error);
            Toast.show('error', error.message || 'Failed to generate labels');
        } finally {
            // Hide splash modal and stop animation
            if (splashModal) splashModal.style.display = 'none';
            if (window._activeSplashInstance && window._activeSplashInstance.stop) {
                window._activeSplashInstance.stop();
                window._activeSplashInstance = null;
            }
            generateBtn.disabled = false;
            generateBtn.innerHTML = 'Generate Tags';
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
            Toast.show('error', 'No tags selected to move');
            return;
        }
        try {
            const response = await fetch('/api/move-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags: checked, direction: 'to_selected' })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to move tags');
            this.debouncedUpdateAvailableTags(data.available_tags);
            this.updateSelectedTags(data.selected_tags);
            this.state.selectedTags = new Set(data.selected_tags.map(tag => tag['Product Name*']));
            Toast.show('success', 'Moved tags to selected');
        } catch (error) {
            Toast.show('error', error.message || 'Failed to move tags');
        }
    },

    async moveToAvailable() {
        // Get checked tags in selectedTags
        const checked = Array.from(document.querySelectorAll('#selectedTags input[type="checkbox"].tag-checkbox:checked')).map(cb => cb.value);
        if (checked.length === 0) {
            Toast.show('error', 'No tags selected to move');
            return;
        }
        try {
            const response = await fetch('/api/move-tags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tags: checked, direction: 'to_available' })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to move tags');
            this.debouncedUpdateAvailableTags(data.available_tags);
            this.updateSelectedTags(data.selected_tags);
            this.state.selectedTags = new Set(data.selected_tags.map(tag => tag['Product Name*']));
            Toast.show('success', 'Moved tags to available');
        } catch (error) {
            Toast.show('error', error.message || 'Failed to move tags');
        }
    },

    async undoMove() {
        try {
            const response = await fetch('/api/undo-move', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Nothing to undo');
            this.debouncedUpdateAvailableTags(data.available_tags);
            this.updateSelectedTags(data.selected_tags);
            this.state.selectedTags = new Set(data.selected_tags.map(tag => tag['Product Name*']));
        } catch (error) {
        }
    },

    async clearSelected() {
        try {
            const response = await fetch('/api/clear-filters', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to clear');
            this.debouncedUpdateAvailableTags(data.available_tags);
            this.updateSelectedTags([]);
            this.state.selectedTags.clear();
        } catch (error) {
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

    async uploadFile(file) {
        const maxRetries = 2;
        let retryCount = 0;
        
        // Validate file type and size
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            Toast.show('error', 'Please select an Excel (.xlsx) file');
            return;
        }

        if (file.size > 16 * 1024 * 1024) {
            Toast.show('error', 'File size must be less than 16MB');
            return;
        }
        
        while (retryCount <= maxRetries) {
            try {
                console.log(`Starting file upload (attempt ${retryCount + 1}):`, file.name, 'Size:', file.size, 'bytes');
                
                // Show Excel loading splash screen
                this.showExcelLoadingSplash(file.name);
                
                // Show loading state
                this.updateUploadUI(`Uploading ${file.name}...`);
                
                // Update drag drop zone state
                const fileDropZone = document.getElementById('fileDropZone');
                if (fileDropZone) {
                    fileDropZone.classList.add('file-loading');
                }
                
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
                    
                    // Update drag drop zone success state
                    if (fileDropZone) {
                        fileDropZone.classList.remove('file-loading');
                        fileDropZone.classList.add('file-uploaded');
                        setTimeout(() => {
                            fileDropZone.classList.remove('file-uploaded');
                        }, 2000);
                    }
                    
                    return; // Success, exit retry loop
                } else if (response.ok) {
                    // Fallback for legacy response
                    this.updateUploadUI(file.name);
                    Toast.show('success', `File uploaded successfully!`);
                    
                    // Update drag drop zone success state
                    if (fileDropZone) {
                        fileDropZone.classList.remove('file-loading');
                        fileDropZone.classList.add('file-uploaded');
                        setTimeout(() => {
                            fileDropZone.classList.remove('file-uploaded');
                        }, 2000);
                    }
                    
                    return; // Success, exit retry loop
                } else {
                    console.error('Upload failed:', data.error);
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI('No file selected');
                    Toast.show('error', data.error || 'Upload failed');
                    
                    // Update drag drop zone error state
                    if (fileDropZone) {
                        fileDropZone.classList.remove('file-loading');
                        fileDropZone.classList.add('file-error');
                        setTimeout(() => {
                            fileDropZone.classList.remove('file-error');
                        }, 3000);
                    }
                    
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
                    Toast.show('error', errorMessage);
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
                    this.hideExcelLoadingSplash();
                    this.updateUploadUI(displayName, 'File ready!', 'success');
                    Toast.show('success', 'File uploaded and ready!');
                    
                    // Load the data - ensure all operations complete successfully
                    const availableTagsLoaded = await this.fetchAndUpdateAvailableTags();
                    const selectedTagsLoaded = await this.fetchAndUpdateSelectedTags();
                    await this.fetchAndPopulateFilters();
                    
                    if (!availableTagsLoaded) {
                        console.error('Failed to load available tags after upload');
                        Toast.show('error', 'Failed to load product data. Please try refreshing the page.');
                        return;
                    }
                    
                    console.log('Upload processing complete');
                    return;
                } else if (status === 'processing') {
                    // Still processing, show progress
                    this.updateUploadUI(`Processing ${displayName}...`);
                    this.updateExcelLoadingStatus('Processing Excel data...');
                    
                } else if (status === 'not_found') {
                    // File not found in processing status - might be a race condition
                    console.warn(`File not found in processing status: ${filename} (age: ${age}s, total files: ${totalFiles})`);
                    if (attempts < 15) { // Give it more attempts for race conditions (increased from 10)
                        this.updateUploadUI(`Processing ${displayName}...`);
                        this.updateExcelLoadingStatus('Waiting for processing to start...');
                    } else {
                        this.hideExcelLoadingSplash();
                        this.updateUploadUI('Upload failed', 'File processing status lost', 'error');
                        Toast.show('error', 'Upload failed: Processing status lost. Please try again.');
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
                    Toast.show('error', 'Upload failed: Network error. Please try again.');
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
        Toast.show('error', 'Upload timed out. Please try again.');
    },

    updateUploadUI(fileName, statusMessage, statusType) {
        const currentFileInfo = document.getElementById('currentFileInfo');
        if (currentFileInfo) {
            currentFileInfo.textContent = fileName;
            // Add tooltip for full path if it's a long path
            if (fileName.length > 50) {
                currentFileInfo.title = fileName;
            } else {
                currentFileInfo.title = '';
            }
            if (statusMessage) {
                currentFileInfo.classList.add(statusType);
                setTimeout(() => {
                    currentFileInfo.classList.remove(statusType);
                }, 3000);
            }
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
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter'];
        
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

    getFilterTypeFromId(filterId) {
        const idToType = {
            'vendorFilter': 'vendor',
            'brandFilter': 'brand',
            'productTypeFilter': 'productType',
            'lineageFilter': 'lineage',
            'weightFilter': 'weight'
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
            { id: 'weightFilter', label: 'Weight' }
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
        const filterIds = ['vendorFilter', 'brandFilter', 'productTypeFilter', 'lineageFilter', 'weightFilter'];
        
        filterIds.forEach(filterId => {
            const filterElement = document.getElementById(filterId);
            if (filterElement) {
                filterElement.value = '';
            }
        });
        
        // Apply the cleared filters
        this.applyFilters();
        this.renderActiveFilters();
        
    }
};

// Expose TagManager to global scope
window.TagManager = TagManager;
window.updateAvailableTags = TagManager.debouncedUpdateAvailableTags.bind(TagManager);
window.updateFilters = TagManager.updateFilters.bind(TagManager);

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
TagManager.debouncedUpdateAvailableTags(TagManager.state.tags);
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
            Toast.show('error', 'Failed to fetch JSON from URL.');
            return;
        }
    }
    try {
        json = JSON.parse(jsonText);
    } catch (e) {
        Toast.show('error', 'Invalid JSON format. Please paste valid JSON.');
        return;
    }
    // ... continue with your matching logic ...
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    const initialData = getInitialData();
    console.log('Loading initial data:', initialData);
    
    // Initialize sticky filter bar behavior
    initializeStickyFilterBar();
    
    if (initialData) {
        // Initialize filters
        if (initialData.filters) {
            try {
                if (typeof window.updateFilters === 'function') {
                    window.updateFilters(initialData.filters);
                } else {
                    console.error('updateFilters function not found');
                }
            } catch (error) {
                console.error('Error updating filters:', error);
                showError('Error loading filters');
            }
        }
        
        // Initialize available tags
        if (initialData.available_tags) {
            try {
                if (typeof window.updateAvailableTags === 'function') {
                    window.updateAvailableTags(initialData.available_tags);
                } else {
                    console.error('updateAvailableTags function not found');
                }
            } catch (error) {
                console.error('Error updating tags:', error);
                showError('Error loading tags');
            }
        }
        
        // Update current file display
        const currentFileElement = document.getElementById('currentFile');
        if (currentFileElement && initialData.filename) {
            currentFileElement.textContent = initialData.filename;
        }
    } else {
        console.log('No initial data available');
    }

    // Note: Select All event listeners are now handled in the TagManager._updateAvailableTags and updateSelectedTags methods
    // to ensure proper state management and prevent duplicate listeners

    // Always clear selected tags on page load
    if (window.TagManager && TagManager.state && TagManager.state.selectedTags) {
        TagManager.state.selectedTags.clear();
        if (typeof TagManager.updateSelectedTags === 'function') {
            TagManager.updateSelectedTags([]);
        }
    }
});

// Initialize sticky filter bar behavior
function initializeStickyFilterBar() {
    const stickyFilterBar = document.querySelector('.sticky-filter-bar');
    const tagList = document.getElementById('availableTags');
    
    if (stickyFilterBar && tagList) {
        // Use Intersection Observer for better performance
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    stickyFilterBar.classList.remove('is-sticky');
                } else {
                    stickyFilterBar.classList.add('is-sticky');
                }
            });
        }, {
            threshold: 0,
            rootMargin: '-1px 0px 0px 0px'
        });
        
        // Observe the card header to determine when to make filter bar sticky
        const cardHeader = document.querySelector('.card-header');
        if (cardHeader) {
            observer.observe(cardHeader);
        }
        
        // Fallback for older browsers
        const handleScroll = () => {
            if (cardHeader) {
                const headerRect = cardHeader.getBoundingClientRect();
                if (headerRect.bottom <= 0) {
                    stickyFilterBar.classList.add('is-sticky');
                } else {
                    stickyFilterBar.classList.remove('is-sticky');
                }
            }
        };
        
        // Use passive listeners for better performance
        tagList.addEventListener('scroll', handleScroll, { passive: true });
        window.addEventListener('scroll', handleScroll, { passive: true });
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

// Ensure double-template class is toggled on body for Double template
const templateSelect = document.getElementById('templateSelect');
if (templateSelect) {
  templateSelect.addEventListener('change', function() {
    // Remove all template classes first
    document.body.classList.remove('double-template', 'vertical-template');
    
    // Add appropriate class based on selection
    if (this.value === 'double') {
      document.body.classList.add('double-template');
    } else if (this.value === 'vertical') {
      document.body.classList.add('vertical-template');
    }
  });
  // On page load, set class if template is already selected
  if (templateSelect.value === 'double') {
    document.body.classList.add('double-template');
  } else if (templateSelect.value === 'vertical') {
    document.body.classList.add('vertical-template');
  } else {
    document.body.classList.remove('double-template', 'vertical-template');
  }
}

// Helper to parse weight strings like '1g', '3.5g', '14g', '28g', etc.
function parseWeight(weightStr) {
    if (!weightStr) return 0;
    // Extract number and unit
    const match = weightStr.match(/([\d.]+)\s*(mg|g|oz|lb|kg)?/i);
    if (!match) return 0;
    let value = parseFloat(match[1]);
    let unit = (match[2] || '').toLowerCase();
    // Convert all to grams for sorting
    if (unit === 'mg') value = value / 1000;
    if (unit === 'kg') value = value * 1000;
    if (unit === 'oz') value = value * 28.3495;
    if (unit === 'lb') value = value * 453.592;
    return value;
}