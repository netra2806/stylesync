/* StyleSync frontend
   Flask integration contract:
   POST /api/search (multipart/form-data, field name: image)
   Expected JSON: { results: [{ id, name, brand, price, image_url, category, color, similarity, product_url }] }
   Optional GET /api/products returns { products: [...] } for the Discover catalog.
*/
// Always determine the working backend API origin
const API_BASE = (window.location.origin && window.location.origin.startsWith('http') && window.location.port === '5001')
  ? ''
  : 'http://127.0.0.1:5001';
const SEARCH_ENDPOINT = `${API_BASE}/api/search`;
const PRODUCTS_ENDPOINT = `${API_BASE}/api/products`;
const MAX_FILE_SIZE = 8 * 1024 * 1024;

const $ = (selector) => document.querySelector(selector);
const imageInput = $('#imageInput');
const dropZone = $('#dropZone');
const uploadEmpty = $('#uploadEmpty');
const uploadPreview = $('#uploadPreview');
const previewImage = $('#previewImage');
const findMatchesButton = $('#findMatchesButton');
const searchLoader = $('#searchLoader');
const searchError = $('#searchError');
const resultsSection = $('#resultsSection');
const resultsGrid = $('#resultsGrid');
const toast = $('#toast');

let selectedFile = null;
let currentResults = [];
let currentReferenceUrl = '';
let allProducts = [];
let wishlist = loadWishlist();
let toastTimer;

const demoProducts = [
  { id: 'demo-1', name: 'The Sunday Knit', brand: 'FORME STUDIO', price: 1890, category: 'Tops', color: 'Cream', similarity: 96, image_url: 'https://images.unsplash.com/photo-1551163943-3f6a855d1153?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-2', name: 'Everyday Tailored', brand: 'THE EDIT', price: 2490, category: 'Trousers', color: 'Beige', similarity: 93, image_url: 'https://images.unsplash.com/photo-1509631179647-0177331693ae?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-3', name: 'Soft Structure Shirt', brand: 'OBJECTS', price: 1590, category: 'Tops', color: 'White', similarity: 91, image_url: 'https://images.unsplash.com/photo-1598554747436-c9293d6a588f?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-4', name: 'The City Denim', brand: 'DAY OFF', price: 2190, category: 'Jeans', color: 'Blue', similarity: 89, image_url: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-5', name: 'After Hours Dress', brand: 'MAISON N°8', price: 3290, category: 'Dresses', color: 'Black', similarity: 88, image_url: 'https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-6', name: 'Weekend Co-ord', brand: 'SOFT FORM', price: 2790, category: 'Sets', color: 'Olive', similarity: 86, image_url: 'https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-7', name: 'Sculpted Mini Bag', brand: 'SIDE NOTE', price: 1390, category: 'Accessories', color: 'Brown', similarity: 84, image_url: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=700&q=85', product_url: '#' },
  { id: 'demo-8', name: 'Classic Low Top', brand: 'COMMON GROUND', price: 2990, category: 'Shoes', color: 'White', similarity: 82, image_url: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=700&q=85', product_url: '#' }
];

function loadWishlist() {
  try { return JSON.parse(localStorage.getItem('stylesync-wishlist') || '[]'); }
  catch { return []; }
}
function saveWishlist() {
  localStorage.setItem('stylesync-wishlist', JSON.stringify(wishlist));
  $('#wishlistCount').textContent = wishlist.length;
}
function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
}
function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}
function formatPrice(value) {
  if (typeof value === 'number') return `₹${value.toLocaleString('en-IN')}`;
  if (value === undefined || value === null || value === '') return 'Price unavailable';
  return String(value).match(/[₹$€£]/) ? String(value) : `₹${value}`;
}
function normalizeProduct(product, index = 0) {
  let img = product.image_url ?? product.image ?? product.image_path ?? '';
  if (img && img.startsWith('/')) {
    img = `${API_BASE}${img}`;
  }
  return {
    id: String(product.id ?? product.product_id ?? `product-${index}`),
    name: product.name ?? product.title ?? 'Untitled product',
    brand: product.brand ?? 'INDEPENDENT LABEL',
    price: product.price ?? product.displayed_price ?? '',
    category: product.category ?? 'Fashion',
    color: product.color ?? '',
    similarity: Number(product.similarity ?? product.similarity_score ?? product.score ?? 0),
    image_url: img,
    product_url: product.product_url ?? product.url ?? '#'
  };
}
function safeExternalUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '#';
  } catch { return '#'; }
}
function productCard(product) {
  const saved = wishlist.some(item => item.id === product.id);
  const similarity = product.similarity > 0 ? `${Math.round(product.similarity)}% MATCH` : 'STYLE PICK';
  const link = safeExternalUrl(product.product_url);
  const image = product.image_url || 'https://placehold.co/700x900/eee9dd/82796f?text=Image+unavailable';
  return `
    <article class="product-card">
      <div class="product-image-wrap">
        <img src="${escapeHtml(image)}" alt="${escapeHtml(product.name)}" loading="lazy" onerror="this.src='https://placehold.co/700x900/eee9dd/82796f?text=Image+unavailable'" />
        <span class="product-badge">${escapeHtml(similarity)}</span>
        <button class="product-wishlist ${saved ? 'saved' : ''}" data-wishlist="${escapeHtml(product.id)}" aria-label="${saved ? 'Remove from' : 'Add to'} wishlist">${saved ? '♥' : '♡'}</button>
      </div>
      <div class="product-info">
        <div class="product-meta"><span>${escapeHtml(product.brand)}</span><span>${escapeHtml(product.category)}</span></div>
        <h3>${escapeHtml(product.name)}</h3>
        <div class="product-bottom"><span class="product-price">${escapeHtml(formatPrice(product.price))}</span><a class="product-link" href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">View product ↗</a></div>
      </div>
    </article>`;
}
function renderProducts(products, target = resultsGrid) {
  target.innerHTML = products.map(productCard).join('');
}
function updateWishlistButton(id) {
  const button = document.querySelector(`[data-wishlist="${CSS.escape(id)}"]`);
  if (!button) return;
  const saved = wishlist.some(item => item.id === id);
  button.classList.toggle('saved', saved);
  button.textContent = saved ? '♥' : '♡';
  button.setAttribute('aria-label', saved ? 'Remove from wishlist' : 'Add to wishlist');
}
function toggleWishlist(id) {
  const product = [...allProducts, ...currentResults, ...demoProducts].find(item => item.id === id);
  if (!product) return;
  const exists = wishlist.some(item => item.id === id);
  wishlist = exists ? wishlist.filter(item => item.id !== id) : [...wishlist, product];
  saveWishlist();
  updateWishlistButton(id);
  renderWishlist();
  showToast(exists ? 'Removed from your saved styles.' : 'Added to your saved styles.');
}
function renderWishlist() {
  const container = $('#wishlistItems');
  if (!wishlist.length) {
    container.innerHTML = '<p class="wishlist-empty">Your saved styles will live here. Tap the ♡ on anything you love.</p>';
    return;
  }
  container.innerHTML = wishlist.map(item => `
    <div class="wishlist-item">
      <img src="${escapeHtml(item.image_url || '')}" alt="${escapeHtml(item.name)}" onerror="this.src='https://placehold.co/200x250/eee9dd/82796f?text=Style'" />
      <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.brand)} · ${escapeHtml(formatPrice(item.price))}</small></div>
      <button data-remove-wishlist="${escapeHtml(item.id)}" aria-label="Remove ${escapeHtml(item.name)}">×</button>
    </div>`).join('');
}

function selectImage(file) {
  searchError.classList.add('hidden');
  if (!file) return;
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    showToast('Please choose a JPG, PNG or WEBP image.');
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    showToast('That image is over 8 MB. Choose a smaller file.');
    return;
  }
  selectedFile = file;
  if (currentReferenceUrl) URL.revokeObjectURL(currentReferenceUrl);
  currentReferenceUrl = URL.createObjectURL(file);
  previewImage.src = currentReferenceUrl;
  uploadEmpty.classList.add('hidden');
  uploadPreview.classList.remove('hidden');
  findMatchesButton.disabled = false;
  $('#uploadStatus').textContent = `${file.name} is ready for visual search.`;
}
function clearImage() {
  selectedFile = null;
  imageInput.value = '';
  if (currentReferenceUrl) URL.revokeObjectURL(currentReferenceUrl);
  currentReferenceUrl = '';
  previewImage.src = '';
  uploadPreview.classList.add('hidden');
  uploadEmpty.classList.remove('hidden');
  findMatchesButton.disabled = true;
  $('#uploadStatus').textContent = 'Your inspiration stays yours. Uploads are used for your search.';
}

async function searchSimilarProducts() {
  if (!selectedFile) return;
  searchError.classList.add('hidden');
  resultsSection.classList.add('hidden');
  searchLoader.classList.remove('hidden');
  findMatchesButton.disabled = true;
  const messages = ['Reading your aesthetic...', 'Matching colours and silhouettes...', 'Finding your next favourite...'];
  let messageIndex = 0;
  $('#loaderMessage').textContent = messages[0];
  const messageTimer = setInterval(() => {
    messageIndex = (messageIndex + 1) % messages.length;
    $('#loaderMessage').textContent = messages[messageIndex];
  }, 1400);

  try {
    const formData = new FormData();
    formData.append('image', selectedFile);
    const response = await fetch(SEARCH_ENDPOINT, { method: 'POST', body: formData });
    if (!response.ok) {
      let detail = '';
      try { const errorBody = await response.json(); detail = errorBody.error || errorBody.message || ''; } catch { /* response may not be JSON */ }
      throw new Error(detail || `Search failed (${response.status}). Check the Flask backend.`);
    }
    const payload = await response.json();
    const rawResults = Array.isArray(payload) ? payload : (payload.results || payload.matches || payload.products || []);
    currentResults = rawResults.map(normalizeProduct);
    displayResults(currentResults);
    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    showToast(`${currentResults.length} style match${currentResults.length === 1 ? '' : 'es'} found.`);
  } catch (error) {
    const message = error instanceof TypeError
      ? 'Could not reach the Flask API. Start your backend and make sure POST /api/search accepts an image field named "image".'
      : error.message;
    searchError.textContent = message;
    searchError.classList.remove('hidden');
  } finally {
    clearInterval(messageTimer);
    searchLoader.classList.add('hidden');
    findMatchesButton.disabled = !selectedFile;
  }
}
function displayResults(products) {
  const filtered = applyResultFilters(products);
  $('#resultsCount').textContent = `${filtered.length} MATCH${filtered.length === 1 ? '' : 'ES'}`;
  $('#resultsReferenceImage').src = currentReferenceUrl;
  renderProducts(filtered);
  $('#noResults').classList.toggle('hidden', filtered.length > 0);
  resultsGrid.classList.toggle('hidden', filtered.length === 0);
}
function applyResultFilters(products) {
  const category = $('#categoryFilter').value;
  const sort = $('#sortFilter').value;
  let filtered = category === 'all' ? [...products] : products.filter(item => item.category.toLowerCase() === category.toLowerCase());
  if (sort === 'low') filtered.sort((a, b) => numericPrice(a.price) - numericPrice(b.price));
  else if (sort === 'high') filtered.sort((a, b) => numericPrice(b.price) - numericPrice(a.price));
  else filtered.sort((a, b) => b.similarity - a.similarity);
  return filtered;
}
function numericPrice(value) {
  const number = Number(String(value ?? '').replace(/[^\d.]/g, ''));
  return Number.isFinite(number) ? number : Number.MAX_SAFE_INTEGER;
}

async function loadCatalog() {
  try {
    const response = await fetch(PRODUCTS_ENDPOINT);
    if (!response.ok) throw new Error('Catalog endpoint unavailable');
    const payload = await response.json();
    const products = Array.isArray(payload) ? payload : (payload.products || []);
    if (products.length) allProducts = products.map(normalizeProduct);
  } catch {
    // Demo catalog keeps the Discover UI populated when the optional catalog API is not connected.
    allProducts = demoProducts.map(normalizeProduct);
  }
}

// Upload interactions
$('#browseButton').addEventListener('click', () => imageInput.click());
uploadEmpty.addEventListener('click', (event) => {
  if (!event.target.closest('button')) imageInput.click();
});
imageInput.addEventListener('change', () => selectImage(imageInput.files[0]));
$('#removeImage').addEventListener('click', clearImage);
findMatchesButton.addEventListener('click', searchSimilarProducts);
['dragenter', 'dragover'].forEach(type => dropZone.addEventListener(type, event => {
  event.preventDefault(); event.stopPropagation(); dropZone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach(type => dropZone.addEventListener(type, event => {
  event.preventDefault(); event.stopPropagation(); dropZone.classList.remove('dragging');
}));
dropZone.addEventListener('drop', event => selectImage(event.dataTransfer.files[0]));

// Product actions and filters
document.addEventListener('click', event => {
  const wishlistButton = event.target.closest('[data-wishlist]');
  if (wishlistButton) toggleWishlist(wishlistButton.dataset.wishlist);
  const removeButton = event.target.closest('[data-remove-wishlist]');
  if (removeButton) {
    const id = removeButton.dataset.removeWishlist;
    wishlist = wishlist.filter(item => item.id !== id);
    saveWishlist(); renderWishlist(); updateWishlistButton(id);
  }
});
$('#categoryFilter').addEventListener('change', () => displayResults(currentResults));
$('#sortFilter').addEventListener('change', () => displayResults(currentResults));
$('#resetSearch').addEventListener('click', () => {
  clearImage(); resultsSection.classList.add('hidden'); $('#visual-search').scrollIntoView({ behavior: 'smooth' });
});

// Navigation and wishlist panel
$('#menuToggle').addEventListener('click', () => {
  const isOpen = $('#mainNav').classList.toggle('open');
  $('#menuToggle').setAttribute('aria-expanded', String(isOpen));
});
document.querySelectorAll('.main-nav a').forEach(link => link.addEventListener('click', () => {
  $('#mainNav').classList.remove('open'); $('#menuToggle').setAttribute('aria-expanded', 'false');
}));
$('#searchFocusButton').addEventListener('click', () => $('#visual-search').scrollIntoView({ behavior: 'smooth' }));
$('#wishlistButton').addEventListener('click', () => { renderWishlist(); $('#wishlistPanel').classList.remove('hidden'); });
$('#closeWishlist').addEventListener('click', () => $('#wishlistPanel').classList.add('hidden'));
$('#year').textContent = new Date().getFullYear();
saveWishlist();
renderWishlist();
loadCatalog();
