from collections import defaultdict 

import os
import argparse
from lxml import etree as et 

import gc

import moviepy.editor as mp
from svglib.svglib import svg2rlg, find_font, _registered_fonts 
from reportlab.graphics import renderPM
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor

from util import save_xml, load_json
from svg_snapshot import SnapshotSVG

FRAMES_PER_SECOND = 24
SCREEN_WIDTH_480P = 720
SCREEN_WIDTH_480P = 480
SCREEN_WIDTH_HD = 1920
SCREEN_HEIGHT_HD = 1080
FRAMES_PER_CHUNK = 200

registerFont(TTFont('NotoSans','./fonts/Noto_Sans_400.ttf'))
_registered_fonts['NotoSans'] = True


NUM_MOVIE_CHUNKS = 0
def write_movie_chunk(clips, background_filename, fps):
    global NUM_MOVIE_CHUNKS
    tempfile_path = "temp/temp" + str(NUM_MOVIE_CHUNKS) + ".mp4"
    NUM_MOVIE_CHUNKS += 1
    result_clip = mp.concatenate_videoclips(clips, method="compose")
    if background_filename:
        bgClip = mp.ImageClip(background_filename).set_duration(result_clip.duration)
        result_clip = mp.CompositeVideoClip([bgClip, result_clip])
    result_clip.write_videofile(tempfile_path, fps=fps)
    return tempfile_path

def svg_to_mp4(svg_tree, 
                audio_filename,
                config_filename, 
                output_filename,
                fps=FRAMES_PER_SECOND):

    clips = []

    if audio_filename:
        audio_clip = mp.AudioFileClip(audio_filename)
        video_length = audio_clip.duration
    else:
        video_length = 4.0

    frame_duration = 1.0 / fps
    current_length = 0

    snapshot_svg = SnapshotSVG(svg_tree)

    if config_filename:
        config = load_json(config_filename)
        background_filename = config.get("bg-image", "")
    else:
        background_filename = ""

    movie_chunk_paths = []

    while True:

        if len(clips) >= FRAMES_PER_CHUNK:
            movie_chunk_path = write_movie_chunk(clips, background_filename, fps)
            print(movie_chunk_path)
            movie_chunk_paths.append(movie_chunk_path)
            clips = []        
            #gc.collect()
            #print("collected")

        frozen_svg = snapshot_svg[current_length]
        tempfile_basename = "temp/temp"
        save_xml(tempfile_basename + ".svg", frozen_svg)
        drawing = svg2rlg(tempfile_basename + ".svg")
        renderPM.drawToFile(drawing, tempfile_basename + ".tiff", fmt="TIFF", bg=0x140A00, configPIL={'transparent': toColor('rgb(20,10,0)')})

        #imageClip = mp.ImageClip(tempfile_basename + ".png").set_duration(frame_duration)
        #maskClip = mp.ImageClip(tempfile_basename + ".png", ismask=True)
        #imageClip.set_mask(maskClip)
        #renderPM.drawToFile(drawing, tempfile_basename + ".gif", fmt="GIF", bg=0xffff00, configPIL={'transparent': 0xffff00})
        
        #p = renderPM.drawToPIL(drawing, bg=0xffffff, configPIL={'transparent': 0xffffff})
        #p.save(tempfile_basename + ".png")
        imageClip = mp.ImageClip(tempfile_basename + ".tiff", transparent=True).set_duration(frame_duration)
        
        clips.append(imageClip)
        current_length += frame_duration
        
        if current_length >= video_length:
            break

    if clips:
        movie_chunk_path = write_movie_chunk(clips, background_filename, fps)
        movie_chunk_paths.append(movie_chunk_path)
        clips = []   

    movie_chunks = []
    for movie_chunk_path in movie_chunk_paths:
        chunkClip = mp.VideoFileClip(movie_chunk_path)
        movie_chunks.append(chunkClip)

    result_clip = mp.concatenate_videoclips(movie_chunks, method="compose").set_duration(video_length)
    #bgClip = mp.ImageClip(background_filename).set_duration(video_length)
    #result_clip = mp.CompositeVideoClip([bgClip, result_clip])
    if audio_filename:
        result_clip.audio = audio_clip
    result_clip.write_videofile(output_filename, fps=fps)


def main(input_filename, audio_filename, config_filename, output_filename):

    svg_tree = et.parse(input_filename)
    svg_to_mp4(svg_tree, audio_filename, config_filename, output_filename, 24)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render an SVG animation to MP4 movie')
    parser.add_argument('input', type=str, help='Input .svg file')
    parser.add_argument('output', type=str, help='Output .mp4 file')
    parser.add_argument('audio', type=str, nargs="?", default="", help='Input .mp3 file')
    parser.add_argument('config', type=str, nargs="?", default="", help="Config JSON file")
    args = parser.parse_args()
    main(args.input, args.audio, args.config, args.output)
