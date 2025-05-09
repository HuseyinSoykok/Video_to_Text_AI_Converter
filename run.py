import os
import threading
import subprocess
import whisper
from pydub import AudioSegment
from pydub.utils import which
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timedelta
import math

# FFmpeg Path
AudioSegment.converter = r"[Directory where FFmpeg is installed]"  # Directory where FFmpeg is installed EXAMPELE: C:\ffmpeg\ffmpeg.exe


class TranscriberApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video to Text Converter AI Tool")
        self.geometry("900x380")
        self.resizable(False, False)

        # 1) Model selection
        tk.Label(self, text="Model:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.model_var = tk.StringVar(value="medium")
        modeller = ["tiny", "base", "small", "medium", "large"]
        self.model_menu = ttk.Combobox(self, textvariable=self.model_var, values=modeller, state="readonly", width=10)
        self.model_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # 2) Video file selection
        tk.Label(self, text="Video File:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.video_path_var = tk.StringVar()
        tk.Entry(self, textvariable=self.video_path_var, width=45).grid(row=1, column=1, padx=10, pady=10, columnspan=2,
                                                                        sticky="w")
        browse_btn = tk.Button(self, text="Select File", command=self.browse_file, bg="#1E90FF", fg="white",
                               activebackground="#104E8B")
        browse_btn.grid(row=1, column=3, padx=10, pady=10)

        # 3) Convert Button
        self.convert_btn = tk.Button(self, text="Convert", command=self.start_transcription, bg="#28A745", fg="white",
                                     activebackground="#19692C")
        self.convert_btn.grid(row=2, column=1, pady=10)

        # Status Label
        self.status_var = tk.StringVar(value="Please select a video file and model.\n\n")
        tk.Label(self, textvariable=self.status_var, font=("Arial", 12, "italic")).grid(row=3, column=0, columnspan=4,
                                                                                        pady=5)

        # Info Label
        self.info_var = tk.StringVar(value=(
            "tiny: The smallest and fastest model, providing basic transcription.\n\n"
            "base: More accurate than tiny while still relatively fast.\n\n"
            "small: Offers higher accuracy than base, with a bit more processing time.\n\n"
            "medium: Delivers a balanced blend of speed and accuracy; ideal performance for most applications.\n\n"
            "large: Achieves the highest accuracy and most detailed transcription, but with the longest processing time."
        ))
        info_frame = tk.LabelFrame(self, text="Model Guide", padx=10, pady=10)
        info_frame.grid(row=0, column=4, rowspan=4, padx=10, pady=10, sticky="n")
        tk.Label(info_frame, textvariable=self.info_var, justify="left", font=("Arial", 11), wraplength=300).pack()

    def browse_file(self):
        filetypes = [("Video Files", "*.mp4 *.mkv *.avi *.mov"), ("All Files", "*.*")]
        path = filedialog.askopenfilename(title="Select the video", filetypes=filetypes)
        if path:
            self.video_path_var.set(path)

    def start_transcription(self):
        video_path = self.video_path_var.get()
        if not video_path:
            messagebox.showwarning("Warning", "Please select the video file.")
            return

        model_name = self.model_var.get()
        base, _ = os.path.splitext(video_path)
        output_txt = base + "_transcript.txt"

        self.convert_btn.config(state="disabled")
        self.status_var.set("Converting… Please wait…\nThis may take a while.\n\n")


        t = threading.Thread(target=self._transcribe_thread, args=(video_path, output_txt, model_name), daemon=True)
        t.start()

    def _transcribe_thread(self, video_path, output_txt_path, model_name):
        try:
            # 1) CONVERTING VIDEO TO AUDIO
            audio_path = "temp_audio.wav"
            ffmpeg_path = AudioSegment.converter or which("ffmpeg")
            cmd = [ffmpeg_path, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", audio_path]
            subprocess.run(cmd, check=True)

            # 2) Partitioning with Pydub
            audio = AudioSegment.from_wav(audio_path)
            total_ms = len(audio)
            chunk_ms = 30 * 1000  # 30 seconds chunk size
            num_chunks = math.ceil(total_ms / chunk_ms)

            model = whisper.load_model(model_name)
            overall_start = datetime.now()
            times = []  # each chunk processing time

            # Open output file in write mode
            with open(output_txt_path, "w", encoding="utf-8") as out_f:
                for i in range(num_chunks):
                    start_ms = i * chunk_ms
                    end_ms = min((i + 1) * chunk_ms, total_ms)
                    chunk = audio[start_ms:end_ms]
                    chunk_file = f"chunk_{i}.wav"
                    chunk.export(chunk_file, format="wav")

                    # Part processing time
                    chunk_start = datetime.now()
                    result = model.transcribe(chunk_file, fp16=False)
                    chunk_elapsed = (datetime.now() - chunk_start).total_seconds()
                    times.append(chunk_elapsed)

                    # Append text to file
                    out_f.write(result["text"] + "\n")

                    # Delete temporary part file
                    os.remove(chunk_file)

                    # Estimated remaining time
                    avg = sum(times) / len(times)
                    remaining_chunks = num_chunks - i - 1
                    remaining_sec = int(avg * remaining_chunks)
                    mins, secs = divmod(remaining_sec, 60)

                    # UI Update
                    self.after(0, lambda m=mins, s=secs, i=i: self.status_var.set(
                        f"Processing: Chunk {i + 1}/{num_chunks} — Remaining: {m} min {s} sec"
                    ))

                total_elapsed = datetime.now() - overall_start
                tsec = int(total_elapsed.total_seconds())
                tmin, tsec = divmod(tsec, 60)
                self.after(0, lambda: self.status_var.set(f"Completed! Total Running Time: {tmin} min {tsec} sec"))
                self.after(0, lambda: messagebox.showinfo("Finish", f"Text File:\n{output_txt_path}"))

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Warning", f"An Error Occurred:\n{e}"))
            self.after(0, lambda: self.status_var.set("Error occurred."))
        finally:
            #Temporary main file
            if os.path.exists(audio_path):
                os.remove(audio_path)
            self.after(0, lambda: self.convert_btn.config(state="normal"))


if __name__ == "__main__":
    app = TranscriberApp()
    app.mainloop()
