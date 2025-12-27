import sys, os, numpy as np, sounddevice as sd, soundfile as sf
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QFileDialog,
    QVBoxLayout, QSlider, QGroupBox, QLabel, QHBoxLayout,
    QScrollArea, QTabWidget, QTextEdit
)
from PySide6.QtCore import Qt, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from faster_whisper import WhisperModel

PLAY_ICON = "▶ Play"
PAUSE_ICON = "⏸ Pause"

TRACK_KEYWORDS = ["instrumental", "drums", "vocals", "bass", "others"]


# ================= LYRICS GENERATOR ================= #
class LyricsGenerator:
    def __init__(self, model_size="tiny.en", device="cpu", compute_type="int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def generate_lyrics(self, audio_path):
        try:
            segments, _ = self.model.transcribe(audio_path, beam_size=5)
            return "\n".join(seg.text for seg in segments)
        except Exception as e:
            return f"Error: {e}"


# ================= IMPORT HELPERS ================= #
def load_audio(path):
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, sr


def scan_folder(folder):
    found = {}
    files = os.listdir(folder)

    for key in TRACK_KEYWORDS:
        matches = []
        for f in files:
            name = f.lower()
            if f"(no {key})" in name:
                continue
            if f"({key})" in name:
                matches.insert(0, f)
            elif key in name:
                matches.append(f)

        if matches:
            found[key] = os.path.join(folder, matches[0])

    return found


# ---------------- WAVEFORM ---------------- #
class WaveformWidget(FigureCanvas):
    def __init__(self, click_callback):
        fig = Figure(figsize=(5, 1.4), dpi=100)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)

        self.click_callback = click_callback
        self.wave_len = 1
        self.playhead = None

        self.ax.set_facecolor("#111")
        fig.patch.set_facecolor("#111")
        self.mpl_connect("button_press_event", self.on_click)

    def plot_waveform(self, audio):
        self.ax.clear()
        step = max(1, len(audio) // 2500)
        waveform = audio[::step]
        self.wave_len = len(waveform)

        self.ax.plot(waveform, linewidth=0.6, color="#4fc3f7")
        self.ax.margins(x=0)
        self.ax.set_xlim(0, self.wave_len)

        for s in self.ax.spines.values():
            s.set_visible(False)

        self.playhead = self.ax.axvline(0, color="red", linewidth=1)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.draw_idle()

    def set_playhead_percent(self, percent):
        if self.playhead:
            x = (percent / 100) * self.wave_len
            self.playhead.set_xdata([x, x])
            self.draw_idle()

    def on_click(self, event):
        if event.xdata is None:
            return
        percent = max(0, min(100, (event.xdata / self.wave_len) * 100))
        self.click_callback(percent)


# ================= MAIN APP ================= #
class AudioMixer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini DAW")
        self.resize(820, 700)
        self.setAcceptDrops(True)

        self.tracks = {}
        self.positions = {}
        self.lengths = {}
        self.sliders = {}
        self.waveforms = {}
        self.mute = {}
        self.solo = {}

        self.sample_rate = 44100
        self.stream = None
        self.is_playing = False
        self.vocals_path = None

        self.lyrics_gen = LyricsGenerator()

        self.main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tab_tracks = QWidget()
        self.tab_lyrics = QWidget()
        self.tabs.addTab(self.tab_tracks, "Tracks")
        self.tabs.addTab(self.tab_lyrics, "Lyrics")
        self.main_layout.addWidget(self.tabs)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.tracks_container = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        tracks_layout = QVBoxLayout(self.tab_tracks)
        tracks_layout.addWidget(self.scroll_area)

        seek_row = QHBoxLayout()
        self.time_current = QLabel("00:00")
        self.master_slider = QSlider(Qt.Horizontal)
        self.master_slider.sliderMoved.connect(self.seek_position)
        self.time_remaining_total = QLabel("00:00 / 00:00")
        self.time_remaining_total.setAlignment(Qt.AlignRight)

        seek_row.addWidget(self.time_current)
        seek_row.addWidget(self.master_slider, 1)
        seek_row.addWidget(self.time_remaining_total)
        tracks_layout.addLayout(seek_row)

        btn_row = QHBoxLayout()
        self.btn_folder = QPushButton("Select Folder")
        self.btn_folder.clicked.connect(self.select_folder)

        self.btn_play = QPushButton(PLAY_ICON)
        self.btn_play.clicked.connect(self.play)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.clicked.connect(self.stop)

        self.btn_export = QPushButton("💾 Export")
        self.btn_export.clicked.connect(self.export_mix)

        btn_row.addWidget(self.btn_folder)
        btn_row.addWidget(self.btn_play)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_export)
        tracks_layout.addLayout(btn_row)

        self.lyrics_text = QTextEdit()
        self.lyrics_text.setReadOnly(True)
        self.btn_generate_lyrics = QPushButton("Generate Lyrics")
        self.btn_generate_lyrics.clicked.connect(self.generate_lyrics)

        lyrics_layout = QVBoxLayout(self.tab_lyrics)
        lyrics_layout.addWidget(self.lyrics_text)
        lyrics_layout.addWidget(self.btn_generate_lyrics)

        self.ui_timer = QTimer()
        self.ui_timer.setInterval(20)
        self.ui_timer.timeout.connect(self.update_ui)

    # -------- DRAG & DROP -------- #
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isdir(path):
                self.load_folder(path)
            else:
                self.load_folder(os.path.dirname(path))

    # -------- IMPORT -------- #
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Folder")
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder):
        self.clear_tracks_ui()
        self.tracks.clear()
        self.positions.clear()
        self.lengths.clear()
        self.waveforms.clear()
        self.mute.clear()
        self.solo.clear()

        found = scan_folder(folder)

        for name, path in found.items():
            data, sr = load_audio(path)
            self.tracks[name] = data
            self.positions[name] = 0
            self.lengths[name] = len(data)
            self.sample_rate = sr

            self.mute[name] = False   # ✅ FIX
            self.solo[name] = False   # ✅ FIX

            if name == "vocals":
                self.vocals_path = path

            self.create_track_ui(name)
            self.waveforms[name].plot_waveform(data)

    def clear_tracks_ui(self):
        while self.tracks_container.count():
            item = self.tracks_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def create_track_ui(self, name):
        box = QGroupBox(name.capitalize())
        hbox = QHBoxLayout()

        left = QVBoxLayout()
        btn_mute = QPushButton("M")
        btn_mute.setCheckable(True)
        btn_mute.clicked.connect(lambda _, n=name: self.toggle_mute(n))

        btn_solo = QPushButton("S")
        btn_solo.setCheckable(True)
        btn_solo.clicked.connect(lambda _, n=name: self.toggle_solo(n))

        slider = QSlider(Qt.Vertical)
        slider.setRange(0, 100)
        slider.setValue(80)
        self.sliders[name] = slider

        left.addWidget(btn_mute)
        left.addWidget(btn_solo)
        left.addWidget(slider)

        waveform = WaveformWidget(self.seek_position)
        self.waveforms[name] = waveform

        hbox.addLayout(left)
        hbox.addWidget(waveform, 1)
        box.setLayout(hbox)
        self.tracks_container.addWidget(box)

    # -------- AUDIO -------- #
    def audio_callback(self, outdata, frames, time, status):
        mix = np.zeros(frames, dtype=np.float32)
        solo_active = any(self.solo.values())

        for name, data in self.tracks.items():
            if self.mute[name]:
                continue
            if solo_active and not self.solo[name]:
                continue

            pos = self.positions[name]
            chunk = data[pos:pos + frames]
            if len(chunk) < frames:
                chunk = np.pad(chunk, (0, frames - len(chunk)))

            mix += chunk * (self.sliders[name].value() / 100)
            self.positions[name] += frames

        outdata[:] = mix.reshape(-1, 1)

    def play(self):
        if not self.tracks:
            return

        if self.stream and self.is_playing:
            self.stream.stop()
            self.is_playing = False
            self.ui_timer.stop()
            self.btn_play.setText(PLAY_ICON)
            return

        if not self.stream:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=512,
                callback=self.audio_callback
            )

        self.stream.start()
        self.is_playing = True
        self.ui_timer.start()
        self.btn_play.setText(PAUSE_ICON)

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_playing = False
        self.ui_timer.stop()
        self.btn_play.setText(PLAY_ICON)

    # -------- UI -------- #
    def seek_position(self, percent):
        for name in self.tracks:
            self.positions[name] = int((percent / 100) * self.lengths[name])

    def toggle_mute(self, name):
        self.mute[name] = not self.mute[name]

    def toggle_solo(self, name):
        self.solo[name] = not self.solo[name]

    def update_ui(self):
        if not self.tracks:
            return
        first = next(iter(self.tracks))
        pos = self.positions[first]
        length = self.lengths[first]
        percent = (pos / length) * 100

        self.master_slider.blockSignals(True)
        self.master_slider.setValue(int(percent))
        self.master_slider.blockSignals(False)

        for name in self.tracks:
            self.waveforms[name].set_playhead_percent(percent)

    # -------- EXPORT / LYRICS -------- #
    def export_mix(self):
        max_len = max(self.lengths.values())
        mix = np.zeros(max_len, dtype=np.float32)
        solo_active = any(self.solo.values())

        for name, data in self.tracks.items():
            if self.mute[name]:
                continue
            if solo_active and not self.solo[name]:
                continue

            padded = np.pad(data, (0, max_len - len(data)))
            mix += padded * (self.sliders[name].value() / 100)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Mix", "mix.wav", "WAV Files (*.wav)"
        )
        if path:
            sf.write(path, mix, self.sample_rate)

    def generate_lyrics(self):
        if not self.vocals_path:
            self.lyrics_text.setText("No vocals track found")
            return
        self.lyrics_text.setText("Generating lyrics...")
        QApplication.processEvents()
        self.lyrics_text.setText(self.lyrics_gen.generate_lyrics(self.vocals_path))


# ---------------- RUN ---------------- #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AudioMixer()
    win.show()
    sys.exit(app.exec())
