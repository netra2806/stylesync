"""
Catalog seeder for StyleSync.
Downloads high-resolution genuine fashion photography, stores them locally,
computes authentic CLIP ViT-B/32 image embeddings, and populates the SQLite catalog.
"""

import os
import io
import json
import logging
import requests
from PIL import Image
from database.db_manager import init_db, insert_product, get_all_products
from models.image_similarity import extract_image_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylesync.seeder")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS_DIR = os.path.join(BASE_DIR, "static", "uploads", "products")
COLLECTIONS_DIR = os.path.join(BASE_DIR, "static", "images", "collections")

os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(COLLECTIONS_DIR, exist_ok=True)

# Curated High-Fashion Catalog Dataset with genuine fashion photography & real brand shopping URLs
CATALOG_ITEMS = [
    {
        "name": "Oversized Tailored Wool Trench Coat",
        "brand": "Totême Atelier",
        "category": "Minimalist Fashion",
        "color": "Beige",
        "price": 890.00,
        "description": "Double-breasted trench in brushed Italian melton wool. Structured storm flaps and dropped shoulder silhouette.",
        "image_url_source": "https://images.unsplash.com/photo-1544441893-675973e31985?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://toteme-studio.com",
        "filename": "toteme_beige_trench.jpg"
    },
    {
        "name": "Heavyweight Boxy Hoodie",
        "brand": "Fear of God Essentials",
        "category": "Streetwear",
        "color": "Black",
        "price": 140.00,
        "description": "Custom 480gsm cotton fleece with dropped shoulders, raw hems, and understated tonal logo stamp on back.",
        "image_url_source": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://fearofgod.com",
        "filename": "essentials_black_hoodie.jpg"
    },
    {
        "name": "Backless Silk Slip Maxi Dress",
        "brand": "Khaite New York",
        "category": "Dresses",
        "color": "Black",
        "price": 1250.00,
        "description": "Heavyweight 100% silk charmeuse bias cut gown with ultra-thin criss-cross straps and subtle side slit.",
        "image_url_source": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://khaite.com",
        "filename": "khaite_silk_slip_black.jpg"
    },
    {
        "name": "Sculpted Hourglass Blazer",
        "brand": "Mugler",
        "category": "Party Wear",
        "color": "Black",
        "price": 1690.00,
        "description": "Signature Mugler architecture featuring razor-sharp peaked lapels, sculpted waist synching and power shoulders.",
        "image_url_source": "https://images.unsplash.com/photo-1584273143981-41c073dfe8f8?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://fashionphile.com",
        "filename": "mugler_hourglass_blazer.jpg"
    },
    {
        "name": "Relaxed Cable-Knit Cashmere Cardigan",
        "brand": "The Row",
        "category": "Casual Wear",
        "color": "Cream",
        "price": 1950.00,
        "description": "Seven-ply Mongolian cashmere with horn button closures. Unmatched tactile warmth and drapey comfort.",
        "image_url_source": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://therow.com",
        "filename": "therow_cashmere_cream.jpg"
    },
    {
        "name": "Hand-Embroidered Chanderi Kurta Set",
        "brand": "Sabyasachi Mukherjee",
        "category": "Traditional Wear",
        "color": "Gold",
        "price": 1850.00,
        "description": "Heritage tissue chanderi woven with antique zardozi borders, paired with matching flared churidar and diaphanous dupatta.",
        "image_url_source": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://sabyasachi.com",
        "filename": "sabyasachi_gold_kurta.jpg"
    },
    {
        "name": "Padded Leather Cassette Crossbody Bag",
        "brand": "Bottega Veneta",
        "category": "Accessories",
        "color": "Brown",
        "price": 3500.00,
        "description": "Double-face orthogonal maxi intreccio weave in supple lambskin with adjustable shoulder strap and triangular buckle.",
        "image_url_source": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://bottegaveneta.com",
        "filename": "bottega_cassette_brown.jpg"
    },
    {
        "name": "Wide-Leg Pleated Tailored Trousers",
        "brand": "COS Atelier",
        "category": "Minimalist Fashion",
        "color": "Beige",
        "price": 175.00,
        "description": "Responsibly sourced wool-blend trousers with fluid deep front pleats, slant pockets, and a clean hook-and-bar waistband.",
        "image_url_source": "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://cos.com",
        "filename": "cos_pleated_trousers_beige.jpg"
    },
    {
        "name": "Distressed Raw-Edge Denim Jacket",
        "brand": "Balenciaga",
        "category": "Streetwear",
        "color": "Blue",
        "price": 1450.00,
        "description": "Vintage Japanese washed selvedge denim with dropped kimono armholes, raw cuffs, and destroyed back hem.",
        "image_url_source": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://balenciaga.com",
        "filename": "balenciaga_denim_jacket.jpg"
    },
    {
        "name": "Pleated Emerald Green Cocktail Dress",
        "brand": "Self-Portrait",
        "category": "Party Wear",
        "color": "Green",
        "price": 495.00,
        "description": "Lace bodice detailing combined with knife-pleated flowing georgette skirt in jewel-toned emerald green.",
        "image_url_source": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://self-portrait.com",
        "filename": "self_portrait_emerald_dress.jpg"
    },
    {
        "name": "Raw Silk Banarasi Saree with Zari",
        "brand": "Raw Mango",
        "category": "Traditional Wear",
        "color": "Red",
        "price": 920.00,
        "description": "Handspun Varanasi silk handloom featuring traditional floral boota patterns and rich gold pallu edging.",
        "image_url_source": "https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://rawmango.com",
        "filename": "raw_mango_red_banarasi.jpg"
    },
    {
        "name": "Sculptural Acetate Cat-Eye Sunglasses",
        "brand": "Gentle Monster",
        "category": "Accessories",
        "color": "Black",
        "price": 320.00,
        "description": "Curved geometric front silhouette with metallic core temples and 99.9% UV protected tinted Zeis lenses.",
        "image_url_source": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://gentlemonster.com",
        "filename": "gentle_monster_cateye.jpg"
    },
    {
        "name": "Heavyweight Cotton Poplin Shirt",
        "brand": "Lemaire",
        "category": "Minimalist Fashion",
        "color": "White",
        "price": 440.00,
        "description": "Crisp Italian poplin with signature twisted collar, mother-of-pearl buttons, and structured elongated cuffs.",
        "image_url_source": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://lemaire.fr",
        "filename": "lemaire_poplin_white.jpg"
    },
    {
        "name": "Linen Drawstring Resort Trousers",
        "brand": "Jacquemus",
        "category": "Casual Wear",
        "color": "Olive",
        "price": 380.00,
        "description": "Garment-dyed pure French flax with relaxed tapered leg, twill belt loop accent, and contrast stitching.",
        "image_url_source": "https://images.unsplash.com/photo-1479064555552-3ef4979f8908?auto=format&fit=crop&w=800&q=80",
        "shopping_url": "https://jacquemus.com",
        "filename": "jacquemus_olive_linen.jpg"
    }
]

COLLECTION_IMAGES = {
    "streetwear.jpg": "https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=800&q=80",
    "minimalist.jpg": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=800&q=80",
    "dresses.jpg": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=800&q=80",
    "casual.jpg": "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?auto=format&fit=crop&w=800&q=80",
    "party.jpg": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=800&q=80",
    "traditional.jpg": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
    "accessories.jpg": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=800&q=80"
}

def download_and_save_image(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        # Resize to standard haute lookbook bounds (e.g. 800x1000 max) to conserve storage while retaining crisp fidelity
        img.thumbnail((800, 1000), Image.Resampling.LANCZOS)
        img.save(save_path, "JPEG", quality=85)
        logger.info(f"Saved: {save_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to download {url}: {e}")
        return False

def seed_catalog():
    init_db()
    existing = get_all_products()
    if existing:
        logger.info(f"Database already contains {len(existing)} products. Skipping duplicate seeding.")
        return

    # 1. Download Collection background imagery
    logger.info("Downloading editorial collection headers...")
    for filename, url in COLLECTION_IMAGES.items():
        coll_path = os.path.join(COLLECTIONS_DIR, filename)
        if not os.path.exists(coll_path):
            download_and_save_image(url, coll_path)

    # 2. Download and vectorize catalog products
    logger.info("Seeding products with authentic CLIP embeddings...")
    for idx, item in enumerate(CATALOG_ITEMS, 1):
        filename = item["filename"]
        local_path = os.path.join(PRODUCTS_DIR, filename)
        
        success = False
        if not os.path.exists(local_path):
            success = download_and_save_image(item["image_url_source"], local_path)
        else:
            success = True

        relative_img_url = f"/static/uploads/products/{filename}" if success else item["image_url_source"]

        # Compute genuine CLIP visual embedding
        embedding = None
        if os.path.exists(local_path):
            try:
                embedding = extract_image_embedding(local_path)
                logger.info(f"[{idx}/{len(CATALOG_ITEMS)}] Generated 512-D embedding for: {item['name']}")
            except Exception as e:
                logger.error(f"Error embedding {item['name']}: {e}")

        insert_product(
            name=item["name"],
            brand=item["brand"],
            category=item["category"],
            color=item["color"],
            price=item["price"],
            description=item["description"],
            image_url=relative_img_url,
            shopping_url=item["shopping_url"],
            embedding=embedding
        )

    logger.info("StyleSync catalog seeded successfully with AI embeddings!")

if __name__ == "__main__":
    seed_catalog()

