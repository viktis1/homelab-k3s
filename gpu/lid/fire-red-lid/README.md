# Intent
This is a wrapper for FireRedLID model that enables language detection. The model is used in create-ringtone to classify the language of audio snippets. This is useful, since the TTS model works best in the same language as the voice it is trying to imitate, it is important to know the original language of the audio clip.

I have made a small wrapper `classify.py`, which downloads the model weights into the disk if the weights are missing. Then, it runs the model and outputs the 

# Origins
This FireRedLID code is part of the FireRedASR paper ([code](https://github.com/FireRedTeam/FireRedASR2S/tree/main)). The following snippet comes from their official repository:

```text
A SOTA Industrial-Grade All-in-One ASR system with ASR, VAD, LID, and Punc modules. FireRedASR2 supports Chinese (Mandarin, 20+ dialects/accents), English, code-switching, and both speech and singing ASR. FireRedVAD supports speech/singing/music in 100+ langs. FireRedLID supports 100+ langs and 20+ zh dialects. FireRedPunc supports zh and en.
```

