"""Screenshot comparator for page state verification."""
import numpy as np
from typing import Optional, Any

from PIL import Image
import io

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenshotComparator:
    """Compares screenshots to verify expected states."""

    def __init__(self, threshold: float = 0.85):
        """Initialize comparator.

        Args:
            threshold: Similarity threshold (0-1)
        """
        self.threshold = threshold

    def compare_images(
        self,
        img1_bytes: bytes,
        img2_bytes: bytes,
    ) -> dict[str, Any]:
        """Compare two images using pixel comparison.

        Args:
            img1_bytes: First image bytes
            img2_bytes: Second image bytes

        Returns:
            Dict with similarity score and diff info
        """
        try:
            img1 = Image.open(io.BytesIO(img1_bytes)).convert("RGB")
            img2 = Image.open(io.BytesIO(img2_bytes)).convert("RGB")

            # Resize to same size if different
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            # Convert to numpy arrays
            arr1 = np.array(img1)
            arr2 = np.array(img2)

            # Calculate similarity
            similarity = self._calculate_similarity(arr1, arr2)

            # Calculate difference
            diff = np.abs(arr1.astype(float) - arr2.astype(float))
            diff_score = float(np.mean(diff))

            return {
                "similar": similarity >= self.threshold,
                "similarity": float(similarity),
                "diff_score": diff_score,
                "same_size": arr1.shape == arr2.shape,
            }

        except Exception as e:
            logger.error(f"Image comparison error: {e}")
            return {
                "similar": False,
                "error": str(e),
            }

    def _calculate_similarity(self, arr1: np.ndarray, arr2: np.ndarray) -> float:
        """Calculate cosine similarity between image arrays."""
        # Flatten arrays
        flat1 = arr1.flatten().astype(float)
        flat2 = arr2.flatten().astype(float)

        # Normalize
        norm1 = np.linalg.norm(flat1)
        norm2 = np.linalg.norm(flat2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Cosine similarity
        return float(np.dot(flat1, flat2) / (norm1 * norm2))

    def find_diff_regions(
        self,
        img1_bytes: bytes,
        img2_bytes: bytes,
        threshold: int = 30,
    ) -> list[dict]:
        """Find regions that differ between images.

        Args:
            img1_bytes: First image bytes
            img2_bytes: Second image bytes
            threshold: Pixel difference threshold

        Returns:
            List of differing regions
        """
        try:
            img1 = Image.open(io.BytesIO(img1_bytes)).convert("RGB")
            img2 = Image.open(io.BytesIO(img2_bytes)).convert("RGB")

            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            arr1 = np.array(img1)
            arr2 = np.array(img2)

            # Calculate per-pixel difference
            diff = np.abs(arr1.astype(float) - arr2.astype(float))
            diff_sum = np.sum(diff, axis=2)

            # Find regions with significant difference
            mask = diff_sum > threshold
            regions = []

            # Simple grid-based region detection
            h, w = mask.shape
            grid_size = 50

            for i in range(0, h, grid_size):
                for j in range(0, w, grid_size):
                    region = mask[i : i + grid_size, j : j + grid_size]
                    if np.any(region):
                        regions.append(
                            {
                                "x": j,
                                "y": i,
                                "width": grid_size,
                                "height": grid_size,
                                "diff_pixels": int(np.sum(region)),
                            }
                        )

            return regions

        except Exception as e:
            logger.error(f"Diff region finding error: {e}")
            return []
