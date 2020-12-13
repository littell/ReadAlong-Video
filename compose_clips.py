
import argparse
import moviepy.editor as mp



def compose_clips(clip_paths, output_path, fade_duration=0.5):
    clips = []
    current_time = 0
    max_fps = 1

    for clip_path in clip_paths:
        clip = mp.VideoFileClip(clip_path) #.crossfadeout(fade_duration)
        if current_time != 0:
            current_time -= fade_duration
            clip = clip.set_start(current_time).crossfadein(fade_duration)
        current_time += clip.duration
        max_fps = max(max_fps, clip.fps)
        clips.append(clip)

    video = mp.CompositeVideoClip(clips)
    video.write_videofile(output_path, audio_codec='aac', fps=max_fps)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Combine movie clips with 1s crossfade')
    parser.add_argument('input_paths', metavar='N', type=str, nargs='+',
                    help='The clips to combine')
    parser.add_argument("--output_path", type=str, help="The output clip")
    parser.add_argument("--fade_duration", type=float, default=0.5, help="The duration of the crossfade, in seconds [default=0.5]")
    args = parser.parse_args()
    compose_clips(args.input_paths, args.output_path, args.fade_duration)