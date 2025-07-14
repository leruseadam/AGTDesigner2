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
        const tagName = document.getElementById('editTagName').value;
        const newLineage = document.getElementById('editLineageSelect').value;

        if (!tagName || !newLineage) {
            Toast.show('error', 'Missing tag name or lineage');
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

            // Update the tag in TagManager state
            const tag = TagManager.state.tags.find(t => t['Product Name*'] === tagName);
            if (tag) {
                tag.lineage = newLineage;
            }

            // Update the tag in original tags as well
            const originalTag = TagManager.state.originalTags.find(t => t['Product Name*'] === tagName);
            if (originalTag) {
                originalTag.lineage = newLineage;
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
                const lineageSelect = item.querySelector('.lineage-select');
                if (lineageSelect) {
                    lineageSelect.value = newLineage;
                }

                // Update background color
                const newColor = TagManager.getLineageColor(newLineage);
                item.style.background = newColor;
            });

            // Close modal
            this.modal.hide();

            // Refresh the tag lists in the GUI
            TagManager.debouncedUpdateAvailableTags(TagManager.state.tags);
            TagManager.updateSelectedTags(
                Array.from(TagManager.state.selectedTags).map(
                    name => TagManager.state.tags.find(t => t['Product Name*'] === name)
                )
            );

        } catch (error) {
            console.error('Error:', error);
            Toast.show('error', error.message || 'Failed to update lineage');
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

// Force compact style on the modal's lineage select every 100ms while modal is open
(function forceCompactLineageSelect() {
  let interval = null;
  document.addEventListener('shown.bs.modal', function (event) {
    if (event.target && event.target.id === 'lineageEditorModal') {
      setTimeout(() => {
        var select = document.getElementById('lineageSelect');
        if (select) {
          // REMOVE all JS that sets style.width, style.minWidth, style.maxWidth, style.fontSize, style.paddingLeft, style.paddingRight
        }
      }, 200); // Wait for modal content to render
    }
  });
  document.addEventListener('hidden.bs.modal', function (event) {
    if (event.target && event.target.id === 'lineageEditorModal') {
      if (interval) clearInterval(interval);
    }
  });
})();