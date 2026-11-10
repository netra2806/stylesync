# StyleSync Frontend

A responsive fashion-editorial frontend for the StyleSync visual outfit finder.

## Files

- `index.html` — homepage, upload experience, results section, collections, about and footer.
- `static/css/style.css` — responsive styling, layout and animations.
- `static/js/script.js` — upload preview, drag-and-drop, wishlist, filters and Flask API integration.

## Run the frontend

For a quick visual preview, open `index.html` in a browser. The landing page, upload preview and wishlist UI work without a backend. AI search requires the Flask API described below.

For a local server, run from this directory:

```bash
python -m http.server 5500
```

Then open `http://localhost:5500`.

## Flask API contract

The JavaScript expects these optional endpoints on the same origin:

### `POST /api/search`

- Content type: `multipart/form-data`
- File field: `image`
- Returns JSON with one of these shapes:

```json
{
  "results": [
    {
      "id": 1,
      "name": "Linen Blend Shirt",
      "brand": "Example Brand",
      "price": 1890,
      "category": "Tops",
      "color": "Ivory",
      "similarity": 94.5,
      "image_url": "/static/uploads/products/shirt.jpg",
      "product_url": "https://example.com/product"
    }
  ]
}
```

### `GET /api/products` (optional)

Returns `{ "products": [...] }` using the same product fields. If this endpoint is unavailable, the Discover section uses a small illustrative demo catalog. These demo items are not AI search results and are not real shopping recommendations.

## Integration notes

1. Put this frontend into the Flask project's `templates/` and `static/` folders, or adjust the asset paths to match your structure.
2. If using Flask templates, change the stylesheet and script paths to `{{ url_for('static', filename='css/style.css') }}` and `{{ url_for('static', filename='js/script.js') }}`.
3. Make sure the Flask route accepts the multipart field named `image` and returns the JSON shape above.
4. Serve product image URLs from your Flask app (for example, `/static/uploads/products/...`).
5. If your API uses a different route or response shape, update `SEARCH_ENDPOINT`, `PRODUCTS_ENDPOINT`, or `normalizeProduct()` in `static/js/script.js`.

The frontend does not implement CLIP or cosine similarity; those belong in the Python backend. It sends the uploaded image to Flask and renders the returned matches.
