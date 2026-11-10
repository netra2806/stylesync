"""
Flask Application for StyleSync - AI-Powered Outfit Finder
"""

import os
import uuid
import json
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_cors import CORS

from database.db_manager import (
    init_db, get_all_products, get_product_by_id, insert_product,
    update_product, delete_product, log_search, get_recent_searches
)
from models.image_similarity import extract_image_embedding, rank_similar_products

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylesync.app")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
PRODUCTS_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "products")
TEMP_UPLOAD_DIR = os.path.join(UPLOAD_FOLDER, "temporary")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "stylesync-fashion-luxury-secret-key-2026")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure directories exist
os.makedirs(PRODUCTS_UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
init_db()

@app.route("/")
def index():
    recent_searches = get_recent_searches(limit=4)
    # Featured collection highlights
    featured_products = get_all_products()[:8]
    return render_template("index.html", recent_searches=recent_searches, featured_products=featured_products)

@app.route("/discover")
def discover():
    category = request.args.get("category", "All")
    color = request.args.get("color", "All")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort_by = request.args.get("sort", "best_match")
    
    products = get_all_products(
        category=None if category == "All" else category,
        color=None if color == "All" else color,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        sort_by=sort_by
    )
    
    categories = ["Streetwear", "Casual Wear", "Party Wear", "Dresses", "Traditional Wear", "Accessories", "Minimalist Fashion"]
    colors = ["Black", "White", "Beige", "Brown", "Cream", "Blue", "Olive", "Red", "Gold"]
    
    return render_template("discover.html", 
                           products=products, 
                           categories=categories, 
                           colors=colors,
                           selected_category=category,
                           selected_color=color,
                           selected_sort=sort_by)

@app.route("/collections")
def collections():
    collections_data = [
        {
            "id": "streetwear",
            "title": "Urban Contour: Modern Streetwear",
            "tagline": "Oversized silhouettes & raw aesthetics",
            "category": "Streetwear",
            "image": "/static/images/collections/streetwear.jpg",
            "description": "High-octane utilitarian cuts, structured outerwear, and effortless statement layering curated for the urban modernist."
        },
        {
            "id": "minimalist",
            "title": "Atelier Serene: Minimalist Fashion",
            "tagline": "Understated luxury & clean lines",
            "category": "Minimalist Fashion",
            "image": "/static/images/collections/minimalist.jpg",
            "description": "Sculptural tailoring in warm ecru, sand and espresso palettes. Designed for longevity and quiet elegance."
        },
        {
            "id": "dresses",
            "title": "Midnight & Silk: Designer Dresses",
            "tagline": "Fluid drapes and evening sophistication",
            "category": "Dresses",
            "image": "/static/images/collections/dresses.jpg",
            "description": "Captivating slip silhouettes, backless architectural gowns and delicate textures for grand occasions."
        },
        {
            "id": "casual",
            "title": "Weekend Riviera: Casual Wear",
            "tagline": "Breezy knits, linen blends & relaxed tailoring",
            "category": "Casual Wear",
            "image": "/static/images/collections/casual.jpg",
            "description": "Effortless morning-to-night staples combining supreme tactile comfort with refined Parisian proportions."
        },
        {
            "id": "party",
            "title": "Velvet Soirée: Party Wear",
            "tagline": "High shine, sharp contrasts & allure",
            "category": "Party Wear",
            "image": "/static/images/collections/party.jpg",
            "description": "Show-stopping tailored blazers, metallic sheens and dramatic cuts made to own the spotlight."
        },
        {
            "id": "traditional",
            "title": "Heritage Weaves: Traditional Wear",
            "tagline": "Handcrafted elegance meets contemporary grace",
            "category": "Traditional Wear",
            "image": "/static/images/collections/traditional.jpg",
            "description": "Intricate craftsmanship, rich hand-woven textiles and royal silhouettes honoring timeless cultural artistry."
        },
        {
            "id": "accessories",
            "title": "Accents of Distinction: Accessories",
            "tagline": "Artisanal leather & sculpted metal",
            "category": "Accessories",
            "image": "/static/images/collections/accessories.jpg",
            "description": "Signature leather shoulder bags, handcrafted jewelry, and handcrafted sunglasses that define the entire look."
        }
    ]
    return render_template("collections.html", collections=collections_data)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")

@app.route("/search-outfit", methods=["POST"])
def search_outfit():
    """
    Core AI Visual Search Endpoint:
    Accepts uploaded outfit image -> Generates CLIP embedding -> Ranks catalog by cosine similarity
    """
    if "image" not in request.files:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "No image file provided."}), 400
        flash("No image provided. Please select an outfit image.", "error")
        return redirect(url_for("index"))

    file = request.files["image"]
    if file.filename == "":
        flash("No selected file.", "error")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Invalid image format. Allowed formats: JPG, JPEG, PNG, WEBP.", "error")
        return redirect(url_for("index"))

    # Secure unique filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    temp_save_path = os.path.join(TEMP_UPLOAD_DIR, unique_filename)
    file.save(temp_save_path)

    try:
        # Run AI visual embedding extraction
        query_embedding = extract_image_embedding(temp_save_path)
        all_catalog = get_all_products()
        
        # Rank top 10 visually similar products via cosine similarity
        matched_products = rank_similar_products(query_embedding, all_catalog, top_k=10)
        
        # Determine dominant matched category for history logging
        dominant_category = matched_products[0]["category"] if matched_products else "Fashion"
        
        # Log search record
        relative_query_path = f"/static/uploads/temporary/{unique_filename}"
        log_search(relative_query_path, dominant_category)
        
        # Render results page
        return render_template("results.html", 
                               reference_image=relative_query_path,
                               products=matched_products,
                               total_matches=len(matched_products))
    except Exception as e:
        logger.error(f"Error during visual similarity search: {e}", exc_info=True)
        flash(f"AI image analysis error: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/api/search", methods=["POST"])
def api_search():
    """JSON API endpoint for asynchronous frontend upload and instant results."""
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image uploaded"}), 400
    
    file = request.files["image"]
    if not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Unsupported file format. Use JPG, PNG, or WEBP."}), 400
        
    ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    temp_save_path = os.path.join(TEMP_UPLOAD_DIR, unique_filename)
    file.save(temp_save_path)
    
    try:
        query_embedding = extract_image_embedding(temp_save_path)
        all_catalog = get_all_products()
        matched_products = rank_similar_products(query_embedding, all_catalog, top_k=10)
        
        relative_query_path = f"/static/uploads/temporary/{unique_filename}"
        dominant_cat = matched_products[0]["category"] if matched_products else "General"
        log_search(relative_query_path, dominant_cat)
        
        # Format products to match both 'results' and 'products' conventions
        formatted_matches = []
        for p in matched_products:
            p_dict = dict(p)
            p_dict["similarity"] = p.get("match_percentage", 90)
            p_dict["product_url"] = p.get("shopping_url", "#")
            formatted_matches.append(p_dict)

        return jsonify({
            "success": True,
            "reference_image": relative_query_path,
            "results": formatted_matches,
            "products": formatted_matches,
            "matches": formatted_matches,
            "count": len(formatted_matches)
        })
    except Exception as e:
        logger.error(f"API Search Error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/products")
def api_products():
    category = request.args.get("category")
    color = request.args.get("color")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort_by = request.args.get("sort")
    search_q = request.args.get("q", "").strip().lower()

    products = get_all_products(
        category=category,
        color=color,
        min_price=float(min_price) if min_price else None,
        max_price=float(max_price) if max_price else None,
        sort_by=sort_by
    )

    if search_q:
        products = [
            p for p in products 
            if search_q in p["name"].lower() or search_q in p["brand"].lower() or search_q in p["category"].lower()
        ]

    # Clean embeddings before sending JSON
    for p in products:
        p.pop("embedding", None)

    return jsonify({"success": True, "products": products, "count": len(products)})

# ADMIN ROUTES
@app.route("/admin")
def admin():
    products = get_all_products(sort_by="newest")
    categories = ["Streetwear", "Casual Wear", "Party Wear", "Dresses", "Traditional Wear", "Accessories", "Minimalist Fashion"]
    colors = ["Black", "White", "Beige", "Brown", "Cream", "Blue", "Olive", "Red", "Gold", "Green", "Grey"]
    return render_template("admin.html", products=products, categories=categories, colors=colors)

@app.route("/admin/product/add", methods=["POST"])
def admin_add_product():
    name = request.form.get("name")
    brand = request.form.get("brand")
    category = request.form.get("category")
    color = request.form.get("color")
    price = request.form.get("price")
    description = request.form.get("description", "")
    shopping_url = request.form.get("shopping_url")

    if not name or not brand or not category or not price or not shopping_url:
        flash("Please fill in all mandatory product fields.", "error")
        return redirect(url_for("admin"))

    image_url = None
    embedding = None

    if "image" in request.files and request.files["image"].filename != "":
        file = request.files["image"]
        if allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"prod_{uuid.uuid4().hex[:10]}.{ext}"
            file_path = os.path.join(PRODUCTS_UPLOAD_DIR, filename)
            file.save(file_path)
            image_url = f"/static/uploads/products/{filename}"
            
            # Extract and store embedding automatically
            try:
                emb = extract_image_embedding(file_path)
                embedding = emb
            except Exception as e:
                logger.error(f"Failed to generate embedding for added product: {e}")
        else:
            flash("Invalid image format.", "error")
            return redirect(url_for("admin"))
    else:
        # Fallback to image url if text provided
        image_url = request.form.get("image_url_text", "/static/images/placeholder.jpg")

    insert_product(name, brand, category, color, price, description, image_url, shopping_url, embedding)
    flash(f"Product '{name}' added successfully with AI visual embedding generated!", "success")
    return redirect(url_for("admin"))

@app.route("/admin/product/edit/<int:product_id>", methods=["POST"])
def admin_edit_product(product_id):
    existing = get_product_by_id(product_id)
    if not existing:
        flash("Product not found.", "error")
        return redirect(url_for("admin"))

    name = request.form.get("name")
    brand = request.form.get("brand")
    category = request.form.get("category")
    color = request.form.get("color")
    price = request.form.get("price")
    description = request.form.get("description")
    shopping_url = request.form.get("shopping_url")

    image_url = existing["image_url"]
    embedding = None

    if "image" in request.files and request.files["image"].filename != "":
        file = request.files["image"]
        if allowed_file(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            filename = f"prod_{uuid.uuid4().hex[:10]}.{ext}"
            file_path = os.path.join(PRODUCTS_UPLOAD_DIR, filename)
            file.save(file_path)
            image_url = f"/static/uploads/products/{filename}"
            try:
                embedding = extract_image_embedding(file_path)
            except Exception as e:
                logger.error(f"Failed to compute embedding on edit: {e}")

    update_product(product_id, name, brand, category, color, price, description, image_url, shopping_url, embedding)
    flash(f"Product #{product_id} updated successfully.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/product/delete/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    delete_product(product_id)
    flash(f"Product #{product_id} deleted from catalog.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(413)
def file_too_large(e):
    flash("The uploaded image exceeds the 8 MB maximum size limit.", "error")
    return redirect(url_for("index")), 413

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"\n=======================================================")
    print(f"  ✦ StyleSync AI Server running on http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(debug=True, host="127.0.0.1", port=port)

