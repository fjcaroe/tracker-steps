"""Make an MP4 with offline Spanish narration and optional subtitles from the browser recording.

Input/output are private artifacts outside the repository. Requires Windows SAPI,
imageio-ffmpeg and chapters.json from protection-guide-native.cjs.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    chapters = json.loads((root / 'chapters.json').read_text(encoding='utf8'))
    assert chapters and all(c['end'] > c['start'] >= 0 for c in chapters)
    environment = {**os.environ, 'STEPS_GUIDE_ARTIFACTS': str(root)}
    script = r"""
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  $spanish = $voice.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1
  if (-not $spanish) { throw 'No hay una voz española instalada' }
  $voice.SelectVoice($spanish.VoiceInfo.Name)
  $voice.Rate = 1
  $rows = Get-Content -LiteralPath (Join-Path $env:STEPS_GUIDE_ARTIFACTS 'chapters.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  $index = 0
  foreach ($row in $rows) {
    $voice.SetOutputToWaveFile((Join-Path $env:STEPS_GUIDE_ARTIFACTS ('voice-{0:D2}.wav' -f $index)))
    $voice.Speak($row.text)
    $voice.SetOutputToNull()
    $index++
  }
} finally { $voice.Dispose() }
"""
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script], env=environment, check=True)
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y', '-i', str(root / 'steps-tracker-guide.webm')]
    filters, labels = [], []
    for index, chapter in enumerate(chapters):
        audio = root / f'voice-{index:02d}.wav'
        with wave.open(str(audio)) as clip:
            duration = clip.getnframes() / clip.getframerate()
        available = chapter['end'] - chapter['start'] - .3
        tempo = max(1.0, duration / available)
        assert tempo <= 2, 'Narration is too long for the recorded chapter'
        command.extend(['-i', str(audio)])
        name = f'a{index}'
        filters.append(f'[{index+1}:a]atempo={tempo:.5f},adelay={round(chapter["start"]*1000)}:all=1[{name}]')
        labels.append(f'[{name}]')
    filters.append(''.join(labels) + f'amix=inputs={len(labels)}:normalize=0,apad,atrim=duration={chapters[-1]["end"]+.5}[voice]')
    def stamp(value):
        ms = round(value * 1000)
        return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
    subtitles = root / 'steps-tracker-guide.srt'
    subtitles.write_text('\n\n'.join(f'{i+1}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["title"]}\n{c["text"]}' for i,c in enumerate(chapters)), encoding='utf8')
    command.extend(['-i', str(subtitles), '-filter_complex', ';'.join(filters), '-map', '0:v:0', '-map', '[voice]', '-map', f'{len(chapters)+1}:s:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=spa', '-metadata', 'title=Steps Tracker · guía de protección y monitoreo', '-metadata', 'comment=Demostración con datos sintéticos. Narración española generada localmente.', '-movflags', '+faststart', '-t', str(chapters[-1]['end']+.5), str(root / 'Steps-Tracker-Guia.mp4')])
    subprocess.run(command, check=True)
    print(json.dumps({'video': str(root / 'Steps-Tracker-Guia.mp4'), 'chapters': len(chapters), 'seconds': round(chapters[-1]['end']+.5), 'spanish_narration': True, 'subtitles': True, 'synthetic_data_only': True}))


if __name__ == '__main__':
    main()
