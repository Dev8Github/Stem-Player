# Stem-Player
Stem Player is a lightweight desktop app for managing and mixing pre-separated audio stems like vocals, drums, bass, and instruments. It automatically detects WAV stem files by filename keywords, allows volume control, mute/solo, waveform preview, lyric generation, and exports a final mixed track.




🎛️ Stem Player

Stem Player is a lightweight desktop application for managing, mixing, and re-merging pre-separated audio stems such as vocals, drums, bass, instrumental, and others.

Inspired by tools like Ultimate Vocal Remover, this project does not perform stem separation or audio generation. Instead, it focuses on the post-separation workflow — providing an easy way to load existing stems, control their levels, preview them in real time, generate lyrics, and export a final mix.





✨ Features

📂 Automatic Stem Detection (Filename-Based)
Select a folder and Stem Player automatically detects stem files based on keywords in filenames
(e.g. vocals, drums, bass, instrumental, others).

🎵 WAV-Only Support (Current)
Works exclusively with .wav audio files.
Stereo files are automatically converted to mono for playback and mixing.

🎚️ Per-Stem Volume Control
Independently adjust gain for each stem.

🔇 Mute & Solo
Instantly mute or isolate individual stems.

▶️ Real-Time Playback & Seeking
Play, pause, stop, and seek across all stems on a shared timeline.

📊 Waveform Visualization
Visual waveforms with synchronized playhead and click-to-seek support.

🔄 Re-Merge & Export
Combine stems using current mix settings and export the result as a WAV file.

📝 Lyrics Generation (English Only, WIP)
Generate lyrics from the vocals stem using Whisper speech-to-text.




🧠 Intended Workflow

Generate stems using an external tool (e.g. Ultimate Vocal Remover)

Open Stem Player

Select the folder containing WAV stem files

Adjust volume, mute/solo stems

Export the final mix

(Optional) Generate lyrics from the vocals track





🛠️ Tech Stack

Python

PySide6 (Qt)

NumPy

sounddevice

soundfile

Matplotlib

faster-whisper





🚧 Project Status

Active development — focused on simplicity, clarity, and usability.
Lyrics generation and format support are still evolving.
