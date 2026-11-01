"""Export the browser guide as silent captioned video or offline Spanish narration.

Input/output are artifacts outside the repository. Requires imageio-ffmpeg and
chapters.json from protection-guide-native.cjs. Narration additionally uses SAPI.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import textwrap
import wave


def silent_video(root, chapters):
    """Burn captions into a silent, 720p baseline MP4; no optional text tracks."""
    import imageio_ffmpeg
    source = root / 'steps-tracker-guide.webm'
    frames = imageio_ffmpeg.read_frames(str(source))
    metadata = next(frames)
    frames.close()
    assert metadata['size'] == (1280, 600), 'Record with GPS_GUIDE_CLEAN_VIDEO=1 first'
    start, end = chapters[0]['start'], chapters[-1]['end']
    def clock(value):
        cs = round(max(0, value) * 100)
        return f'{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}'
    def escape(value):
        return value.replace('\\', '').replace('{', '(').replace('}', ')').replace('\n', ' ')
    lines = [
        '[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1280', 'PlayResY: 720', 'WrapStyle: 2',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        'Style: Title,Segoe UI,20,&H0062FFD8,&H0062FFD8,&H00333C12,&H00333C12,-1,0,0,0,100,100,0,0,1,0,0,7,30,30,0,1',
        'Style: Body,Segoe UI,23,&H00FFFFFF,&H00FFFFFF,&H00333C12,&H00333C12,0,0,0,0,100,100,0,0,1,0,0,7,30,30,0,1',
        '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    ]
    for chapter in chapters:
        a,b = clock(chapter['start']-start),clock(chapter['end']-start)
        title = escape(chapter['title']) + '  ·  DEMOSTRACIÓN'
        wrapped = textwrap.wrap(escape(chapter['text']), width=98)
        assert len(wrapped) <= 2, 'Shorten this caption to fit the visible title strip'
        body = r'\N'.join(wrapped)
        lines.extend([f'Dialogue: 0,{a},{b},Title,,0,0,0,,{{\\pos(30,12)}}{title}', f'Dialogue: 0,{a},{b},Body,,0,0,0,,{{\\pos(30,44)}}{body}'])
    (root/'captions-burned.ass').write_text('\n'.join(lines),encoding='utf8')
    filters = f'trim=start={start}:end={end},setpts=PTS-STARTPTS,fps=25,setsar=1,pad=1280:720:0:120:color=0x123c33,drawbox=x=0:y=117:w=1280:h=3:color=0xd8ff62:t=fill,ass=captions-burned.ass,format=yuv420p'
    video = root/'Steps-Tracker-Sin-Audio.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-y','-i',str(source),'-vf',filters,'-an','-sn','-c:v','libx264','-profile:v','baseline','-level:v','3.1','-preset','fast','-crf','19','-maxrate','4M','-bufsize','8M','-bf','0','-g','50','-keyint_min','25','-pix_fmt','yuv420p','-tag:v','avc1','-movflags','+faststart','-metadata','title=Steps Tracker · guía visual sin audio',str(video)],cwd=root,check=True)
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-ss','2','-i',str(video),'-frames:v','1',str(root/'Steps-Tracker-Vista-Previa.png')],check=True)
    # Image-based fallback for viewers that cannot play local MP4 files.
    gif = root/'Steps-Tracker-Vista-Animada.gif'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-y','-i',str(video),'-vf','fps=2,scale=960:540:flags=lanczos,split[p0][p1];[p0]palettegen=max_colors=128:stats_mode=diff[palette];[p1][palette]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle','-loop','0',str(gif)],check=True)
    proof={'video':str(video),'animated_preview':str(gif),'seconds':round(end-start,2),'resolution':[1280,720],'profile':'H.264 constrained baseline 3.1','audio':False,'captions':'burned into every chapter, including dialogs','chapters':len(chapters),'source_start_trimmed':start}
    (root/'silent-render.json').write_text(json.dumps(proof,indent=2),encoding='utf8')
    print(json.dumps(proof))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--silent',action='store_true',help='No narration; burn visible captions into a compatible 720p MP4')
    args = parser.parse_args()
    root = args.directory.resolve()
    chapters = json.loads((root / 'chapters.json').read_text(encoding='utf8'))
    assert chapters and all(c['end'] > c['start'] >= 0 for c in chapters)
    if args.silent:
        silent_video(root,chapters)
        return
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
