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

const TagManager = {
    state: {
        selectedTags: new Set(),
        initialized: false,
        filters: {},
        loading: false,
        brandCategories: new Map(),  // Add this for storing brand subcategories
        originalTags: [], // Store original tags separately
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

    createSelectAllCheckbox(container, tags) {
        const selectAllDiv = document.createElement('div');
        selectAllDiv.className = 'select-all-container mb-2 p-2';
        selectAllDiv.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
        selectAllDiv.style.borderRadius = '6px';
        selectAllDiv.style.border = '1px solid rgba(255, 255, 255, 0.2)';
        
        const selectAllCheckbox = document.createElement('input');
        selectAllCheckbox.type = 'checkbox';
        selectAllCheckbox.className = 'select-all-checkbox me-2';
        selectAllCheckbox.id = 'selectAllCheckbox_' + Math.random().toString(36).substr(2, 9);
        
        const selectAllLabel = document.createElement('label');
        selectAllLabel.htmlFor = selectAllCheckbox.id;
        selectAllLabel.textContent = 'Select All';
        selectAllLabel.style.color = '#fff';
        selectAllLabel.style.fontWeight = '500';
        
        selectAllDiv.appendChild(selectAllCheckbox);
        selectAllDiv.appendChild(selectAllLabel);
        
        // Add change event listener
        selectAllCheckbox.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            const checkboxes = container.querySelectorAll('.tag-checkbox');
            checkboxes.forEach(checkbox => {
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
            ));
        });
        
        return selectAllDiv;
    },

    updateFilters(filters) {
        if (!filters) return;
        
        // Debug log for filters
        console.log('Updating filters with:', filters);
        
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
            
            // Sort values alphabetically
            const sortedValues = Array.from(values).sort();
            
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
                weight: document.getElementById('weightFilter')?.value || '',
                strain: document.getElementById('strainFilter')?.value || ''
            };

            // Call the filter options API with current filters
            const response = await fetch('/api/filter-options', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filters: currentFilters })
            });

            if (!response.ok) {
                throw new Error('Failed to fetch filter options');
            }

            const filterOptions = await response.json();

            // Update each filter dropdown with new options
            const filterFieldMap = {
                vendor: 'vendorFilter',
                brand: 'brandFilter',
                productType: 'productTypeFilter',
                lineage: 'lineageFilter',
                weight: 'weightFilter',
                strain: 'strainFilter'
            };

            Object.entries(filterFieldMap).forEach(([filterType, filterId]) => {
                const filterElement = document.getElementById(filterId);
                if (!filterElement) {
                    return;
                }

                const currentValue = filterElement.value;
                const newOptions = filterOptions[filterType] || [];
                
                // Only update if options have actually changed
                const currentOptions = Array.from(filterElement.options).map(opt => opt.value).filter(v => v !== '');
                const optionsChanged = currentOptions.length !== newOptions.length || 
                                     !currentOptions.every((opt, i) => opt === newOptions[i]);
                
                if (optionsChanged) {
                    // Create new options HTML
                    const optionsHtml = `
                        <option value="">All</option>
                        ${newOptions.map(value => `<option value="${value}">${value}</option>`).join('')}
                    `;
                    
                    // Update the dropdown options
                    filterElement.innerHTML = optionsHtml;
                    
                    // Try to restore the previous selection if it's still valid
                    if (currentValue && newOptions.includes(currentValue)) {
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
            // Check vendor filter
            if (vendorFilter && vendorFilter !== '') {
                const tagVendor = tag.vendor || '';
                if (tagVendor.toLowerCase() !== vendorFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check brand filter - use productBrand field
            if (brandFilter && brandFilter !== '') {
                const tagBrand = tag.productBrand || '';
                if (tagBrand.toLowerCase() !== brandFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check product type filter
            if (productTypeFilter && productTypeFilter !== '') {
                const tagProductType = tag.productType || '';
                if (tagProductType.toLowerCase() !== productTypeFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check lineage filter
            if (lineageFilter && lineageFilter !== '') {
                const tagLineage = tag.lineage || '';
                if (tagLineage.toLowerCase() !== lineageFilter.toLowerCase()) {
                    return false;
                }
            }
            
            // Check weight filter
            if (weightFilter && weightFilter !== '') {
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
        
        tags.forEach(tag => {
            // Use the correct field names from the tag object
            let vendor = tag.vendor || '';
            let brand = tag.productBrand || this.extractBrand(tag);
            const productType = tag.productType || 'Unknown Type';
            const lineage = tag.lineage || 'MIXED';
            const weight = tag.weight || '';
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

            // Skip if no vendor
            if (!vendor) {
                skippedTags++;
                return;
            }

            // Normalize the tag data
            const normalizedTag = {
                ...tag,
                vendor: vendor.trim(),
                brand: brand.trim(),
                productType: productType.trim(),
                lineage: lineage.trim(),
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
        // Clear any existing timer before starting a new one
        if (this.updateAvailableTagsTimer) {
            clearTimeout(this.updateAvailableTagsTimer);
            this.updateAvailableTagsTimer = null;
        }
        console.time('updateAvailableTags');
        
        // Handle undefined or null tags
        if (!tags || !Array.isArray(tags)) {
            console.warn('updateAvailableTags called with invalid tags:', tags);
            tags = [];
        }
        
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

        // Clear existing content
        container.innerHTML = '';

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

        // Add select all selected checkbox - only add event listener once
        const selectAllSelected = document.getElementById('selectAllSelected');
        console.log('Select All Selected checkbox found:', selectAllSelected);
        if (selectAllSelected && !selectAllSelected.hasAttribute('data-listener-added')) {
            console.log('Adding event listener to Select All Selected checkbox');
            selectAllSelected.setAttribute('data-listener-added', 'true');
            selectAllSelected.addEventListener('change', (e) => {
                console.log('Select All Selected checkbox changed:', e.target.checked);
                const isChecked = e.target.checked;
                const tagCheckboxes = document.querySelectorAll('#selectedTags .tag-checkbox');
                console.log('Found selected tag checkboxes:', tagCheckboxes.length);
                tagCheckboxes.forEach(checkbox => {
                    checkbox.checked = isChecked;
                });
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
                            tags.forEach(tag => {
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
        // Set background color based on product type and lineage
        if (tag.productType === 'Paraphernalia') {
            tag.lineage = 'PARAPHERNALIA';
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
        // Remove 'by ...' up to the hyphen
        let rawName = tag['Product Name*'] || '';
        let cleanedName = rawName.replace(/ by [^-]+(?= -)/i, '');
        cleanedName = cleanedName.replace(/-/g, '\u2011');
        tagName.textContent = cleanedName;
        // Create lineage dropdown
        const lineageSelect = document.createElement('select');
        lineageSelect.className = 'form-select form-select-sm lineage-select lineage-dropdown lineage-dropdown-mini';
        // Remove inline width styles to allow CSS to control sizing
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
        lineageSelect.addEventListener('change', (e) => {
            const newLineage = e.target.value;
            this.handleLineageChange(tag['Product Name*'], newLineage);
        });
        tagElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            if (window.lineageEditor) {
                window.lineageEditor.openEditor(tag['Product Name*'], tag.lineage);
            }
        });
        tagInfo.appendChild(tagName);
        tagInfo.appendChild(lineageSelect);
        tagElement.appendChild(checkbox);
        tagElement.appendChild(tagInfo);
        row.appendChild(tagElement);
        return row;
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
        console.time('updateSelectedTags');
        console.log('updateSelectedTags called with tags:', tags);
        const container = document.getElementById('selectedTags');
        if (!container) {
            console.error('selectedTags container not found');
            console.timeEnd('updateSelectedTags');
            return;
        }

        // Clear existing content
        container.innerHTML = '';

        // Add global select all checkbox
        const topSelectAll = document.getElementById('selectAllSelected');
        if (topSelectAll) {
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
                            tags.forEach(tag => {
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
            const response = await fetch('/api/available-tags');
            if (!response.ok) {
                throw new Error('Failed to fetch available tags');
            }
            const tags = await response.json();
            this.state.selectedTags.clear();
            // Clear filter cache when new data is loaded
            this.state.filterCache = null;
            this.debouncedUpdateAvailableTags(tags);
        } catch (error) {
            console.error('Error fetching available tags:', error);
            Toast.show('error', 'Failed to load available tags');
        }
    },

    async fetchAndUpdateSelectedTags() {
        try {
            const response = await fetch('/api/selected-tags');
            if (!response.ok) {
                throw new Error('Failed to fetch selected tags');
            }
            const tags = await response.json();
            console.log('Fetched selected tags:', tags);
            this.state.selectedTags = new Set(tags);
            this.updateSelectedTags(tags);
        } catch (error) {
            console.error('Error fetching selected tags:', error);
            Toast.show('error', 'Failed to load selected tags');
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
        console.log('TagManager initialized');
        this.state.initialized = true;

        // Add null checks for all DOM elements
        const fileInput = document.getElementById('fileInput');
        const fileDropZone = document.getElementById('fileDropZone');
        const generateBtn = document.getElementById('generateBtn');
        const btnMoveToSelected = document.getElementById('btnMoveToSelected');
        const btnMoveToAvailable = document.getElementById('btnMoveToAvailable');
        const undoMoveBtn = document.getElementById('undo-move-btn');
        const clearFiltersBtn = document.getElementById('clear-filters-btn');
        const availableTagsSearch = document.getElementById('availableTagsSearch');
        const selectedTagsSearch = document.getElementById('selectedTagsSearch');

        if (fileInput) {
            fileInput.addEventListener('change', (event) => {
                const file = event.target.files[0];
                if (file) {
                    this.uploadFile(file);
                }
            });
        }

        if (fileDropZone) {
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

        this.fetchAndUpdateAvailableTags();
        this.fetchAndUpdateSelectedTags();
        this.fetchAndPopulateFilters();
        
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

        // JSON Paste Bar handler for selected tags
        const jsonPasteBtn = document.getElementById('jsonPasteMatchBtn');
        const jsonPasteInput = document.getElementById('jsonPasteInput');
        if (jsonPasteBtn && jsonPasteInput) {
            jsonPasteBtn.addEventListener('click', async () => {
                let json;
                try {
                    json = JSON.parse(jsonPasteInput.value);
                } catch (e) {
                    Toast.show('error', 'Invalid JSON. Please paste valid JSON.');
                    return;
                }
                try {
                    const response = await fetch('/api/match-json-tags', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(json)
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        Toast.show('error', result.error || 'JSON matching failed.');
                        return;
                    }
                    const allTags = TagManager.state.originalTags || [];
                    const matchedNames = new Set(result.matched.map(tag => tag['Product Name*']));
                    result.matched.forEach(tag => TagManager.state.selectedTags.add(tag['Product Name*']));
                    TagManager.updateSelectedTags(Array.from(TagManager.state.selectedTags).map(name => allTags.find(t => t['Product Name*'] === name)).filter(Boolean));
                    let msg = `Matched ${result.matched.length} tag(s).`;
                    if (result.unmatched && result.unmatched.length) {
                        msg += ` Unmatched: ${result.unmatched.join(', ')}`;
                    }
                    Toast.show('success', msg);
                } catch (err) {
                    Toast.show('error', 'Error matching JSON tags.');
                }
            });
        }
    },

    // Debounced version of the label generation logic
    debouncedGenerate: debounce(async function() {
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
            const checkedTags = Array.from(allCheckboxes).filter(cb => cb.checked).map(cb => cb.value);
            if (checkedTags.length === 0) {
                Toast.show('error', 'Please select at least one tag to generate');
                return;
            }
            // Get template and scale info
            const templateType = document.getElementById('templateSelect')?.value || 'horizontal';
            const scaleFactor = parseFloat(document.getElementById('scaleInput')?.value) || 1.0;
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
            const response = await fetch('/api/generate', {
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
            a.download = 'generated_labels.docx';
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

    async uploadFile(file) {
        try {
            // Only update file name
            this.updateUploadUI(file.name);
            
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Only update file name
                this.updateUploadUI(file.name);
                this.debouncedUpdateAvailableTags(data.available_tags);
                this.updateSelectedTags(data.selected_tags);
                this.updateFilters(data.filters);
            } else {
                // Only update file name to default
                this.updateUploadUI('No file selected');
                Toast.show('error', data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.updateUploadUI('No file selected');
            Toast.show('error', 'Upload failed');
        }
    },

    updateUploadUI(fileName) {
        const currentFileInfo = document.getElementById('currentFileInfo');
        if (currentFileInfo) currentFileInfo.textContent = fileName;
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
            
            // Always update filter options for cascading behavior
            // This ensures product type can be narrowed based on other filters
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
            const availableTags = document.getElementById('availableTags');
            if (availableTags && availableTags.parentNode) {
                availableTags.parentNode.insertBefore(container, availableTags);
            }
        }
        container.innerHTML = '';
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

setInterval(() => {
  document.querySelectorAll('select, .form-select').forEach(sel => {
  sel.style.width = '56px';
  sel.style.minWidth = '40px';
  sel.style.maxWidth = '56px';
  sel.style.fontSize = '0.9em';
  sel.style.paddingLeft = '2px';
  sel.style.paddingRight = '2px';
  sel.style.background = '#e0e0e0'; // Optional: make it visually obvious for testing
});

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
}, 100);

document.querySelectorAll('select, .form-select').forEach(sel => {
  sel.style.width = '56px';
  sel.style.minWidth = '40px';
  sel.style.maxWidth = '56px';
  sel.style.fontSize = '0.9em';
  sel.style.paddingLeft = '2px';
  sel.style.paddingRight = '2px';
  sel.style.background = '#e0e0e0'; // Optional: make it visually obvious for testing
});