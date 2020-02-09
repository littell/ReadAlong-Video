import argparse
import os
import librosa
import math
import numpy as np
import logging
from collections import defaultdict
from util import load_xml, xpath_default, parse_time


class AudioLibrary:
    ''' Holds a collection of waveforms for analysis '''

    def __init__(self):
        self.clips = {}  # filename: (waveform, sample_rate)

    def load_audio(self, audio_path):    
        waveform, sr = librosa.load(audio_path)
        self.clips[audio_path] = (waveform, sr)

    def get_clip(self, audio_path, begin_time, end_time):
        if audio_path not in self.clips:
            self.load_audio(audio_path)
        waveform, sr = self.clips[audio_path]
        waveform = np.abs(waveform)  # only care about absolute amplitude
        if len(waveform.shape) == 2:
            print(f"old shape = {waveform.shape}")
            waveform = np.max(waveform, axis=1)
            print(f"new shape = {waveform.shape}")
        begin_frame = math.floor(begin_time * sr)
        end_frame = math.floor(end_time * sr)
        assert(begin_frame > 0)
        assert(begin_frame < waveform.shape[0])
        assert(end_frame > 0)
        assert(end_frame < waveform.shape[0])
        assert(begin_frame <= end_frame)
        return waveform[begin_frame:end_frame]

class Timespan:
    ''' A collection of timestamps beyond just begin/end, including the 
    ends and beginnings of nearby elements, the beginning and end of an
    amplitude range, etc. '''

    def __init__(self, target_id, clip_src, begin, end):
        self.target_id = target_id
        self.clip_src = clip_src
        self.begin = begin
        self.end = end

    def __repr__(self):
        return f"{self.target_id} {self.clip_src} {self.begin} {self.end}"



def adjust_timing(clip, begin, end):
    audio_library = AudioLibrary()
    for t in get_times(smil):
        audio_path = os.path.join(smil_dir, t.clip_src)
        clip = audio_library.get_clip(audio_path, t.begin, t.end)
        print(t.begin, t.end, clip.shape)

def get_times(input_smil_path):
    audio_library = AudioLibrary()
    results = []
    for par_elem in xpath_default(smil, ".//i:par"):
        begin = np.inf
        end = -np.inf   
        clip_src = ""
        for audio_elem in xpath_default(par_elem, ".//i:audio"):
            clip_src = audio_elem.attrib["src"]
            clip_begin = parse_time(audio_elem.attrib["clipBegin"])
            clip_end = parse_time(audio_elem.attrib["clipEnd"])
            begin = min(clip_begin, begin)
            end = max(clip_end, end)
        for text_elem in xpath_default(par_elem, ".//i:text"):
            src = text_elem.attrib["src"]
            target_id = src.split("#")[-1]
            timespan = Timespan(target_id, clip_src, begin, end)
            results.append(timespan)
    return results

def get_high_amp_range(clip, percentages):
    percentages = sorted(percentages) # just in case
    for percentage in percentages:
        assert(percentage <= 1.0)
    total_amplitude = np.sum(clip)
    print(f"Total amplitude = {total_amplitude}")
    accumulator = 0.0
    results = []
    for i, amp in enumerate(clip):
        accumulator += amp
        if accumulator / total_amplitude >= percentages[0]:
            results.append(i)
            percentages = percentages[1:]
            if not percentages:
                return results
    assert(len(percentages) = 0)
    return results



def main(input_smil_path, output_smil_path):
    smil = load_xml(input_smil_path)
    smil_dir = os.path.dirname(input_smil_path)

    audio_library = AudioLibrary()
    results = []
    for par_elem in xpath_default(smil, ".//i:par"):
        begin = np.inf
        end = -np.inf   
        clip_src = ""
        for audio_elem in xpath_default(par_elem, ".//i:audio"):
            clip_src = audio_elem.attrib["src"]
            clip_begin = parse_time(audio_elem.attrib["clipBegin"])
            clip_end = parse_time(audio_elem.attrib["clipEnd"])
            begin = min(clip_begin, begin)
            end = max(clip_end, end)
        for text_elem in xpath_default(par_elem, ".//i:text"):
            src = text_elem.attrib["src"]
            target_id = src.split("#")[-1]
            timespan = Timespan(target_id, clip_src, begin, end)
            results.append(timespan)
    return results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI to an MP4')
    parser.add_argument('input_tei', type=str, help='Input TEI file')
    parser.add_argument('input_smil', type=str, help='Input SMIL file')
    parser.add_argument('input_audio', type=str, help='Input audio file')
    parser.add_argument('output_smil', type=str, help='Output SMIL file')
    args = parser.parse_args()
    main(args.input_tei, 
        args.input_smil, 
        args.input_audio,
        args.output_tei)
