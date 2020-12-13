import moviepy.editor as mp

audio_clip = mp.AudioFileClip("kajagens.wav")
video_length = audio_clip.duration
result_clip = mp.VideoFileClip("kajagens.mp4").set_duration(video_length)
result_clip.audio = audio_clip
result_clip.write_videofile("kajagens-fixed.mp4", fps=60) #, codec="mpeg4")
