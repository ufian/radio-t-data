#!/usr/bin/env python3
"""
Voice batch processing script for speaker embedding extraction.

Downloads podcast audio, extracts segments, computes speaker embeddings
using multiple models (pyannote, ecapa, titanet).

Usage:
    python scripts/process_voice_batch.py --batch 0900-0999
    python scripts/process_voice_batch.py --batch 0300-0399 --models pyannote,ecapa
    python scripts/process_voice_batch.py --batch 0300-0399 --skip-download
"""

import argparse
import json
import logging
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CDN_URL_TEMPLATE = "http://cdn.radio-t.com/rt_podcast{episode}.mp3"
DEFAULT_MODELS = ["pyannote", "ecapa", "titanet"]
EMBEDDING_DIMS = {
    "pyannote": 512,
    "ecapa": 192,
    "titanet": 192,
}


class ModelLoader:
    """Lazy loader for embedding models."""

    def __init__(self, models_to_load: list[str]):
        self.models_to_load = models_to_load
        self._models = {}
        self._loaded = False
        self._np = None

    def load(self):
        """Load all requested models."""
        if self._loaded:
            return

        # Import numpy here for lazy loading
        import numpy as np
        self._np = np

        logger.info("Loading embedding models...")
        failed_models = []

        if "pyannote" in self.models_to_load:
            try:
                self._load_pyannote()
            except Exception as e:
                logger.warning(f"Failed to load pyannote, skipping: {e}")
                failed_models.append("pyannote")

        if "ecapa" in self.models_to_load:
            try:
                self._load_ecapa()
            except Exception as e:
                logger.warning(f"Failed to load ecapa, skipping: {e}")
                failed_models.append("ecapa")

        if "titanet" in self.models_to_load:
            try:
                self._load_titanet()
            except Exception as e:
                logger.warning(f"Failed to load titanet, skipping: {e}")
                failed_models.append("titanet")

        # Remove failed models from the list
        for model in failed_models:
            self.models_to_load.remove(model)

        if not self.models_to_load:
            raise RuntimeError("No models could be loaded")

        self._loaded = True
        logger.info(f"Models loaded: {', '.join(self.models_to_load)}")

    def _load_pyannote(self):
        """Load pyannote embedding model."""
        logger.info("Loading pyannote/embedding model...")
        try:
            import torch

            # Workaround for PyTorch 2.6+ weights_only=True default
            # Models from HuggingFace are trusted
            # Must patch torch.load before importing pyannote
            _original_torch_load = torch.load
            def _patched_torch_load(*args, **kwargs):
                kwargs['weights_only'] = False
                return _original_torch_load(*args, **kwargs)
            torch.load = _patched_torch_load

            from pyannote.audio import Model
            from pyannote.audio import Inference

            model = Model.from_pretrained("pyannote/embedding")
            inference = Inference(model, window="whole")
            self._models["pyannote"] = inference

            # Restore original
            torch.load = _original_torch_load
            logger.info("pyannote model loaded")
        except Exception as e:
            logger.error(f"Failed to load pyannote model: {e}")
            raise

    def _load_ecapa(self):
        """Load SpeechBrain ECAPA-TDNN speaker embedding model."""
        logger.info("Loading speechbrain/spkrec-ecapa-voxceleb model...")
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir="pretrained_models/spkrec-ecapa-voxceleb",
                run_opts={"device": device}
            )

            self._models["ecapa"] = {
                "model": model,
                "device": device
            }
            logger.info(f"ECAPA-TDNN model loaded on {device}")
        except Exception as e:
            logger.error(f"Failed to load ECAPA-TDNN model: {e}")
            raise

    def _load_titanet(self):
        """Load NVIDIA TitaNet model."""
        logger.info("Loading nvidia/speakerverification_en_titanet_large model...")
        try:
            import nemo.collections.asr as nemo_asr

            model = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained(
                "nvidia/speakerverification_en_titanet_large"
            )
            model.eval()
            self._models["titanet"] = model
            logger.info("TitaNet model loaded")
        except Exception as e:
            logger.error(f"Failed to load TitaNet model: {e}")
            raise

    def get_model(self, name: str):
        """Get a loaded model by name."""
        if not self._loaded:
            self.load()
        return self._models.get(name)

    def compute_embedding(self, model_name: str, audio_path: str):
        """Compute embedding for audio file using specified model."""
        model = self.get_model(model_name)
        if model is None:
            raise ValueError(f"Model {model_name} not loaded")

        if model_name == "pyannote":
            return self._compute_pyannote(model, audio_path)
        elif model_name == "ecapa":
            return self._compute_ecapa(model, audio_path)
        elif model_name == "titanet":
            return self._compute_titanet(model, audio_path)
        else:
            raise ValueError(f"Unknown model: {model_name}")

    def _compute_pyannote(self, inference, audio_path: str):
        """Compute embedding using pyannote."""
        import torchaudio

        # Load audio with torchaudio (workaround for torchcodec issues)
        waveform, sample_rate = torchaudio.load(audio_path)

        # Pass as dict with waveform and sample_rate
        file = {"waveform": waveform, "sample_rate": sample_rate}
        embedding = inference(file)
        return self._np.array(embedding).flatten()

    def _compute_ecapa(self, model_dict: dict, audio_path: str):
        """Compute embedding using SpeechBrain ECAPA-TDNN."""
        import torchaudio

        model = model_dict["model"]

        # Load audio with torchaudio
        waveform, sample_rate = torchaudio.load(audio_path)

        # Resample to 16kHz if needed
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)

        # Ensure mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Compute embedding
        embedding = model.encode_batch(waveform)

        return embedding.squeeze().cpu().numpy()

    def _compute_titanet(self, model, audio_path: str):
        """Compute embedding using TitaNet."""
        embedding = model.get_embedding(audio_path)
        return embedding.cpu().numpy().flatten()

    def save_embedding(self, embedding, path: Path):
        """Save embedding to numpy file."""
        self._np.save(path, embedding)


def load_batch(batch_name: str, base_dir: Path) -> dict:
    """Load batch YAML file."""
    import yaml

    batch_path = base_dir / "unified_batches" / f"{batch_name}.yaml"

    if not batch_path.exists():
        raise FileNotFoundError(f"Batch file not found: {batch_path}")

    with open(batch_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_episode(episode: int, cache_dir: Path) -> Path:
    """Download episode audio to cache directory."""
    import requests
    from tqdm import tqdm

    cache_dir.mkdir(parents=True, exist_ok=True)
    audio_path = cache_dir / f"rt_podcast{episode}.mp3"

    if audio_path.exists():
        logger.info(f"Episode {episode}: using cached audio")
        return audio_path

    url = CDN_URL_TEMPLATE.format(episode=episode)
    logger.info(f"Downloading episode {episode} from {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    with open(audio_path, 'wb') as f:
        with tqdm(total=total_size, unit='iB', unit_scale=True, desc=f"Episode {episode}") as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                size = f.write(chunk)
                pbar.update(size)

    logger.info(f"Episode {episode}: downloaded to {audio_path}")
    return audio_path


def extract_segment(audio_path: Path, stime: float, duration: float) -> Path:
    """Extract audio segment using ffmpeg, returns path to temporary WAV file."""
    # Create temporary file
    temp_path = Path(tempfile.gettempdir()) / f"{uuid.uuid4()}.wav"

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", str(audio_path),
        "-ss", str(stime),
        "-t", str(duration),
        "-ar", "16000",  # 16kHz sample rate
        "-ac", "1",  # Mono
        "-loglevel", "error",
        str(temp_path)
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg error: {e.stderr.decode()}")
        raise

    return temp_path


def get_segment_filename(episode: int, speaker: str, stime: float) -> str:
    """Generate filename for segment embedding."""
    # Sanitize speaker name (replace dots and special chars)
    safe_speaker = speaker.replace(".", "_")
    return f"{episode}_{safe_speaker}_{stime}.npy"


def load_status(results_dir: Path) -> dict:
    """Load status file or create empty status."""
    status_path = results_dir / "status.json"

    if status_path.exists():
        with open(status_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "started_at": datetime.now().isoformat(),
        "episodes": {}
    }


def save_status(results_dir: Path, status: dict):
    """Save status file."""
    results_dir.mkdir(parents=True, exist_ok=True)
    status_path = results_dir / "status.json"

    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def save_metadata(results_dir: Path, batch_name: str, models: list[str], segments_info: list[dict]):
    """Save metadata file with segment information."""
    metadata = {
        "batch": batch_name,
        "models": models,
        "created_at": datetime.now().isoformat(),
        "segments": segments_info
    }

    metadata_path = results_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def process_batch(
    batch_name: str,
    base_dir: Path,
    cache_dir: Path,
    results_dir: Path,
    models: list[str],
    skip_download: bool = False,
    skip_embeddings: bool = False,
    episode_filter: int = None
):
    """Process a single batch."""
    from tqdm import tqdm

    logger.info(f"Processing batch: {batch_name}")

    # Load batch data
    batch_data = load_batch(batch_name, base_dir)

    # Filter to single episode if requested
    if episode_filter is not None:
        episode_key = str(episode_filter)
        if episode_key not in batch_data.get("episodes", {}) and episode_filter not in batch_data.get("episodes", {}):
            raise ValueError(f"Episode {episode_filter} not found in batch {batch_name}")

        # Handle both int and str keys
        if episode_key in batch_data["episodes"]:
            filtered_episode = batch_data["episodes"][episode_key]
        else:
            filtered_episode = batch_data["episodes"][episode_filter]

        batch_data["episodes"] = {episode_filter: filtered_episode}
        batch_data["episodes_count"] = 1
        batch_data["total_segments"] = filtered_episode["segment_count"]
        logger.info(f"Filtered to episode {episode_filter}: {filtered_episode['segment_count']} segments")
    else:
        logger.info(f"Loaded batch with {batch_data['episodes_count']} episodes, {batch_data['total_segments']} segments")

    # Setup results directory
    batch_results_dir = results_dir / batch_name
    batch_results_dir.mkdir(parents=True, exist_ok=True)

    # Load existing status
    status = load_status(batch_results_dir)
    status["batch"] = batch_name

    # Load models if needed
    model_loader = None
    if not skip_embeddings:
        model_loader = ModelLoader(models.copy())
        model_loader.load()
        # Update models list to only include successfully loaded models
        models = model_loader.models_to_load

    # Create embedding directories
    for model_name in models:
        (batch_results_dir / "embeddings" / model_name).mkdir(parents=True, exist_ok=True)

    # Track all segments for metadata
    all_segments_info = []

    # Process each episode
    episodes = batch_data.get("episodes", {})

    for episode, episode_data in tqdm(episodes.items(), desc="Episodes"):
        episode = int(episode)
        episode_str = str(episode)

        # Check if already completed
        if status["episodes"].get(episode_str, {}).get("status") == "completed":
            logger.info(f"Episode {episode}: already completed, skipping")

            # Still need to add to metadata
            for segment in episode_data["segments"]:
                segment_filename = get_segment_filename(episode, segment["speaker"], segment["stime"])
                segment_info = {
                    "episode": episode,
                    "speaker": segment["speaker"],
                    "stime": segment["stime"],
                    "etime": segment["etime"],
                    "duration": segment["duration"],
                    "types": segment.get("types", []),
                    "task_types": segment.get("task_types", []),
                    "embeddings": {
                        model: f"embeddings/{model}/{segment_filename}"
                        for model in models
                    }
                }
                if "comparison_group" in segment:
                    segment_info["comparison_group"] = segment["comparison_group"]
                all_segments_info.append(segment_info)
            continue

        # Initialize episode status
        status["episodes"][episode_str] = {
            "status": "in_progress",
            "segments_processed": 0,
            "segments_total": episode_data["segment_count"]
        }
        save_status(batch_results_dir, status)

        # Download audio
        audio_path = None
        if not skip_download:
            try:
                audio_path = download_episode(episode, cache_dir)
            except Exception as e:
                logger.error(f"Episode {episode}: failed to download - {e}")
                status["episodes"][episode_str]["status"] = "error"
                status["episodes"][episode_str]["error"] = str(e)
                save_status(batch_results_dir, status)
                continue
        else:
            audio_path = cache_dir / f"rt_podcast{episode}.mp3"
            if not audio_path.exists():
                logger.error(f"Episode {episode}: audio not in cache and skip-download enabled")
                status["episodes"][episode_str]["status"] = "error"
                status["episodes"][episode_str]["error"] = "Audio not in cache"
                save_status(batch_results_dir, status)
                continue

        # Process each segment
        segments = episode_data.get("segments", [])

        for segment in tqdm(segments, desc=f"Ep{episode} segments", leave=False):
            speaker = segment["speaker"]
            stime = segment["stime"]
            duration = segment["duration"]

            segment_filename = get_segment_filename(episode, speaker, stime)

            # Check if embeddings already exist
            embeddings_exist = all(
                (batch_results_dir / "embeddings" / model / segment_filename).exists()
                for model in models
            )

            if embeddings_exist:
                logger.debug(f"Segment {segment_filename}: embeddings exist, skipping")
                status["episodes"][episode_str]["segments_processed"] += 1
            else:
                # Extract segment
                temp_wav = None
                try:
                    temp_wav = extract_segment(audio_path, stime, duration)

                    if not skip_embeddings:
                        # Compute and save embeddings
                        for model_name in models:
                            embedding_path = batch_results_dir / "embeddings" / model_name / segment_filename

                            if not embedding_path.exists():
                                embedding = model_loader.compute_embedding(model_name, str(temp_wav))
                                model_loader.save_embedding(embedding, embedding_path)
                                logger.debug(f"Saved {model_name} embedding: {segment_filename}")

                    status["episodes"][episode_str]["segments_processed"] += 1

                except Exception as e:
                    logger.error(f"Error processing segment {episode}/{speaker}/{stime}: {e}")
                    continue
                finally:
                    # Clean up temporary file
                    if temp_wav and temp_wav.exists():
                        temp_wav.unlink()

            # Add to metadata
            segment_info = {
                "episode": episode,
                "speaker": speaker,
                "stime": stime,
                "etime": segment["etime"],
                "duration": duration,
                "types": segment.get("types", []),
                "task_types": segment.get("task_types", []),
                "embeddings": {
                    model: f"embeddings/{model}/{segment_filename}"
                    for model in models
                }
            }
            if "comparison_group" in segment:
                segment_info["comparison_group"] = segment["comparison_group"]
            all_segments_info.append(segment_info)

        # Mark episode as completed
        status["episodes"][episode_str]["status"] = "completed"
        status["episodes"][episode_str]["completed_at"] = datetime.now().isoformat()
        save_status(batch_results_dir, status)
        logger.info(f"Episode {episode}: completed")

    # Save final metadata
    save_metadata(batch_results_dir, batch_name, models, all_segments_info)

    logger.info(f"Batch {batch_name} processing complete")
    logger.info(f"Results saved to: {batch_results_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Process voice matching batches for speaker embedding extraction"
    )
    parser.add_argument(
        "--batch",
        required=False,
        help="Batch name (e.g., 0300-0399)"
    )
    parser.add_argument(
        "--episode",
        type=int,
        help="Process only this episode number (requires --batch)"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("./cache"),
        help="Directory for caching downloaded MP3 files (default: ./cache)"
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("./cleaning/tasks/voice_matching/results"),
        help="Directory for saving results (default: ./cleaning/tasks/voice_matching/results)"
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help=f"Comma-separated list of models to use (default: {','.join(DEFAULT_MODELS)})"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading, use cached audio only"
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip computing embeddings (only extract segments)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.batch:
        parser.error("--batch is required")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse models
    models = [m.strip() for m in args.models.split(",")]
    for model in models:
        if model not in EMBEDDING_DIMS:
            logger.error(f"Unknown model: {model}. Available: {list(EMBEDDING_DIMS.keys())}")
            sys.exit(1)

    # Determine base directory
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent / "cleaning" / "tasks" / "voice_matching"

    # Process batch
    try:
        process_batch(
            batch_name=args.batch,
            base_dir=base_dir,
            cache_dir=args.cache_dir.resolve(),
            results_dir=args.results_dir.resolve(),
            models=models,
            skip_download=args.skip_download,
            skip_embeddings=args.skip_embeddings,
            episode_filter=args.episode
        )
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
