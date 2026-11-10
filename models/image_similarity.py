"""
StyleSync AI Image Similarity Engine
Uses OpenAI CLIP (ViT-B/32) model via Hugging Face Transformers to extract normalized visual feature embeddings
and compute cosine similarity scores between user outfit uploads and product catalog items.
"""

import os
import json
import logging
import numpy as np
from PIL import Image
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylesync.similarity")

# Global model and processor cache
_MODEL = None
_PROCESSOR = None
MODEL_ID = "openai/clip-vit-base-patch32"

def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def load_clip_model():
    """Lazily load the CLIP model and processor to minimize startup memory overhead."""
    global _MODEL, _PROCESSOR
    if _MODEL is None or _PROCESSOR is None:
        logger.info(f"Loading CLIP model: {MODEL_ID}...")
        from transformers import CLIPProcessor, CLIPModel
        device = get_device()
        try:
            # First attempt offline load from local HF cache to avoid unnecessary network latency
            _PROCESSOR = CLIPProcessor.from_pretrained(MODEL_ID, local_files_only=True)
            _MODEL = CLIPModel.from_pretrained(MODEL_ID, local_files_only=True).to(device)
        except Exception:
            # Fall back to online fetch if cache misses
            _PROCESSOR = CLIPProcessor.from_pretrained(MODEL_ID)
            _MODEL = CLIPModel.from_pretrained(MODEL_ID).to(device)
            
        _MODEL.eval()
        logger.info(f"CLIP model loaded successfully on {device}.")
    return _MODEL, _PROCESSOR

def extract_image_embedding(image_input):
    """
    Extract a normalized 512-dimensional feature vector for a given image.
    image_input can be a PIL Image object or a string file path.
    Returns: numpy array of shape (512,) representing the unit-normalized embedding.
    """
    model, processor = load_clip_model()
    device = get_device()

    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"Image not found at path: {image_input}")
        image = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        image = image_input.convert("RGB")
    else:
        raise ValueError("Invalid image input type. Expected file path or PIL.Image.Image")

    # Resize/pad appropriately if needed, but processor handles standard CLIP preprocessing
    inputs = processor(images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
        # Normalize to unit vector for fast cosine similarity via dot product
        image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
        embedding = image_features.cpu().numpy().flatten()

    return embedding.astype(np.float32)

def compute_cosine_similarity(query_embedding, catalog_embeddings):
    """
    Compute cosine similarity between query embedding and matrix of catalog embeddings.
    Since embeddings are L2-normalized, cosine similarity is simply the matrix-vector dot product.
    
    query_embedding: (512,) numpy array
    catalog_embeddings: (N, 512) numpy array
    Returns: (N,) numpy array with similarity scores in [-1.0, 1.0]
    """
    if len(catalog_embeddings) == 0:
        return np.array([])
    
    # Ensure 2D
    catalog_embeddings = np.asarray(catalog_embeddings, dtype=np.float32)
    query_embedding = np.asarray(query_embedding, dtype=np.float32).reshape(-1)

    # Dot product calculation
    similarities = np.dot(catalog_embeddings, query_embedding)
    return similarities

def rank_similar_products(query_embedding, products, top_k=10):
    """
    Rank products by cosine similarity against the query embedding.
    products: list of dicts, each must have an 'embedding' key (either list or np.ndarray)
    top_k: max number of results to return
    
    Returns: list of products augmented with 'similarity_score' (0.0 - 1.0) and 'match_percentage' (0 - 100)
    """
    valid_products = []
    embeddings = []

    for p in products:
        emb = p.get("embedding")
        if emb is None:
            continue
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                continue
        emb_np = np.array(emb, dtype=np.float32)
        if emb_np.shape[0] == 512:
            valid_products.append(p)
            embeddings.append(emb_np)

    if not valid_products:
        return []

    embeddings_matrix = np.vstack(embeddings)
    scores = compute_cosine_similarity(query_embedding, embeddings_matrix)

    # Sort descending
    sorted_indices = np.argsort(scores)[::-1]

    results = []
    for idx in sorted_indices[:top_k]:
        prod = dict(valid_products[idx])
        raw_score = float(scores[idx])
        # Map raw cosine similarity [-1, 1] to human-intuitive percentage
        # CLIP image-image similarities for fashion usually sit in range 0.4 - 0.95
        # We present normalized confidence: clamp between 0.35 and 0.95 to scale 50% - 99%
        normalized_pct = max(30.0, min(99.0, ((raw_score - 0.25) / (0.90 - 0.25)) * 60.0 + 39.0))
        prod["similarity_score"] = round(raw_score, 4)
        prod["match_percentage"] = int(round(normalized_pct))
        # Remove raw bulky embedding from return payload
        prod.pop("embedding", None)
        results.append(prod)

    return results
