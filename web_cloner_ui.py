import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import sys
import threading
import queue
from urllib.parse import urlparse
import os

# Import modules từ web_cloner.py
# Vì cả 2 file cùng thư mục nên import trực tiếp được
try:
    from web_cloner import WebsiteCloner
except ImportError:
    messagebox.showerror("Lỗi", "Không tìm thấy file web_cloner.py! Vui lòng đặt file này cùng thư mục với web_cloner.py")
    sys.exit(1)

class PrintRedirector:
    """Redirect stdout/stderr tới queue để UI cập nhật"""
    def __init__(self, text_queue):
        self.text_queue = text_queue

    def write(self, string):
        self.text_queue.put(string)

    def flush(self):
        pass

class WebClonerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Website Cloner Pro GUI")
        self.root.geometry("800x600")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam') # Hoặc 'alt', 'default', 'classic'
        
        # Variables
        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value="cloned_site")
        self.depth_var = tk.IntVar(value=4)  # Mặc định độ sâu là 4 theo yêu cầu
        self.is_running = False
        
        # Queue cho logging
        self.log_queue = queue.Queue()
        
        self._create_widgets()
        self._setup_logging()
        
    def _create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Config Section ---
        config_frame = ttk.LabelFrame(main_frame, text="Cấu hình Clone", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        # URL Input
        ttk.Label(config_frame, text="URL Website:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(config_frame, textvariable=self.url_var, width=60)
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        self.url_entry.focus()
        # Bind events để tự động cập nhật thư mục output
        self.url_entry.bind('<FocusOut>', self._auto_update_output_folder)
        self.url_entry.bind('<KeyRelease>', self._auto_update_output_folder)
        
        # Output Directory
        ttk.Label(config_frame, text="Thư mục Output:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_entry = ttk.Entry(config_frame, textvariable=self.output_var)
        self.output_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(config_frame, text="Chọn...", command=self._browse_folder).grid(row=1, column=2, sticky=tk.W, pady=5)
        
        # Depth
        ttk.Label(config_frame, text="Độ sâu (Depth):").grid(row=2, column=0, sticky=tk.W, pady=5)
        depth_spinbox = ttk.Spinbox(config_frame, from_=1, to=10, textvariable=self.depth_var, width=5)
        depth_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Configure grid weights
        config_frame.columnconfigure(1, weight=1)
        
        # --- Control Section ---
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.start_btn = ttk.Button(control_frame, text="🚀 BẮT ĐẦU CLONE", command=self._start_clone_thread)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ DỪNG", command=self._stop_clone, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # --- Log Section ---
        log_frame = ttk.LabelFrame(main_frame, text="Nhật ký hoạt động (Log)", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Tags coloring
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')
        self.log_text.tag_config('WARNING', foreground='#FF8C00') # DarkOrange

        # Tracking state
        self.user_modified_output = False
        self.selected_root_folder = None # Lưu thư mục cha nếu user chọn qua Browse
        
        # Khi user tự gõ vào ô output => disable auto update
        self.output_entry.bind('<KeyPress>', self._on_output_manual_change)

    def _on_output_manual_change(self, event):
        self.user_modified_output = True
        self.selected_root_folder = None

    def _auto_update_output_folder(self, event=None):
        """Tự động cập nhật tên thư mục output dựa trên domain URL"""
        if self.user_modified_output and not self.selected_root_folder:
            return

        url = self.url_var.get().strip()
        safe_name = "cloned_site" # Default fallback
        
        if url:
             # Thêm http:// tạm nếu thiếu để parse đúng
            if not url.startswith(('http://', 'https://')):
                parse_url = 'http://' + url
            else:
                parse_url = url
                
            try:
                parsed = urlparse(parse_url)
                domain = parsed.netloc
                if domain:
                    safe_name = domain.replace(':', '_')
            except Exception:
                pass
        
        # Logic tạo đường dẫn mới
        new_path = safe_name
        
        # Nếu đã chọn thư mục gốc, ghép với tên domain
        if self.selected_root_folder:
            new_path = os.path.join(self.selected_root_folder, safe_name).replace('\\', '/')
            
        # Cập nhật vào ô output nếu khác giá trị hiện tại
        if self.output_var.get() != new_path:
            self.output_var.set(new_path)

    def _browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            # Lưu thư mục cha và kích hoạt lại chế độ auto update phần domain
            self.selected_root_folder = folder_selected
            self.user_modified_output = False 
            self._auto_update_output_folder()

    def _log(self, message, tag='INFO'):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message, tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def _setup_logging(self):
        """Kiểm tra queue và update log text"""
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            # Simple heuristic for coloring based on content
            tag = 'INFO'
            if "Error" in msg or "Fail" in msg or "✗" in msg:
                tag = 'ERROR'
            elif "Success" in msg or "✓" in msg or "Saved" in msg:
                tag = 'SUCCESS'
            elif "Warning" in msg:
                tag = 'WARNING'
                
            self._log(msg, tag)
            
        # Schedule next check
        self.root.after(100, self._setup_logging)

    def _validate_inputs(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Lỗi", "Vui lòng nhập URL!")
            return False
        if not url.startswith(('http://', 'https://')):
            messagebox.showerror("Lỗi", "URL phải bắt đầu = http:// hoặc https://")
            return False
        return True

    def _start_clone_thread(self):
        if not self._validate_inputs():
            return

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END) # Clear old log
        self.log_text.configure(state='disabled')

        # Auto-detect folder name logic similar to web_cloner.py if empty or default
        url = self.url_var.get().strip()
        output_dir = self.output_var.get().strip()
        
        if not output_dir or output_dir == "cloned_site":
             parsed = urlparse(url)
             domain = parsed.netloc
             safe_domain = domain.replace(':', '_')
             # Nếu user chưa nhập output hoặc để mặc định, ta gợi ý domain name
             # Nhưng ở UI, tốt nhất cứ để user quyết, hoặc ta update biến self.output_var
             # Tuy nhiên logic dưới đây sẽ chạy trong thread, không nên update GUI var trực tiếp mà không cẩn thận
             pass 

        # Create thread
        self.clone_thread = threading.Thread(target=self._run_cloner, args=(url, output_dir, self.depth_var.get()))
        self.clone_thread.daemon = True # Kill thread if main closes
        self.clone_thread.start()

    def _run_cloner(self, url, output, depth):
        # Redirect stdout/stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        sys.stdout = PrintRedirector(self.log_queue)
        sys.stderr = PrintRedirector(self.log_queue)
        
        try:
            print(f"--- BẮT ĐẦU CLONE: {url} ---")
            print(f"Output: {output}")
            print(f"Depth: {depth}\n")
            
            # Nếu output rỗng, tự đặt tên theo domain (logic from user request)
            if not output:
                 parsed = urlparse(url)
                 output = parsed.netloc.replace(':', '_')
                 print(f"Output directory not specified. Auto-set to: {output}")

            cloner = WebsiteCloner(url, output, depth)
            cloner.clone()
            
            print("\n--- HOÀN TẤT ---")
            
            # Show absolute path properly through main thread or just log
            abs_path = os.path.abspath(os.path.join(output, 'index.html'))
            print(f"File chính: {abs_path}")

        except Exception as e:
            print(f"\n[CRITICAL ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Restore stdout
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            # Update UI back in main thread safe way (via after or queue, but simple logic here works mostly safely or via callback)
            self.root.after(0, self._on_clone_finished)

    def _on_clone_finished(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        messagebox.showinfo("Thông báo", "Quá trình Clone đã kết thúc!")

    def _stop_clone(self):
        # Việc dừng thread đang chạy request network là khó khăn
        # Cách đơn giản là đóng app hoặc báo user là "Dừng không được hỗ trợ triệt để"
        # Hoặc đặt 1 flag trong WebsiteCloner nếu có thể modify class.
        # Ở đây ta chỉ cảnh báo.
        if messagebox.askyesno("Xác nhận", "Việc dừng đột ngột có thể làm file bị lỗi. Bạn có muốn thoát ứng dụng không?"):
            self.root.quit()

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        # Fix độ phân giải cao trên Windows
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

    root = tk.Tk()
    app = WebClonerUI(root)
    root.mainloop()
