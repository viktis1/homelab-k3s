import argparse
import json
import tempfile
from urllib.request import urlopen
import subprocess

from fireredlid.lid import FireRedLid, FireRedLidConfig

from pathlib import Path
from huggingface_hub import snapshot_download

MODEL_REPO = "FireRedTeam/FireRedLID"

def ensure_model(model_dir):
    model_dir = Path(model_dir)

    required_files = [
        "model.pth.tar",
        "cmvn.ark",
        "dict.txt", 
    ]

    if all((model_dir / file).is_file() for file in required_files):
        return

    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=str(model_dir),
        allow_patterns=required_files,
    )

def download_audio(url, destination):
    with urlopen(url, timeout=60) as response, open(destination, "wb") as file:
        while chunk := response.read(1024 * 1024):
            file.write(chunk)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model-dir", default="/models/FireRedLID")
    args = parser.parse_args()

    ensure_model(args.model_dir)

    model = FireRedLid.from_pretrained(
        args.model_dir,
        FireRedLidConfig(use_gpu=True, use_half=False),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        original_path = Path(temp_dir) / "original.wav"
        audio_path = Path(temp_dir) / "audio.wav"

        download_audio(args.audio, original_path)

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(original_path),
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
        )

        result = model.process(
            batch_uttid=["audio"],
            batch_wav_path=[str(audio_path)],
        )[0]

    if not result["lang"]:
        raise RuntimeError("Language classification failed")

    print(json.dumps(result))


if __name__ == "__main__":
    main()