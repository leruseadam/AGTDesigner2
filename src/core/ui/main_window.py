import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
import platform
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from .theme import Theme
from .components import (
    FileUploadPanel,
    FilterPanel,
    TagListPanel,
    ActionPanel
)

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.theme = Theme()
        self.default_file_loaded = False  # Add a flag
        self.setup_window()
        self.setup_theme()
        self.create_components()
        self.load_default_file()
        
    def setup_window(self):
        """Configure the main window properties"""
        self.root.title("AGT Price Tag Transformer")
        
        # DPI-aware scaling
        dpi_scaling = self.root.winfo_pixels('1i') / 72
        self.root.tk.call('tk', 'scaling', dpi_scaling)
        
        # Center and scale GUI
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        width = int(sw * 0.95)
        height = int(sh * 0.95)
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
    def setup_theme(self):
        """Apply the theme to the root window"""
        self.root.configure(bg=self.theme.colors['background'])
        
    def create_components(self):
        """Create and arrange the main GUI components"""
        # Main container
        self.main_frame = tk.Frame(self.root, bg=self.theme.colors['background'])
        self.main_frame.pack(fill="both", expand=True)

        # --- JSON Matching UI at the top ---
        self.json_frame = tk.Frame(self.main_frame, bg=self.theme.colors['surface'])
        self.json_frame.pack(fill="x", pady=(10, 0))
        self.theme.create_label(self.json_frame, "JSON Matching", font=self.theme.fonts['subheading'], bg=self.theme.colors['surface']).pack(anchor="w", padx=10)
        btn_frame = tk.Frame(self.json_frame, bg=self.theme.colors['surface'])
        btn_frame.pack(anchor="w", padx=10, pady=5)
        tk.Button(btn_frame, text="Match JSON", command=self.on_match_json, width=16).pack(side="left", padx=2)
        tk.Button(btn_frame, text="JSON Inventory", command=self.on_json_inventory, width=16).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Clear JSON", command=self.on_clear_json, width=16).pack(side="left", padx=2)
        # --- End JSON Matching UI ---

        # Create panels
        self.file_panel = FileUploadPanel(self.main_frame, self.theme)
        self.filter_panel = FilterPanel(self.main_frame, self.theme)
        self.tag_panel = TagListPanel(self.main_frame, self.theme)
        self.action_panel = ActionPanel(self.main_frame, self.theme)
        
        # Arrange panels
        self.file_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.filter_panel.pack(side="left", fill="y", padx=10, pady=10)
        self.tag_panel.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.action_panel.pack(side="right", fill="y", padx=10, pady=10)
        
    def load_default_file(self):
        """Load the most recent Excel file from Downloads folder, only if not already loaded."""
        if self.default_file_loaded:
            return
        downloads_dir = Path.home() / "Downloads"
        # First, try to find "A Greener Today" files
        matching_files = sorted(
            downloads_dir.glob("A Greener Today*.xlsx"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        if matching_files:
            default_path = str(matching_files[0])
            self.file_panel.set_file(default_path)
            try:
                self.file_panel.load_file(default_path)
                logging.info(f"Loaded default file: {default_path}")
                self.default_file_loaded = True
            except Exception as e:
                logging.error(f"Error loading default file: {e}")
                self._load_test_file()
        else:
            logging.debug("No 'A Greener Today' files found in Downloads folder")
            self._load_test_file()
            self.default_file_loaded = True
    
    def _load_test_file(self):
        """Load the test file as a fallback"""
        from src.core.utils.test_file_generator import create_test_file
        
        downloads_dir = Path.home() / "Downloads"
        test_file_path = downloads_dir / "testFile.xlsx"
        
        if not test_file_path.exists():
            # Create the test file if it doesn't exist
            created_path = create_test_file()
            if created_path:
                test_file_path = Path(created_path)
            else:
                logging.error("Failed to create test file")
                messagebox.showerror("Error", "Failed to create test file. Please upload a spreadsheet manually.")
                return
        
        try:
            self.file_panel.set_file(str(test_file_path))
            self.file_panel.load_file(str(test_file_path))
            logging.info(f"Loaded test file: {test_file_path}")
            messagebox.showinfo("Test File Loaded", 
                "No tag lists found. Loaded testFile.xlsx with sample data for demonstration.")
        except Exception as e:
            logging.error(f"Error loading test file: {e}")
            messagebox.showerror("Error", f"Failed to load test file: {e}")
            
    def run(self):
        """Start the main event loop"""
        self.root.mainloop()

    def handle_json_match(self, json_url):
        """Fetch and match JSON, then update the selected tags panel with matches."""
        from src.core.data.json_matcher import JSONMatcher
        # Assume file_panel has loaded the Excel file and has a DataFrame
        excel_processor = type('ExcelProcessor', (), {'df': self.file_panel.df})()
        matcher = JSONMatcher(excel_processor)
        try:
            matched_names = matcher.fetch_and_match(json_url)
            self.tag_panel.populate_selected_tags(matched_names)
            messagebox.showinfo("JSON Match", f"Matched {len(matched_names)} products.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to match JSON: {e}")

    def on_match_json(self):
        # TODO: Implement the logic to match JSON
        messagebox.showinfo("Match JSON", "Match JSON button clicked.")

    def on_json_inventory(self):
        # TODO: Implement the logic to show JSON inventory
        messagebox.showinfo("JSON Inventory", "JSON Inventory button clicked.")

    def on_clear_json(self):
        # TODO: Implement the logic to clear JSON matches
        messagebox.showinfo("Clear JSON", "Clear JSON button clicked.") 