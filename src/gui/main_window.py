import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional
import logging

from src.core.data.excel_processor import ExcelProcessor
from src.gui.components.filter_panel import FilterPanel
from src.gui.components.tag_panel import TagPanel
from src.gui.components.action_panel import ActionPanel

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.excel_processor = ExcelProcessor()
        self._setup_ui()
        self._bind_events()
        # Removed _load_default_file() call - no automatic file loading
        
    def _setup_ui(self):
        self.root.title("AGT Price Tag Transformer")
        self.root.geometry("1200x800")
        self.root.configure(bg="#228B22")
        
        # Create frames
        self.left_frame = FilterPanel(self.root, self.on_filter_change)
        self.center_frame = TagPanel(self.root)
        self.right_frame = ActionPanel(self.root)
        
        self._layout_frames()

    # Removed _load_default_file method - no automatic file loading