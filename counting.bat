CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count1.xml ..\ReadAlong-Samples\ctp\counting\aligned\count1.smil ..\ReadAlong-Samples\ctp\counting\aligned\count1.wav ..\ReadAlong-Samples\ctp\counting\configs\config1.json count1.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count2.xml ..\ReadAlong-Samples\ctp\counting\aligned\count2.smil ..\ReadAlong-Samples\ctp\counting\aligned\count2.wav ..\ReadAlong-Samples\ctp\counting\configs\config2.json count2.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count3.xml ..\ReadAlong-Samples\ctp\counting\aligned\count3.smil ..\ReadAlong-Samples\ctp\counting\aligned\count3.wav ..\ReadAlong-Samples\ctp\counting\configs\config3.json count3.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count4.xml ..\ReadAlong-Samples\ctp\counting\aligned\count4.smil ..\ReadAlong-Samples\ctp\counting\aligned\count4.wav ..\ReadAlong-Samples\ctp\counting\configs\config4json count4.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count5.xml ..\ReadAlong-Samples\ctp\counting\aligned\count5.smil ..\ReadAlong-Samples\ctp\counting\aligned\count5.wav ..\ReadAlong-Samples\ctp\counting\configs\config5.json count5.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count6.xml ..\ReadAlong-Samples\ctp\counting\aligned\count6.smil ..\ReadAlong-Samples\ctp\counting\aligned\count6.wav ..\ReadAlong-Samples\ctp\counting\configs\config6.json count6.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count7.xml ..\ReadAlong-Samples\ctp\counting\aligned\count7.smil ..\ReadAlong-Samples\ctp\counting\aligned\count7.wav ..\ReadAlong-Samples\ctp\counting\configs\config7.json count7.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count8.xml ..\ReadAlong-Samples\ctp\counting\aligned\count8.smil ..\ReadAlong-Samples\ctp\counting\aligned\count8.wav ..\ReadAlong-Samples\ctp\counting\configs\config8.json count8.mp4

CALL py -3 -m tei_to_mp4 ..\ReadAlong-Samples\ctp\counting\aligned\count9.xml ..\ReadAlong-Samples\ctp\counting\aligned\count9.smil ..\ReadAlong-Samples\ctp\counting\aligned\count9.wav ..\ReadAlong-Samples\ctp\counting\configs\config9.json count9.mp4

CALL py -3 -m compose_clips count1.mp4 count2.mp4 count3.mp4 count4.mp4 count5.mp4 count6.mp4 count7.mp4 count8.mp4 count9.mp4 --o chatino_counting.mp4
