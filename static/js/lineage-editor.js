class LineageEditor {
    constructor() {
        this.modal = null;
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
        // Initialize once DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {
            this.modal = new bootstrap.Modal(document.getElementById('lineageEditorModal'));
            this.initializeEventListeners();
        });
    }

    initializeEventListeners() {
        // Save changes button handler
        const saveButton = document.getElementById('saveLineageChanges');
        if (saveButton) {
            saveButton.addEventListener('click', () => this.saveChanges());
        }
    }

    openEditor(tagName, currentLineage) {
        const tagNameInput = document.getElementById('tagName');
        const lineageSelect = document.getElementById('lineageSelect');
        
        if (tagNameInput && lineageSelect) {
            tagNameInput.value = tagName;
            
            // Populate dropdown with abbreviated options
            lineageSelect.innerHTML = '';
            const uniqueLineages = ['SATIVA','INDICA','HYBRID','HYBRID/SATIVA','HYBRID/INDICA','CBD','MIXED','PARA'];
            
            uniqueLineages.forEach(lin => {
                const option = document.createElement('option');
                option.value = lin;
                const abbr = LineageEditor.ABBREVIATED_LINEAGE[lin] || lin;
                option.textContent = abbr;
                if ((currentLineage === lin) || (lin === 'CBD' && currentLineage === 'CBD_BLEND')) {
                    option.selected = true;
                }
                lineageSelect.appendChild(option);
            });
            
            this.modal.show();
        } else {
            console.error('Lineage editor modal elements not found');
        }
    }

    async saveChanges() {
        const tagName = document.getElementById('tagName').value;
        const newLineage = document.getElementById('lineageSelect').value;

        if (!tagName || !newLineage) {
            if (window.Toast) {
                Toast.show('error', 'Missing tag name or lineage');
            }
            return;
        }

        try {
            const response = await fetch('/api/update-lineage', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tag_name: tagName,
                    "Product Name*": tagName,
                    lineage: newLineage
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update lineage');
            }

            // Update the tag in TagManager state if available
            if (window.TagManager && window.TagManager.state) {
                const tag = TagManager.state.tags.find(t => t['Product Name*'] === tagName);
                if (tag) {
                    tag.lineage = newLineage;
                }

                // Update the tag in original tags as well
                const originalTag = TagManager.state.originalTags.find(t => t['Product Name*'] === tagName);
                if (originalTag) {
                    originalTag.lineage = newLineage;
                }
            }

            // Update UI elements
            const tagElements = document.querySelectorAll(`[data-tag-name="${tagName}"], .tag-item:has([value="${tagName}"])`);
            tagElements.forEach(item => {
                // Update lineage data attribute
                item.dataset.lineage = newLineage;
                
                // Update lineage display text
                const lineageText = item.querySelector('.text-muted');
                if (lineageText) {
                    lineageText.textContent = `[${newLineage}]`;
                }

                // Update lineage dropdown if it exists
                const lineageSelect = item.querySelector('.lineage-select, .lineage-dropdown');
                if (lineageSelect) {
                    lineageSelect.value = newLineage;
                }

                // Update background color if TagManager is available
                if (window.TagManager && window.TagManager.getLineageColor) {
                    const newColor = TagManager.getLineageColor(newLineage);
                    item.style.background = newColor;
                }
            });

            // Close modal
            this.modal.hide();

            // Refresh the tag lists in the GUI if TagManager is available
            if (window.TagManager) {
                TagManager.debouncedUpdateAvailableTags(TagManager.state.tags);
                TagManager.updateSelectedTags(
                    Array.from(TagManager.state.selectedTags).map(
                        name => TagManager.state.tags.find(t => t['Product Name*'] === name)
                    )
                );
            }

            // Show success message
            if (window.Toast) {
                Toast.show('success', `Updated lineage for ${tagName}`);
            }

        } catch (error) {
            console.error('Error:', error);
            if (window.Toast) {
                Toast.show('error', error.message || 'Failed to update lineage');
            }
        }
    }

    static init() {
        window.lineageEditor = new LineageEditor();
    }
}

// Initialize the editor
LineageEditor.init();

// Export for use in other files
window.LineageEditor = LineageEditor;