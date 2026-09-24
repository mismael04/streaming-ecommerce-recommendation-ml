import shutil
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = PROJECT_ROOT / "models"
MODEL_FILE = MODEL_DIR / "recommender.joblib"

INFERENCE_DIR = PROJECT_ROOT / "src" / "inference"

BUILD_DIR = PROJECT_ROOT / "build" / "model"

OUTPUT_DIR = PROJECT_ROOT / "build"

OUTPUT_FILE = OUTPUT_DIR / "model.tar.gz"


def main():
    print("Preparing SageMaker model package...")

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model artifact not found: {MODEL_FILE}"
        )

    inference_file = INFERENCE_DIR / "inference.py"

    if not inference_file.exists():
        raise FileNotFoundError(
            f"Inference script not found: {inference_file}"
        )

    # Start with a clean build directory.
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    BUILD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Copy files directly to the root of the build staging directory.
    shutil.copy2(
        MODEL_FILE,
        BUILD_DIR / "recommender.joblib",
    )

    shutil.copy2(
        inference_file,
        BUILD_DIR / "inference.py",
    )

    # Create model.tar.gz with a flat structure.
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    with tarfile.open(
        OUTPUT_FILE,
        "w:gz",
    ) as tar:
        tar.add(
            BUILD_DIR / "recommender.joblib",
            arcname="recommender.joblib",
        )

        tar.add(
            BUILD_DIR / "inference.py",
            arcname="inference.py",
        )

    print("\nModel package created successfully.")
    print(f"Source model: {MODEL_FILE}")
    print(f"Package:      {OUTPUT_FILE}")

    print("\nPackage contents:")

    with tarfile.open(
        OUTPUT_FILE,
        "r:gz",
    ) as tar:
        for member in tar.getmembers():
            print(f"  {member.name}")


if __name__ == "__main__":
    main()