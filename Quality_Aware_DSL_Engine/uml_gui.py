#!/usr/bin/env python3

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from PIL import Image, ImageTk
import math
import re
import os
import tempfile
import json
from datetime import datetime
from typing import Dict, Any, Optional

# Import quality-aware modules
from uml_extract import (
    preprocess_text, 
    extract_uml_elements_with_quality,
    extract_raw_dsl_from_text,
    apply_validation_and_repair,
    validate_dsl_only,
    get_dsl_state,
    generate_quality_aware_dsl,
    save_dsl_to_file,
    load_dsl_from_file,
    QualityAwareDSL,
    QualityMetrics,
    ValidationError
)
from uml_to_code import (
    generate_code_with_fallback, 
    get_available_models,
    parse_dsl_to_uml_with_quality,
    is_ollama_available,
    generate_dsl_text_from_object
)
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# ===============================
# Main Application
# ===============================

class UMLDiagramApp:
    def __init__(self, root):
        """Initialize the graphical interface to display the UML diagram."""
        self.root = root
        self.root.title("Text2UML2Code - Quality-Aware DSL (v3.2)")
        self.root.geometry("1400x950")
        self.root.configure(bg="#f8f9fa")
        
        # Language selection for code generation
        self.selected_language = tk.StringVar(value="Python")
        
        # Model selection for code generation
        self.selected_model = tk.StringVar(value="gemma:2b")
        
        # List of available models
        self.models_list = [
            "gemma:2b",
            "phi3:mini", 
            "codellama:7b",
            "mistral:7b",
            "neural-chat:7b",
            "llama3:8b",
            "deepseek-coder:6.7b"
        ]
        
        # DSL storage
        self.raw_dsl: Optional[QualityAwareDSL] = None  # Raw DSL from BERT
        self.corrected_dsl: Optional[QualityAwareDSL] = None  # DSL after correction
        self.current_display_dsl: Optional[QualityAwareDSL] = None  # Currently displayed DSL
        self.uml_data = None
        self.class_positions = {}
        self.current_text = ""
        self.is_manual_edit = False  # Flag to track if DSL was manually edited
        self._suppress_edit_event = False  # Flag to suppress edit events during programmatic updates

        # --- Banner image below title ---
        try:
            banner_image = Image.open("logo3.jpg")
            banner_image = banner_image.resize((1280, 70), Image.Resampling.LANCZOS)
            self.banner_photo = ImageTk.PhotoImage(banner_image)
            tk.Label(self.root, image=self.banner_photo, bg="#f8f9fa", borderwidth=0, highlightthickness=0).pack(fill="x", padx=0, pady=(0, 0))
        except:
            pass

        # Combined area: Specifications + DSL
        self.create_spec_and_dsl_area()
        
        # UML Canvas area
        self.create_uml_canvas()
        
        # Code and Logs area
        self.create_code_and_logs()
        
        # Quality Metrics panel
        self.create_quality_panel()
        
        # Bind events to detect manual DSL edits
        self.dsl_editor.bind('<<Modified>>', self.on_dsl_edited)
        
        # Refresh models list at startup
        self.root.after(1000, self.refresh_models)

    # ----------------------------
    # Combined area: Specifications + DSL
    # ----------------------------
    def create_spec_and_dsl_area(self):
        container = tk.Frame(self.root, bg="#f8f9fa")
        container.pack(fill="x", pady=(1, 0))

        container.columnconfigure(0, weight=50)
        container.columnconfigure(1, weight=50)
        container.rowconfigure(0, weight=1)

        # === Specifications Zone ===
        spec_frame = tk.Frame(container, bg="#f8f9fa")
        spec_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2))

        spec_header = tk.Frame(spec_frame, bg="#f8f9fa")
        spec_header.pack(fill="x", pady=(0, 0))
        tk.Label(spec_header, text="Requirements", font=("Broadway", 12, "bold"), fg="#4682B4", bg="#f8f9fa").pack(side="left", padx=0)

        tk.Button(spec_header, text="Clear All", command=self.clear_all, width=10, height=1, 
                font=("Arial", 9, "bold"), bg="tomato", fg="white", activebackground="steelblue", activeforeground="white").pack(side="right", padx=(2, 20))
        tk.Button(spec_header, text="Analyze Text", command=self.analyze_text, width=12, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        tk.Button(spec_header, text="Load File", command=self.load_file, width=10, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)

        self.text_entry = scrolledtext.ScrolledText(spec_frame, wrap=tk.WORD, height=6, 
                                                    font=("times new roman", 11), bg="#ffffff", padx=10, pady=4)
        self.text_entry.pack(fill="both", expand=True, padx=2, pady=1)

        # === DSL Zone ===
        dsl_frame = tk.Frame(container, bg="#f8f9fa")
        dsl_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 5))

        dsl_header = tk.Frame(dsl_frame, bg="#f8f9fa")
        dsl_header.pack(fill="x", pady=(0, 0))
        tk.Label(dsl_header, text="Quality-Aware DSL", font=("Broadway", 12, "bold"), fg="#4682B4", bg="#f8f9fa").pack(side="left", padx=0)
        
        # DSL Control Buttons
        tk.Button(dsl_header, text="Save UML", command=self.save_diagram, width=9, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=(2, 20))
        tk.Button(dsl_header, text="Generate UML", command=self.generate_uml_from_dsl, width=12, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        tk.Button(dsl_header, text="Save DSL", command=self.save_dsl_to_file, width=9, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        tk.Button(dsl_header, text="Auto Correct", command=self.auto_correct_dsl, width=12, height=1, 
                font=("Arial", 9, "bold"), bg="#F39C12", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        tk.Button(dsl_header, text="Validate DSL", command=self.validate_dsl, width=12, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        
        self.dsl_editor = scrolledtext.ScrolledText(dsl_frame, wrap=tk.WORD, height=6, 
                                                    font=("Consolas", 11), bg="#ffffff", padx=10, pady=4)
        self.dsl_editor.pack(fill="both", expand=True, padx=2, pady=1)
        
        # DSL status indicator - This shows the current state dynamically
        self.dsl_status = tk.Label(dsl_frame, text="🔴 DSL not loaded", font=("Arial", 9, "bold"), 
                                   fg="#E74C3C", bg="#f8f9fa")
        self.dsl_status.pack(anchor="e", padx=10, pady=(2, 0))

    # ----------------------------
    # UML Canvas area
    # ----------------------------
    def create_uml_canvas(self):
        frame = tk.Frame(self.root, bg="#f8f9fa")
        frame.pack(fill="both", expand=False, padx=0, pady=(0, 0))

        canvas_container = tk.Frame(frame)
        canvas_container.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(canvas_container, bg="white", highlightthickness=1, 
                                highlightbackground="#cccccc", scrollregion=(0, 0, 2000, 2000))
        v_scrollbar = tk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set)
        
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

    # ----------------------------
    # Code and Logs area
    # ----------------------------
    def create_code_and_logs(self):
        bottom_frame = tk.Frame(self.root, bg="#f8f9fa")
        bottom_frame.pack(fill="both", expand=True, padx=5, pady=0)

        # === Code Zone ===
        code_frame = tk.Frame(bottom_frame, bg="#f8f9fa")
        code_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        code_header = tk.Frame(code_frame, bg="#f8f9fa")
        code_header.pack(fill="x", pady=(1, 1))
        tk.Label(code_header, text="Generated Code", font=("Broadway", 12, "bold"), fg="#4682B4", bg="#f8f9fa").pack(side="left", padx=0)
        
        tk.Button(code_header, text="Save Code", command=self.save_as_code, width=10, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=(2, 20))

        # Selectors frame (language + model)
        selectors_frame = tk.Frame(code_header, bg="#f8f9fa")
        selectors_frame.pack(side="right", padx=0)
        
        # Language selector
        lang_frame = tk.Frame(selectors_frame, bg="#f8f9fa")
        lang_frame.pack(side="left", padx=0)
        lang_options = ["Python", "Java", "C#"]
        lang_menu = ttk.Combobox(lang_frame, textvariable=self.selected_language, values=lang_options, 
                                  state="readonly", width=8, font=("Arial", 9))
        lang_menu.pack(side="left", padx=2)
        
        # LLM model selector
        model_frame = tk.Frame(selectors_frame, bg="#f8f9fa")
        model_frame.pack(side="left", padx=0)
        tk.Label(model_frame, text="Using", font=("Arial", 9, "bold"), bg="#f8f9fa").pack(side="left", padx=2)
        self.model_menu = ttk.Combobox(model_frame, textvariable=self.selected_model, values=self.models_list, 
                                        state="readonly", width=18, font=("Arial", 9))
        self.model_menu.pack(side="left", padx=2)
        
        # Refresh models button
        tk.Button(model_frame, text="↑↓", command=self.refresh_models, width=3, height=1, 
                 font=("Arial", 9, "bold"), bg="tomato", fg="white", activebackground="steelblue", activeforeground="white").pack(side="left", padx=2)
        
        tk.Button(code_header, text="Generate Code", command=self.generate_code_from_uml, width=12, height=1, 
                 font=("Arial", 9, "bold"), bg="#4682B4", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=2)
        
        self.code_viewer = scrolledtext.ScrolledText(code_frame, wrap=tk.WORD, height=8, 
                                                      font=("Consolas", 11), bg="#f7f7f7", fg="#0028DC", padx=10, pady=4)
        self.code_viewer.pack(fill="both", expand=True)

        # === Logs Zone ===
        log_frame = tk.Frame(bottom_frame, bg="#f8f9fa", width=400)
        log_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        log_header = tk.Frame(log_frame, bg="#f8f9fa")
        log_header.pack(fill="x", pady=(1, 1))
        tk.Label(log_header, text="Execution Log", font=("Broadway", 12, "bold"), fg="#4682B4", bg="#f8f9fa").pack(side="left", padx=0)
        tk.Button(log_header, text="Save Report", command=self.save_report, width=10, height=1, 
                font=("Arial", 9, "bold"), bg="steelblue", fg="white", activebackground="tomato", activeforeground="white").pack(side="right", padx=(2, 20))
        tk.Button(log_header, text="Save Errors", command=self.save_error_report, width=10, height=1, 
                font=("Arial", 9, "bold"), bg="tomato", fg="white", activebackground="steelblue", activeforeground="white").pack(side="right", padx=2)

        self.report_viewer = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=8, 
                                                        font=("Consolas", 10), bg="#f1f3f4", 
                                                        padx=10, pady=4, state=tk.DISABLED)
        self.report_viewer.pack(fill="both", expand=True)

    # ----------------------------
    # Quality Metrics panel
    # ----------------------------
    def create_quality_panel(self):
        """Create a panel to display quality metrics."""
        quality_frame = tk.Frame(self.root, bg="#f8f9fa", height=60)
        quality_frame.pack(fill="x", padx=5, pady=(2, 2))
        quality_frame.pack_propagate(False)
        
        panel = tk.Frame(quality_frame, bg="#e8f0fe", relief=tk.RIDGE, bd=1)
        panel.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.quality_labels = {}
        
        metrics = [
            ("reliability", "🔒 Reliability", "#2E86C1"),
            ("classes", "📦 Classes", "#27AE60"),
            ("relations", "🔗 Relations", "#E67E22"),
            ("errors", "❌ Errors", "#E74C3C"),
            ("repairs", "🔄 Repairs", "#8E44AD"),
            ("status", "📊 Status", "#2C3E50")
        ]
        
        for i, (key, label, color) in enumerate(metrics):
            frame = tk.Frame(panel, bg="#e8f0fe")
            frame.pack(side="left", padx=10, pady=2, expand=True)
            
            tk.Label(frame, text=label, font=("Arial", 9, "bold"), fg="#333", bg="#e8f0fe").pack(side="left")
            
            value_label = tk.Label(frame, text="—", font=("Consolas", 10, "bold"), fg=color, bg="#e8f0fe", width=12)
            value_label.pack(side="left", padx=5)
            
            self.quality_labels[key] = value_label

    # ==================================================
    # Helper method to update DSL editor programmatically
    # ==================================================
    
    def _set_dsl_editor_content(self, content: str):
        """Set DSL editor content programmatically without triggering edit events."""
        self._suppress_edit_event = True
        self.dsl_editor.delete(1.0, tk.END)
        self.dsl_editor.insert(1.0, content)
        self.dsl_editor.edit_modified(False)
        self._suppress_edit_event = False
        self.highlight_dsl_keywords()

    # ==================================================
    # Main metrics update method
    # ==================================================
    
    def update_all_metrics(self, dsl: QualityAwareDSL = None):
        """
        Update all quality metrics and status display.
        This method is called after any modification to the DSL.
        """
        if dsl is None:
            dsl = self.current_display_dsl
        
        if not dsl:
            for label in self.quality_labels.values():
                label.config(text="—")
            if not self.is_manual_edit:
                self.dsl_status.config(text="🔴 DSL not loaded", fg="#E74C3C")
            else:
                self.dsl_status.config(text="✏️ MANUAL EDIT - No DSL loaded", fg="#F39C12")
            return
        
        # Calculate metrics
        reliability = dsl.get_reliability_score() if hasattr(dsl, 'get_reliability_score') else 0.0
        total_errors = len(dsl.validation_errors) if hasattr(dsl, 'validation_errors') else 0
        total_repairs = len(dsl.repair_history) if hasattr(dsl, 'repair_history') else 0
        total_classes = len(dsl.classes) if hasattr(dsl, 'classes') else 0
        total_relations = len(dsl.relations) if hasattr(dsl, 'relations') else 0
        
        # Determine status
        is_raw = dsl.metadata.get('is_raw', False)
        is_valid = total_errors == 0
        
        # Check if DSL has been manually edited
        if self.is_manual_edit:
            status = "✏️ MANUAL EDIT"
            status_color = "#F39C12"
        elif is_raw:
            status = "🔍 RAW (BERT)"
            status_color = "#F39C12"
        elif is_valid:
            status = "✅ VALID"
            status_color = "#27AE60"
        else:
            status = "⚠️ INVALID"
            status_color = "#E74C3C"
        
        # Update quality labels
        self.quality_labels["reliability"].config(text=f"{reliability:.3f}")
        self.quality_labels["classes"].config(text=str(total_classes))
        self.quality_labels["relations"].config(text=str(total_relations))
        self.quality_labels["errors"].config(text=str(total_errors))
        self.quality_labels["repairs"].config(text=str(total_repairs))
        self.quality_labels["status"].config(text=status, fg=status_color)
        
        # Update the DSL status label with the current state
        status_text = f"{status} - {total_classes} classes, {total_relations} relations"
        self.dsl_status.config(text=status_text, fg=status_color)

    # ==================================================
    # Event handlers
    # ==================================================
    
    def on_dsl_edited(self, event):
        """Handle manual DSL editor modifications."""
        if self._suppress_edit_event:
            return
        
        if self.dsl_editor.edit_modified():
            # Check if the content actually changed (not just cursor movement)
            current_content = self.dsl_editor.get("1.0", tk.END).strip()
            if self.current_display_dsl:
                old_content = generate_quality_aware_dsl(self.current_display_dsl).strip()
                if current_content != old_content:
                    self.is_manual_edit = True
                    # Re-parse and update metrics
                    try:
                        dsl = parse_dsl_to_uml_with_quality(current_content)
                        self.current_display_dsl = dsl
                        self.update_all_metrics(dsl)
                    except Exception as e:
                        # If parsing fails, just update status
                        self.dsl_status.config(text="✏️ MANUAL EDIT - Invalid DSL", fg="#F39C12")
                else:
                    # Content hasn't changed, reset the flag
                    self.is_manual_edit = False
                    self.update_all_metrics(self.current_display_dsl)
            else:
                # No DSL loaded, but content exists - manual edit
                if current_content:
                    self.is_manual_edit = True
                    self.dsl_status.config(text="✏️ MANUAL EDIT - No DSL loaded", fg="#F39C12")
            
            # Reset the modified flag
            self.dsl_editor.edit_modified(False)

    # ==================================================
    # Utility functions
    # ==================================================
    
    def refresh_models(self):
        """Refresh the list of available models from Ollama."""
        try:
            available = get_available_models()
            if available:
                self.models_list = available
                self.model_menu['values'] = self.models_list
                self.add_log(f"🔄 Models refreshed: {', '.join(available[:5])}{'...' if len(available) > 5 else ''}", "info")
            else:
                self.add_log("⚠️ No models found. Please run 'ollama pull gemma:2b'", "warning")
        except Exception as e:
            self.add_log(f"❌ Error refreshing models: {e}", "error")
    
    def clear_all(self):
        """Clear all areas."""
        if (not self.text_entry.get("1.0", tk.END).strip() and
            not self.dsl_editor.get("1.0", tk.END).strip() and
            not self.code_viewer.get("1.0", tk.END).strip() and
            not self.report_viewer.get("1.0", tk.END).strip() and
            not self.canvas.find_all()):
            messagebox.showinfo("Nothing to clear", "All areas are already empty.")
            return

        confirm = messagebox.askyesno("Confirm deletion", "Are you sure you want to clear all areas?")
        if not confirm:
            return

        report_was_disabled = False
        try:
            if self.report_viewer.cget('state') == tk.DISABLED:
                report_was_disabled = True
                self.report_viewer.config(state=tk.NORMAL)
        except:
            pass

        self.text_entry.delete("1.0", tk.END)
        self._set_dsl_editor_content("")
        self.canvas.delete("all")
        self.code_viewer.delete("1.0", tk.END)
        self.report_viewer.delete("1.0", tk.END)
        
        if report_was_disabled:
            self.report_viewer.config(state=tk.DISABLED)
        
        self.raw_dsl = None
        self.corrected_dsl = None
        self.current_display_dsl = None
        self.uml_data = None
        self.class_positions = {}
        self.is_manual_edit = False
        self.update_all_metrics(None)

    def load_file(self):
        """Load a text file."""
        self.raw_dsl = None
        self.corrected_dsl = None
        self.current_display_dsl = None
        self.uml_data = None
        self.canvas.delete("all")
        self.text_entry.delete("1.0", tk.END)
        self._set_dsl_editor_content("")
        self.code_viewer.delete("1.0", tk.END)
        self.report_viewer.delete("1.0", tk.END)
        self.is_manual_edit = False
        self.update_all_metrics(None)

        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.text_entry.insert(tk.END, content)
                    self.current_text = content
                    self.add_log(f"📂 File loaded: {file_path}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read the file: {e}")

    def save_dsl_to_file(self):
        """Save DSL to file with format selection."""
        dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
        if not dsl_text:
            messagebox.showwarning("Warning", "No DSL content to save.")
            return

        format_choice = messagebox.askquestion(
            "Save format", 
            "Save as JSON format (with metadata and quality metrics)?\n\n"
            "Yes = JSON (full quality data)\n"
            "No = TXT (human-readable)"
        )
        
        is_json = (format_choice == "yes")
        
        if is_json:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json", 
                filetypes=[("JSON file", "*.json"), ("All files", "*.*")]
            )
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt", 
                filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
            )
        
        if file_path:
            dsl_to_save = self.corrected_dsl if self.corrected_dsl else self.current_display_dsl
            try:
                if is_json and dsl_to_save:
                    if hasattr(dsl_to_save, 'metadata'):
                        dsl_to_save.metadata['saved_date'] = datetime.now().isoformat()
                    save_dsl_to_file(dsl_to_save, file_path, "json")
                    messagebox.showinfo("Success", f"Quality-aware DSL saved to {file_path}")
                    self.add_log(f"💾 Quality DSL saved as JSON to {file_path}", "success")
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(dsl_text)
                    messagebox.showinfo("Success", f"DSL saved as text to {file_path}")
                    self.add_log(f"💾 DSL saved as text to {file_path}", "success")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save DSL: {e}")
                self.add_log(f"❌ Error saving DSL: {e}", "error")

    def add_log(self, msg, level="info"):
        """Add a log message with color coding."""
        self.report_viewer.config(state=tk.NORMAL)
        
        colors = {
            "info": "#0078D7",
            "success": "#0A9B00",
            "warning": "#E6A100",
            "error": "#FF6347"
        }
        
        color = colors.get(level, "#333333")
        
        tag_name = f"log_{level}_{len(self.report_viewer.get('1.0', tk.END))}"
        self.report_viewer.tag_config(tag_name, foreground=color, font=("Consolas", 10, "normal"))
        
        self.report_viewer.insert(tk.END, msg + "\n", tag_name)
        self.report_viewer.see(tk.END)
        
        self.report_viewer.config(state=tk.DISABLED)
    
    def save_error_report(self):
        """Save only error and warning messages."""
        self.report_viewer.config(state=tk.NORMAL)
        content = self.report_viewer.get("1.0", tk.END).strip()
        self.report_viewer.config(state=tk.DISABLED)
        
        if not content:
            messagebox.showwarning("Warning", "The log is empty.")
            return
        
        filtered_lines = []
        for line in content.splitlines():
            if any(keyword in line.lower() for keyword in ["error", "warning", "❌", "⚠️", "fail", "invalid"]):
                filtered_lines.append(line)
        
        if not filtered_lines:
            messagebox.showinfo("No issues", "No errors or warnings found in the log.")
            return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", 
                                                  filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("ERRORS AND WARNINGS REPORT\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("\n".join(filtered_lines))
                messagebox.showinfo("Success", f"Error report saved to {file_path}")
                self.add_log(f"📝 Error report saved to {file_path}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report: {e}")
    
    def is_text_in_english(self, text: str) -> bool:
        """Check if text is in English."""
        try:
            language = detect(text)
            return language == "en"
        except LangDetectException:
            return False

    # ==================================================
    # Main pipeline functions
    # ==================================================

    def analyze_text(self):
        """Analyze text and generate raw DSL from BERT."""
        self.canvas.delete("all")
        self.code_viewer.delete("1.0", tk.END)
        
        input_text = self.text_entry.get("1.0", tk.END).strip()

        if not input_text:
            messagebox.showwarning("Warning", "No text provided for analysis.")
            return

        if not self.is_text_in_english(input_text):
            messagebox.showwarning("Warning", "The text provided is not in English.")
            return

        try:
            self.add_log("🔍 Analyzing text with BERT extraction...", "info")
            self.current_text = input_text
            
            # Reset manual edit flag
            self.is_manual_edit = False
            
            # 1. Extract raw DSL from BERT
            self.raw_dsl = extract_raw_dsl_from_text(input_text)
            self.current_display_dsl = self.raw_dsl
            
            # 2. Mark as raw
            self.raw_dsl.metadata['is_raw'] = True
            
            # 3. Display DSL in editor
            dsl_code = generate_quality_aware_dsl(self.raw_dsl)
            self._set_dsl_editor_content(dsl_code)
            
            # 4. Display UML diagram from raw DSL
            self.uml_data = {
                'classes': self.raw_dsl.classes,
                'relations': self.raw_dsl.relations
            }
            self.draw_uml_diagram()
            
            # 5. Update all metrics
            self.update_all_metrics(self.raw_dsl)
            
            # 6. Logs
            self.add_log(f"✅ Raw DSL extracted from BERT!", "success")
            self.add_log(f"   📦 {len(self.raw_dsl.classes)} classes detected", "info")
            self.add_log(f"   🔗 {len(self.raw_dsl.relations)} relations detected", "info")
            self.add_log(f"   🔍 DSL is in RAW state - click 'Validate DSL' or 'Auto Correct'", "warning")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error during analysis: {e}")
            self.add_log(f"❌ Error: {e}", "error")
            import traceback
            traceback.print_exc()

    def validate_dsl(self):
        """Validate the current DSL without applying corrections."""
        # Get the current DSL from the editor
        dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
        if not dsl_text:
            messagebox.showwarning("Warning", "No DSL to validate.")
            return
        
        try:
            self.add_log("🔍 Validating DSL...", "info")
            
            # Parse the current DSL from editor
            dsl = parse_dsl_to_uml_with_quality(dsl_text)
            
            is_valid, errors = validate_dsl_only(dsl)
            
            # Update the current display DSL
            self.current_display_dsl = dsl
            
            # Reset manual edit flag if validation is performed
            if self.is_manual_edit:
                self.is_manual_edit = False
            
            if errors:
                self.add_log(f"⚠️ {len(errors)} validation errors found:", "warning")
                for error in errors[:5]:
                    self.add_log(f"   [{error.error_type.value}] {error.message}", "warning")
                    if error.suggestion:
                        self.add_log(f"      → {error.suggestion}", "info")
            else:
                self.add_log("✅ DSL is valid! No errors found.", "success")
            
            # Update display with all metrics
            self.update_all_metrics(dsl)
            
            # Display errors in DSL editor
            dsl_code = generate_quality_aware_dsl(dsl)
            self._set_dsl_editor_content(dsl_code)
            
            messagebox.showinfo(
                "Validation Complete",
                f"Validation completed.\n\n"
                f"Total Errors: {len(errors)}\n"
                f"Status: {'✅ Valid' if is_valid else '⚠️ Invalid'}"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Validation failed: {e}")
            self.add_log(f"❌ Validation error: {e}", "error")

    def auto_correct_dsl(self):
        """Apply automatic corrections to the DSL."""
        # Get the current DSL from the editor
        dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
        if not dsl_text:
            messagebox.showwarning("Warning", "No DSL to correct.")
            return
        
        try:
            self.add_log("🔧 Applying automatic corrections...", "info")
            
            # Parse the current DSL from editor
            dsl = parse_dsl_to_uml_with_quality(dsl_text)
            
            # Apply corrections
            text = self.current_text if self.current_text else ""
            self.corrected_dsl = apply_validation_and_repair(dsl, text)
            self.current_display_dsl = self.corrected_dsl
            
            # Reset manual edit flag
            self.is_manual_edit = False
            
            # Update display
            dsl_code = generate_quality_aware_dsl(self.corrected_dsl)
            self._set_dsl_editor_content(dsl_code)
            
            # Update diagram
            self.uml_data = {
                'classes': self.corrected_dsl.classes,
                'relations': self.corrected_dsl.relations
            }
            self.draw_uml_diagram()
            
            # Update all metrics
            self.update_all_metrics(self.corrected_dsl)
            
            # Logs
            errors = len(self.corrected_dsl.validation_errors)
            repairs = len(self.corrected_dsl.repair_history)
            corrections = len(self.corrected_dsl.metadata.get('corrections_applied', []))
            
            self.add_log(f"✅ Auto-correction completed!", "success")
            self.add_log(f"   🔄 {repairs} repair iterations performed", "info")
            self.add_log(f"   ✏️ {corrections} corrections applied", "info")
            
            if errors > 0:
                self.add_log(f"   ⚠️ {errors} errors remaining (need manual review)", "warning")
            else:
                self.add_log(f"   ✅ No errors remaining - DSL is valid!", "success")
            
            messagebox.showinfo(
                "Auto-Correction Complete",
                f"Correction completed.\n\n"
                f"Repair iterations: {repairs}\n"
                f"Corrections applied: {corrections}\n"
                f"Remaining errors: {errors}\n"
                f"Status: {'✅ Valid' if errors == 0 else '⚠️ Needs review'}"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Correction failed: {e}")
            self.add_log(f"❌ Correction error: {e}", "error")

    def generate_uml_from_dsl(self):
        """Generate UML diagram from the current DSL."""
        # Get the current DSL from the editor
        dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
        
        if not dsl_text:
            messagebox.showwarning("Warning", "No DSL content to generate UML from.")
            return
        
        try:
            self.add_log("🎨 Generating UML diagram from DSL...", "info")
            
            # Parse the current DSL from editor
            dsl = parse_dsl_to_uml_with_quality(dsl_text)
            
            # Validate the DSL to check if it's valid - this acts as user validation
            is_valid, errors = validate_dsl_only(dsl)
            
            # Update the current display DSL
            self.current_display_dsl = dsl
            
            # Reset manual edit flag if the DSL was successfully parsed
            if self.is_manual_edit:
                self.is_manual_edit = False
                self.add_log("   📝 Manual edits incorporated into UML diagram", "info")
            
            self.uml_data = {
                'classes': dsl.classes,
                'relations': dsl.relations
            }
            
            if not self.uml_data['classes']:
                self.add_log("⚠️ No classes detected in DSL.", "warning")
                messagebox.showwarning(
                    "Warning", 
                    "No classes detected in DSL.\n\n"
                    "Make sure your DSL follows this format:\n"
                    "Class ClassName:\n"
                    "    Attributes: attr1, attr2\n"
                    "    Methods: method1(), method2()\n\n"
                    "Relation: Source type Target"
                )
                # Update status to show it's invalid
                self.update_all_metrics(dsl)
                return
            
            self.canvas.delete("all")
            self.class_positions.clear()
            self.draw_uml_diagram()
            
            num_classes = len(self.uml_data['classes'])
            num_relations = len(self.uml_data.get('relations', []))
            
            self.add_log(f"✅ UML diagram generated successfully!", "success")
            self.add_log(f"   📦 {num_classes} class(es) displayed", "info")
            self.add_log(f"   🔗 {num_relations} relationship(s) displayed", "info")
            
            reliability = dsl.get_reliability_score() if hasattr(dsl, 'get_reliability_score') else 0
            self.add_log(f"   Reliability Score: {reliability:.3f}", "info")
            
            # Update the DSL editor with any formatting changes
            formatted_dsl = generate_quality_aware_dsl(dsl)
            if formatted_dsl != dsl_text:
                self._set_dsl_editor_content(formatted_dsl)
                self.add_log("   📝 DSL formatting updated", "info")
            
            # Update all metrics
            self.update_all_metrics(dsl)
            
            # Override the status to show "VALIDATED BY USER" 
            # This indicates that the user clicked Generate UML which implies validation
            if is_valid:
                status_text = f"✅ VALIDATED BY USER - {num_classes} classes, {num_relations} relations"
                self.dsl_status.config(text=status_text, fg="#27AE60")
                self.quality_labels["status"].config(text="✅ VALIDATED BY USER", fg="#27AE60")
                self.add_log("   ✅ DSL VALIDATED BY USER - diagram generated successfully!", "success")
            else:
                status_text = f"⚠️ VALIDATED BY USER (with {len(errors)} errors) - {num_classes} classes, {num_relations} relations"
                self.dsl_status.config(text=status_text, fg="#E67E22")
                self.quality_labels["status"].config(text="⚠️ VALIDATED WITH ERRORS", fg="#E67E22")
                self.add_log(f"   ⚠️ DSL VALIDATED BY USER with {len(errors)} errors - diagram generated", "warning")
            
            # Show validation summary in a message box if there are errors
            if errors:
                error_summary = "\n".join([f"  • {e.message}" for e in errors[:5]])
                if len(errors) > 5:
                    error_summary += f"\n  ... and {len(errors) - 5} more errors"
                
                messagebox.showwarning(
                    "Validation Warnings",
                    f"DSL contains {len(errors)} validation issue(s):\n\n{error_summary}\n\n"
                    f"Diagram has been generated but may not be accurate.\n"
                    f"Click 'Auto Correct' to fix these issues."
                )
            else:
                messagebox.showinfo(
                    "Validation Successful",
                    f"DSL is VALID!\n\n"
                    f"Classes: {num_classes}\n"
                    f"Relations: {num_relations}\n"
                    f"Reliability Score: {reliability:.3f}\n\n"
                    f"Diagram generated successfully."
                )
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate UML: {e}")
            self.add_log(f"❌ Error: {e}", "error")
            import traceback
            traceback.print_exc()

    # ==================================================
    # Code Generation
    # ==================================================

    def highlight_code(self, lang: str):
        """Apply syntax highlighting to generated code."""
        for tag in self.code_viewer.tag_names():
            self.code_viewer.tag_delete(tag)
        
        colors = {
            "keyword": "#0077cc",
            "string": "#008000",
            "comment": "#999999",
            "class": "#8b008b",
            "func": "#cc5500"
        }
        
        for tag, color in colors.items():
            self.code_viewer.tag_config(tag, foreground=color)
        
        code = self.code_viewer.get("1.0", "end-1c")
        
        if lang.lower() == "python":
            keywords = r"\b(False|class|finally|is|return|None|continue|for|lambda|try|True|def|from|nonlocal|while|and|del|global|not|with|as|elif|if|or|yield|assert|else|import|pass|break|except|in|raise)\b"
            comment = r"#.*"
            string = r"(\".*?\"|\'.*?\')"
        elif lang.lower() == "java":
            keywords = r"\b(abstract|assert|boolean|break|byte|case|catch|char|class|continue|default|do|double|else|enum|extends|final|finally|float|for|if|implements|import|instanceof|int|interface|long|native|new|null|package|private|protected|public|return|short|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|void|volatile|while)\b"
            comment = r"//.*|/\*[\s\S]*?\*/"
            string = r"(\".*?\"|\'.*?\')"
        elif lang.lower() in ["c#", "csharp"]:
            keywords = r"\b(abstract|as|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|virtual|void|volatile|while)\b"
            comment = r"//.*|/\*[\s\S]*?\*/"
            string = r"(\".*?\"|\'.*?\')"
        else:
            return
        
        for match in re.finditer(keywords, code):
            self.code_viewer.tag_add("keyword", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(comment, code):
            self.code_viewer.tag_add("comment", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(string, code):
            self.code_viewer.tag_add("string", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(r"\bclass\b", code):
            self.code_viewer.tag_add("class", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(r"\b(def|void|function)\b", code):
            self.code_viewer.tag_add("func", f"1.0+{match.start()}c", f"1.0+{match.end()}c")

    def generate_code_from_uml(self):
        """Generate code from UML using selected LLM model."""
        if not self.current_display_dsl:
            # Try to parse the current DSL from editor
            dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
            if dsl_text:
                try:
                    self.current_display_dsl = parse_dsl_to_uml_with_quality(dsl_text)
                except Exception as e:
                    messagebox.showwarning("Warning", "Invalid DSL. Please check the format.")
                    self.add_log(f"❌ Invalid DSL format: {e}", "error")
                    return
            else:
                messagebox.showwarning("Warning", "No DSL/UML model to generate code from.")
                return
        
        dsl_text = self.dsl_editor.get("1.0", tk.END).strip()
        
        if not dsl_text:
            messagebox.showwarning("Warning", "No DSL content to generate code from.")
            return
        
        language = self.selected_language.get()
        selected_model = self.selected_model.get()
        
        use_llm = is_ollama_available()
        
        if not use_llm:
            self.add_log("⚠️ Ollama not available, using local code generation (Python only)", "warning")
            if language != "Python":
                self.add_log(f"⚠️ Local generation only supports Python. Switching to Python.", "warning")
                language = "Python"
                self.selected_language.set("Python")
        
        self.add_log(f"🔧 Generating {language} code with model: {selected_model}...", "info")
        
        self.code_viewer.delete(1.0, tk.END)
        self.code_viewer.insert(tk.END, f"⏳ Generating {language} code with {selected_model}... Please wait.\n")
        self.code_viewer.update_idletasks()
        self.root.update()
        
        try:
            code, used_llm = generate_code_with_fallback(dsl_text, language, use_llm=use_llm, model=selected_model)
            
            self.code_viewer.delete(1.0, tk.END)
            
            if code and len(code) > 50:
                self.code_viewer.insert(tk.END, code)
                self.highlight_code(language)
                
                if used_llm:
                    self.add_log(f"✅ {language} code generated successfully with {selected_model}!", "success")
                else:
                    self.add_log(f"✅ {language} code generated using local fallback.", "success")
            else:
                self.code_viewer.insert(tk.END, f"# Error: No code generated\n# Please check the UML model\n\n{dsl_text}")
                self.add_log(f"⚠️ No code generated. Check the UML model.", "warning")
            
        except Exception as e:
            self.code_viewer.delete(1.0, tk.END)
            self.code_viewer.insert(tk.END, f"Error generating code: {str(e)}")
            self.add_log(f"❌ Error generating {language} code: {e}", "error")
            messagebox.showerror("Error", f"Failed to generate code: {e}")

    def save_report(self):
        """Save report to file."""
        self.report_viewer.config(state=tk.NORMAL)
        content = self.report_viewer.get("1.0", tk.END).strip()
        self.report_viewer.config(state=tk.DISABLED)
        
        if not content:
            messagebox.showwarning("Warning", "The report is empty.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".txt", 
                                                  filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to {file_path}")
                self.add_log(f"💾 Report saved to {file_path}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report: {e}")

    def save_as_code(self):
        """Save generated code to file."""
        code = self.code_viewer.get("1.0", tk.END).strip()
        if not code:
            messagebox.showwarning("Warning", "No code to save.")
            return

        language = self.selected_language.get().lower()
        extensions = {
            "python": ".py",
            "java": ".java",
            "c#": ".cs"
        }
        ext = extensions.get(language, ".txt")

        file_path = filedialog.asksaveasfilename(defaultextension=ext, 
                                                  filetypes=[(f"{language} files", f"*{ext}"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                messagebox.showinfo("Success", f"Code saved to {file_path}")
                self.add_log(f"💾 {language} code saved to {file_path}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save code: {e}")

    def highlight_dsl_keywords(self):
        """Apply syntax highlighting to DSL keywords."""
        patterns = {
            r'\b(Class|class)\b': '#4682B4',
            r'\b(Attributes|attributes)\b': '#4682B4',
            r'\b(Methods|methods)\b': '#4682B4',
            r'\b(Relation|relation)\b': '#4682B4',
            r'\b(Quality|Quality Metrics|Confidence|Reliability)\b': '#27AE60',
            r'\b(Validation Report|Repair History|Error)\b': '#E74C3C',
            r'\b(HIGH|MEDIUM|LOW|VERY_LOW)\b': '#8E44AD',
            r'\b(CORRECTIONS APPLIED|AUTO)\b': '#F39C12'
        }
        
        for tag in self.dsl_editor.tag_names():
            self.dsl_editor.tag_delete(tag)
        
        for i, (pattern, color) in enumerate(patterns.items()):
            tag_name = f"keyword_{i}"
            self.dsl_editor.tag_config(tag_name, foreground=color, font=("Consolas", 11, "bold"))
            
            content = self.dsl_editor.get("1.0", tk.END)
            for match in re.finditer(pattern, content, re.IGNORECASE):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                self.dsl_editor.tag_add(tag_name, start_idx, end_idx)
        
        content = self.dsl_editor.get("1.0", tk.END)
        class_pattern = r'Class\s+(\w+)'
        
        self.dsl_editor.tag_config("class_name", foreground="#2D2D2D", font=("Consolas", 11, "bold"))
        
        for match in re.finditer(class_pattern, content):
            class_name_start = match.start(1)
            class_name_end = match.end(1)
            start_idx = f"1.0+{class_name_start}c"
            end_idx = f"1.0+{class_name_end}c"
            self.dsl_editor.tag_add("class_name", start_idx, end_idx)

    # ==================================================
    # UML drawing logic
    # ==================================================
    
    def draw_uml_diagram(self):
        """Draw UML classes and relationships."""
        self.canvas.delete("all")
        self.class_positions.clear()

        class_x = 50
        class_y = 50
        class_width = 140
        class_spacing = 180
        line_height = 18
        padding = 10

        if not self.uml_data or not self.uml_data.get('classes'):
            self.canvas.create_text(400, 200, text="No UML classes to display.\nClick 'Analyze Text' first.", 
                                    font=("Arial", 14), fill="#999", anchor="c")
            return

        classes_data = self.uml_data.get('classes', {})
        
        if isinstance(classes_data, dict):
            classes = [{'name': k, 'attributes': v.get('attributes', []), 
                       'methods': v.get('methods', [])} 
                      for k, v in classes_data.items()]
        else:
            classes = classes_data

        for cls_data in classes:
            cls_name = cls_data.get('name', '')
            attributes = cls_data.get('attributes', [])
            methods = cls_data.get('methods', [])

            attr_height = line_height * len(attributes) if attributes else line_height
            method_height = line_height * len(methods) if methods else line_height
            name_height = 30
            class_height = name_height + attr_height + method_height + padding

            self.canvas.create_rectangle(
                class_x, class_y,
                class_x + class_width, class_y + class_height,
                fill="#D4E6F1", outline="black", width=1
            )

            self.canvas.create_rectangle(
                class_x, class_y,
                class_x + class_width, class_y + name_height,
                fill="#5DADE2", outline="black", width=1
            )
            self.canvas.create_text(
                class_x + class_width / 2,
                class_y + name_height / 2,
                text=cls_name, font=("Arial", 11, "bold"), fill="white", anchor="c"
            )

            attr_y = class_y + name_height + 5
            for attr in attributes:
                self.canvas.create_text(
                    class_x + 10, attr_y, anchor="nw",
                    text=f"- {attr}", font=("Arial", 9), fill="#2C3E50"
                )
                attr_y += line_height

            method_y = class_y + name_height + attr_height + 5
            for method in methods:
                method_name = method.replace("()", "").strip()
                if method_name:
                    self.canvas.create_text(
                        class_x + 10, method_y, anchor="nw",
                        text=f"+ {method_name}()", font=("Arial", 9), fill="#2C3E50"
                    )
                    method_y += line_height

            self.class_positions[cls_name] = {
                "x": class_x, "y": class_y,
                "width": class_width, "height": class_height,
                "center_x": class_x + class_width / 2,
                "center_y": class_y + class_height / 2
            }

            class_x += class_spacing
            if class_x + class_width > self.canvas.winfo_width():
                class_x = 50
                class_y += class_height + 50

        if self.uml_data.get('relations'):
            self.draw_relations()

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def draw_relations(self):
        """Draw UML relations."""
        if not self.uml_data.get("relations"):
            return

        # Draw each relation individually to preserve source -> target order
        for relation in self.uml_data["relations"]:
            source = relation.get("source")
            target = relation.get("target")
            rel_type = relation.get("type", "").lower()
            
            if source in self.class_positions and target in self.class_positions:
                src = self.class_positions[source]
                tgt = self.class_positions[target]
                
                if source == target:
                    self.draw_reflexive_relation(src)
                else:
                    # Calculate connection points based on class positions
                    # Start point is always the source, end point is the target
                    if abs(src["center_y"] - tgt["center_y"]) < 50:
                        if src["center_x"] < tgt["center_x"]:
                            start_x = src["x"] + src["width"]
                            start_y = src["center_y"]
                            end_x = tgt["x"]
                            end_y = tgt["center_y"]
                        else:
                            start_x = src["x"]
                            start_y = src["center_y"]
                            end_x = tgt["x"] + tgt["width"]
                            end_y = tgt["center_y"]
                    else:
                        if src["center_y"] < tgt["center_y"]:
                            start_x = src["center_x"]
                            start_y = src["y"] + src["height"]
                            end_x = tgt["center_x"]
                            end_y = tgt["y"]
                        else:
                            start_x = src["center_x"]
                            start_y = src["y"]
                            end_x = tgt["center_x"]
                            end_y = tgt["y"] + tgt["height"]
                    
                    # For inheritance, composition, aggregation,
                    # the symbol is always on the TARGET side
                    if rel_type == "inheritance":
                        self.draw_inheritance_arrow(start_x, start_y, end_x, end_y)
                    elif rel_type == "composition":
                        self.draw_composition_diamond(start_x, start_y, end_x, end_y, filled=True)
                    elif rel_type == "aggregation":
                        self.draw_composition_diamond(start_x, start_y, end_x, end_y, filled=False)
                    else:
                        self.draw_connection(start_x, start_y, end_x, end_y, rel_type)

    def draw_connection(self, start_x, start_y, end_x, end_y, rel_type):
        """Draw a connection between two points."""
        if rel_type == "inheritance":
            self.draw_inheritance_arrow(start_x, start_y, end_x, end_y)
        elif rel_type == "composition":
            self.draw_composition_diamond(start_x, start_y, end_x, end_y, filled=True)
        elif rel_type == "aggregation":
            self.draw_composition_diamond(start_x, start_y, end_x, end_y, filled=False)
        elif rel_type == "dependency":
            self.canvas.create_line(start_x, start_y, end_x, end_y, dash=(4, 2), fill="#E67E22", width=1, arrow=tk.LAST)
        else:
            self.canvas.create_line(start_x, start_y, end_x, end_y, fill="#555555", width=1)

    def draw_inheritance_arrow(self, start_x, start_y, end_x, end_y):
        """Draw inheritance arrow (triangle at target end)."""
        # Draw the line first
        self.canvas.create_line(start_x, start_y, end_x, end_y, fill="#555555", width=1)
        
        # Calculate angle and draw triangle at the END point (target)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        arrow_size = 12
        
        tip_x = end_x
        tip_y = end_y
        base_x = end_x - arrow_size * math.cos(angle)
        base_y = end_y - arrow_size * math.sin(angle)
        
        left_x = base_x - arrow_size/2 * math.sin(angle)
        left_y = base_y + arrow_size/2 * math.cos(angle)
        right_x = base_x + arrow_size/2 * math.sin(angle)
        right_y = base_y - arrow_size/2 * math.cos(angle)
        
        self.canvas.create_polygon(tip_x, tip_y, left_x, left_y, right_x, right_y, 
                                    fill="white", outline="#555555", width=1)

    def draw_composition_diamond(self, start_x, start_y, end_x, end_y, filled=False):
        """Draw composition or aggregation diamond at the target end."""
        # Draw the line first
        self.canvas.create_line(start_x, start_y, end_x, end_y, fill="#555555", width=1)
        
        # Calculate angle and draw diamond at the END point (target)
        angle = math.atan2(end_y - start_y, end_x - start_x)
        diamond_size = 8
        
        # The diamond is placed at the target end
        diamond_x = end_x - diamond_size * math.cos(angle)
        diamond_y = end_y - diamond_size * math.sin(angle)
        
        diamond_points = [
            end_x, end_y,  # Tip points to target
            diamond_x + diamond_size * math.cos(angle + math.pi/2), 
            diamond_y + diamond_size * math.sin(angle + math.pi/2),
            diamond_x - diamond_size * math.cos(angle), 
            diamond_y - diamond_size * math.sin(angle),
            diamond_x + diamond_size * math.cos(angle - math.pi/2), 
            diamond_y + diamond_size * math.sin(angle - math.pi/2)
        ]
        
        fill_color = "#555555" if filled else "white"
        self.canvas.create_polygon(diamond_points, fill=fill_color, outline="#555555", width=1)

    def draw_reflexive_relation(self, class_pos):
        """Draw reflexive relation."""
        x = class_pos["x"] + class_pos["width"]
        y = class_pos["y"]
        
        arc_x = x - 160
        arc_y = y - 30
        arc_width = 40
        arc_height = 40
        
        center_x = arc_x + arc_width/2
        center_y = arc_y + arc_height/2
        radius = arc_width/2
        
        end_angle = 270
        end_angle_rad = math.radians(end_angle)
        
        arrow_x = center_x + radius * math.cos(end_angle_rad)
        arrow_y = center_y + radius * math.sin(end_angle_rad)
        
        self.canvas.create_arc(arc_x, arc_y, arc_x + arc_width, arc_y + arc_height, 
                                start=-30, extent=300, style="arc", 
                                outline="#555555", width=1)
        
        tangent_angle = end_angle_rad + math.pi/2
        arrow_dx = 8 * math.cos(tangent_angle)
        arrow_dy = 8 * math.sin(tangent_angle)
        
        self.canvas.create_line(arrow_x, arrow_y, 
                                arrow_x + arrow_dx, arrow_y + arrow_dy,
                                arrow=tk.LAST, fill="#555555", width=1, arrowshape=(8,10,5))

    def save_diagram(self):
        """Save UML diagram as high-quality PNG."""
        items = self.canvas.find_all()
        if not items:
            messagebox.showwarning("Warning", "No diagram to save.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".png", 
                                                filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if not file_path:
            return

        try:
            bbox = self.canvas.bbox("all")
            if not bbox:
                messagebox.showwarning("Warning", "No content found in diagram.")
                return
                
            x1, y1, x2, y2 = bbox
            
            padding = 50
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = x2 + padding
            y2 = y2 + padding
            
            width = int(x2 - x1)
            height = int(y2 - y1)
            
            dpi = 300
            scale = dpi / 72.0
            
            scaled_width = int(width * scale)
            scaled_height = int(height * scale)
            
            ps_file = tempfile.mktemp(".ps")
            
            self.canvas.postscript(
                file=ps_file,
                x=x1, y=y1,
                width=width, height=height,
                pagewidth=width - 1,
                pageheight=height - 1,
                colormode='color'
            )
            
            img = Image.open(ps_file)
            img = img.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
            
            img.save(file_path, "PNG", dpi=(dpi, dpi), quality=95, optimize=False)
            
            os.remove(ps_file)
            
            messagebox.showinfo("Success", f"High-quality diagram saved to:\n{file_path}")
            self.add_log(f"💾 High-quality diagram saved to {file_path}", "success")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save diagram: {e}")
            self.add_log(f"❌ Error saving diagram: {e}", "error")


def main():
    root = tk.Tk()
    app = UMLDiagramApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()