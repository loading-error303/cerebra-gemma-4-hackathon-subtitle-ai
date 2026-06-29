import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
from translate_subs import extract_subtitles, translate_srt, merge_subtitles

class SubtitleTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Subtitle Translator")
        self.root.geometry("650x650")
        self.root.configure(bg="#fdfdfd")

        # Modern Palette
        self.bg_color = "#fdfdfd"
        self.card_bg = "#ffffff"
        self.accent_color = "#007AFF"  
        self.text_main = "#1d1d1f"     
        self.text_muted = "#86868b"    
        self.border_color = "#d2d2d7"
        self.error_color = "#ff3b30"   
        self.warning_color = "#ffcc00" 

        # Custom Styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        self.style.configure("TLabel", background=self.bg_color, font=("Segoe UI", 11), foreground=self.text_main)
        self.style.configure("CardLabel.TLabel", background=self.card_bg, font=("Segoe UI", 11), foreground=self.text_main)
        self.style.configure("Header.TLabel", font=("Segoe UI Semibold", 22), foreground=self.text_main, background=self.bg_color)
        
        self.video_path = tk.StringVar()
        
        main_container = ttk.Frame(root, padding="40")
        main_container.pack(expand=True, fill="both")

        header = ttk.Label(main_container, text="Subtitle Translator", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        sub_header = ttk.Label(main_container, text="Translate any video's subtitles in seconds", font=("Segoe UI", 12), foreground=self.text_muted)
        sub_header.pack(pady=(0, 40))

        card = ttk.Frame(main_container, style="Card.TFrame", padding="30")
        card.pack(fill="both", expand=True)
        
        self.video_label = ttk.Label(card, text="1. Select your video file", style="CardLabel.TLabel", font=("Segoe UI Semibold", 11))
        self.video_label.pack(anchor="w", pady=(0, 8))
        
        file_frame = ttk.Frame(card, style="Card.TFrame")
        file_frame.pack(fill="x", pady=(0, 30))
        
        self.video_entry = tk.Entry(
            file_frame, textvariable=self.video_path, font=("Segoe UI", 11),
            bg="#f5f5f7", fg=self.text_main, insertbackground=self.text_main,
            relief="flat", borderwidth=10, highlightthickness=0
        )
        self.video_entry.pack(side="left", expand=True, fill="x", padx=(0, 12))
        
        btn_browse = tk.Button(
            file_frame, text="Browse", command=self.browse_file,
            bg=self.card_bg, fg=self.accent_color, font=("Segoe UI Semibold", 10),
            relief="flat", highlightthickness=1, highlightbackground=self.border_color,
            padx=15, pady=5, cursor="hand2"
        )
        btn_browse.pack(side="right")

        self.lang_label = ttk.Label(card, text="2. Choose Target Language", style="CardLabel.TLabel", font=("Segoe UI Semibold", 11))
        self.lang_label.pack(anchor="w", pady=(0, 8))
        
        from deep_translator import GoogleTranslator
        supported_langs = GoogleTranslator().get_supported_languages(as_dict=True)
        sorted_langs = sorted(supported_langs.items())
        self.lang_names = [name.title() for name, code in sorted_langs]
        self.lang_map = {name.title(): code for name, code in sorted_langs}
        
        self.lang_container = ttk.Frame(card, style="Card.TFrame")
        self.lang_container.pack(fill="x", pady=(0, 30))
        
        self.lang_search = tk.Entry(
            self.lang_container, font=("Segoe UI", 11),
            bg="#f5f5f7", fg=self.text_main, relief="flat", borderwidth=10, highlightthickness=0
        )
        self.lang_search.pack(fill="x", pady=(0, 0))
        self.lang_search.insert(0, "English")
        self.lang_search.bind("<KeyRelease>", self.filter_languages)
        self.lang_search.bind("<FocusOut>", self.hide_list)
        
        self.list_frame = ttk.Frame(self.lang_container, style="Card.TFrame")
        self.list_frame.pack(fill="both", expand=True)
        self.list_frame.pack_forget() 
        
        self.lang_listbox = tk.Listbox(
            self.list_frame, font=("Segoe UI", 11), borderwidth=0, relief="flat",
            highlightthickness=0, selectbackground=self.accent_color,
            selectforeground="white", bg="#f5f5f7", fg=self.text_main
        )
        self.lang_listbox.pack(side="left", expand=True, fill="both")
        
        scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.lang_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.lang_listbox.config(yscrollcommand=scrollbar.set)
        self.lang_listbox.bind("<<ListboxSelect>>", self.on_list_select)

        self.btn_process = tk.Button(
            card, text="Replace Video", command=self.process_video,
            bg=self.accent_color, fg="white", font=("Segoe UI Semibold", 13),
            relief="flat", cursor="hand2", padx=30, pady=12
        )
        self.btn_process.pack(pady=20)

        self.status_var = tk.StringVar(value="Ready to process")
        self.status_label = ttk.Label(card, textvariable=self.status_var, foreground=self.text_muted, font=("Segoe UI", 10), style="CardLabel.TLabel")
        self.status_label.pack(pady=10)

        # Save main container for toggling
        self.main_container = main_container

    def show_loading_screen(self):
        self.main_container.pack_forget()
        
        self.loading_frame = ttk.Frame(self.root, padding="50")
        self.loading_frame.pack(expand=True, fill="both")
        
        # Center container for loading
        center_card = ttk.Frame(self.loading_frame, style="Card.TFrame", padding="50")
        center_card.place(relx=0.5, rely=0.5, anchor="center")
        
        ttk.Label(center_card, text="Processing Video", style="Header.TLabel").pack(pady=(0, 20))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            center_card, orient="horizontal", length=400, mode="determinate", variable=self.progress_var
        )
        self.progress_bar.pack(pady=20)
        
        self.loading_status_var = tk.StringVar(value="Starting AI engines...")
        self.loading_status_label = ttk.Label(
            center_card, textvariable=self.loading_status_var, 
            foreground=self.text_muted, font=("Segoe UI", 12), style="CardLabel.TLabel"
        )
        self.loading_status_label.pack(pady=10)

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.flv *.wmv"), ("All files", "*.*")])
        if filename:
            self.video_path.set(filename)
            self.video_entry.config(highlightthickness=1, highlightbackground=self.border_color)

    def filter_languages(self, event):
        query = self.lang_search.get().lower()
        if query:
            self.list_frame.pack(fill="both", expand=True)
            filtered = [name for name in self.lang_names if query in name.lower()]
            self.lang_listbox.delete(0, tk.END)
            for name in filtered:
                self.lang_listbox.insert(tk.END, name)
            self.lang_listbox.config(height=min(len(filtered), 7))
            if filtered:
                self.lang_listbox.selection_set(0)
        else:
            self.hide_list()

    def on_list_select(self, event):
        selection = self.lang_listbox.curselection()
        if selection:
            selected_lang = self.lang_listbox.get(selection[0])
            self.lang_search.delete(0, tk.END)
            self.lang_search.insert(0, selected_lang)
            self.hide_list()

    def hide_list(self, event=None):
        self.list_frame.pack_forget()

    def process_video(self):
        video_file = self.video_path.get()
        lang_name = self.lang_search.get()
        
        valid = True
        if not video_file:
            self.video_label.config(text="1. Select your video file *", foreground=self.error_color)
            self.video_entry.config(highlightthickness=2, highlightbackground=self.warning_color)
            valid = False
        else:
            self.video_label.config(text="1. Select your video file", foreground=self.text_main)
            self.video_entry.config(highlightthickness=1, highlightbackground=self.border_color)

        if not lang_name or lang_name not in self.lang_map:
            self.lang_label.config(text="2. Choose Target Language *", foreground=self.error_color)
            self.lang_search.config(highlightthickness=2, highlightbackground=self.warning_color)
            valid = False
        else:
            self.lang_label.config(text="2. Choose Target Language", foreground=self.text_main)
            self.lang_search.config(highlightthickness=1, highlightbackground=self.border_color)

        if not valid:
            return

        lang_code = self.lang_map[lang_name]
        
        # Switch to Loading Screen
        self.show_loading_screen()
        self.progress_var.set(0)
        self.btn_process.config(state="disabled")
        self.root.update_idletasks()

        def update_progress(value, timestamp=None):
            self.progress_var.set(value)
            if value < 30:
                time_str = f" at {int(timestamp)}s" if timestamp is not None else ""
                self.loading_status_var.set(f"Scanning video frames...{time_str}")
            elif value < 60:
                self.loading_status_var.set("Extracting subtitles via AI...")
            elif value < 90:
                self.loading_status_var.set("Translating text...")
            else:
                self.loading_status_var.set("Merging final video...")
            self.root.update_idletasks()

        def task():
            try:
                print(f"TASK STARTED: Processing {video_file}")
                base_name = os.path.splitext(video_file)[0]
                temp_srt = f"{base_name}_orig.srt"
                translated_srt = f"{base_name}_trans.srt"
                output_video = f"{base_name}_translated.mp4"

                success = extract_subtitles(video_file, temp_srt, update_progress)
                
                if success:
                    translate_srt(temp_srt, translated_srt, lang_code, update_progress)
                    if merge_subtitles(video_file, translated_srt, output_video, update_progress):
                        print("TASK SUCCESS")
                        self.root.after(0, lambda: self.finish_process(True, output_video))
                    else:
                        print("TASK FAILED: Merge phase")
                        self.root.after(0, lambda: self.finish_process(False, "Final merge failed. Check if ffmpeg is installed at C:\\ffmpeg\\bin\\ffmpeg.exe"))
                else:
                    print("TASK FAILED: No subtitles found")
                    self.root.after(0, lambda: self.finish_process(False, "No subtitles found in this video (embedded or burned-in)."))
                
                for f in [temp_srt, translated_srt]:
                    if os.path.exists(f): 
                        try:
                            os.remove(f)
                        except Exception as e:
                            print(f"Cleanup error: {e}")
            except Exception as e:
                import traceback
                err_detail = traceback.format_exc()
                print(f"CRITICAL ERROR:\n{err_detail}")
                self.root.after(0, lambda: self.finish_process(False, f"Critical Error: {str(e)}"))
            finally:
                self.root.after(0, self.reset_ui)

        threading.Thread(target=task, daemon=True).start()

    def reset_ui(self):
        # Restore main screen
        if hasattr(self, 'loading_frame'):
            self.loading_frame.destroy()
        self.main_container.pack(expand=True, fill="both")
        self.btn_process.config(state="normal", bg=self.accent_color)


    def finish_process(self, success, detail):
        if success:
            if messagebox.askyesno("Done!", f"Successfully translated!\n\nSaved as: {os.path.basename(detail)}\n\nWould you like to translate another video?"):
                self.status_var.set("Ready to process another!")
            else:
                self.show_completion_page()
        else:
            messagebox.showerror("Processing Failed", detail)
            self.status_var.set("❌ Error occurred.")

    def show_completion_page(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        finish_container = ttk.Frame(self.root, padding="50")
        finish_container.pack(expand=True, fill="both")
        ttk.Label(finish_container, text="✨ All Done!", font=("Segoe UI Semibold", 24), foreground=self.text_main, background=self.bg_color).pack(pady=(0, 20))
        ttk.Label(finish_container, text="Your video has been processed and translated successfully.\nThank you for using AI Subtitle Translator!", font=("Segoe UI", 12), foreground=self.text_muted, background=self.bg_color, justify="center").pack(pady=(0, 40))
        btn_quit = tk.Button(finish_container, text="Exit Application", command=self.root.quit, bg=self.accent_color, fg="white", font=("Segoe UI Semibold", 12), relief="flat", padx=30, pady=10, cursor="hand2")
        btn_quit.pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = SubtitleTranslatorApp(root)
    root.mainloop()
