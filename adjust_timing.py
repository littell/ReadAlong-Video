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
            waveform = np.max(waveform, axis=1)
        begin_frame = math.floor(begin_time * sr)
        end_frame = math.floor(end_time * sr)
        assert(begin_frame > 0)
        assert(begin_frame < waveform.shape[0])
        assert(end_frame > 0)
        assert(end_frame < waveform.shape[0])
        assert(begin_frame <= end_frame)
        return waveform[begin_frame:end_frame], sr


def get_timestamps_by_percentage(waveform, percentages):
    percentages = sorted(percentages) # just in case
    for percentage in percentages:
        assert(percentage <= 1.0)
    total_amplitude = np.sum(waveform)
    accumulator = 0.0
    results = []
    for frame_idx, amp in enumerate(waveform):
        accumulator += amp
        if accumulator / total_amplitude >= percentages[0]:
            results.append(frame_idx)
            percentages = percentages[1:]
            if not percentages:
                return results

    for percentage in percentages:  # any remaining percentages (e.g. 1.0)
        results.append(waveform.shape[0] - 1)
    return results

def adjust_timing(smil, smil_dir, begin_percent=0.2, end_percent=0.6):
    audio_library = AudioLibrary()
    for par_elem in xpath_default(smil, ".//i:par"):
        clip_src = ""
        for audio_elem in xpath_default(par_elem, ".//i:audio"):
            clip_src = audio_elem.attrib["src"]
            begin = parse_time(audio_elem.attrib["clipBegin"])
            end = parse_time(audio_elem.attrib["clipEnd"])
        
            # get the waveform of the clip
            audio_path = os.path.join(smil_dir, clip_src)
            waveform, sr = audio_library.get_clip(audio_path, begin, end)
        
            # get new begin and end timestamps as percentages of amplitude
            begin_frame_offset, end_frame_offset = get_timestamps_by_percentage(waveform, 
                                [begin_percent, end_percent])
            new_begin = begin + begin_frame_offset / sr
            new_end = begin + end_frame_offset / sr 

            # change the attributes in the SMIL element
            audio_elem.attrib["clipBegin"] = "{:.2f}".format(new_begin)
            audio_elem.attrib["clipEnd"] =  "{:.2f}".format(new_end)


    return smil

def main(input_smil_path, output_smil_path):
    smil = load_xml(input_smil_path)
    smil_dir = os.path.dirname(input_smil_path)
    new_smil = adjust_timing(smil, smil_dir, 0.2, 0.6)
    save_xml(output_smil_path, new_smil)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Adjust SMIL timings according to percentages of absolute amplitude')
    parser.add_argument('input_smil', type=str, help='Input SMIL file')
    parser.add_argument('output_smil', type=str, help='Output SMIL file')
    args = parser.parse_args()
    main(args.input_smil, 
        args.output_smil)
