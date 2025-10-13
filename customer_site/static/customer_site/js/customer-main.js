/**
 * Main JavaScript for Admos Place Customer Website
 */

$(document).ready(function() {
    // Initialize all components
    initializeNavigation();
    initializeCart();
    initializeNotifications();
    initializeModals();
    
    // Update cart count on page load
    updateCartCount();
});

/**
 * Navigation functionality
 */
function initializeNavigation() {
    // Mobile menu toggle
    $('.mobile-menu-toggle').click(function() {
        $('.nav-menu').toggleClass('active');
    });
    
    // Close mobile menu when clicking outside
    $(document).click(function(e) {
        if (!$(e.target).closest('.navbar').length) {
            $('.nav-menu').removeClass('active');
        }
    });
    
    // Profile dropdown functionality
    initializeProfileDropdown();
    
    // Smooth scrolling for anchor links
    $('a[href^="#"]').click(function(e) {
        const href = this.getAttribute('href');
        if (href && href !== '#') {
            e.preventDefault();
            const target = $(href);
            if (target.length) {
                $('html, body').animate({
                    scrollTop: target.offset().top - 80
                }, 500);
            }
        }
    });
}

/**
 * Profile dropdown functionality
 */
function initializeProfileDropdown() {
    // Handle profile button clicks (both desktop and mobile)
    $('#profile-btn, #profile-btn-mobile').click(function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const $dropdown = $(this).siblings('.profile-dropdown');
        const $allDropdowns = $('.profile-dropdown');
        
        // Close all other dropdowns
        $allDropdowns.not($dropdown).removeClass('show');
        
        // Toggle current dropdown
        $dropdown.toggleClass('show');
    });
    
    // Close dropdown when clicking outside
    $(document).click(function(e) {
        if (!$(e.target).closest('.user-profile-container').length) {
            $('.profile-dropdown').removeClass('show');
        }
    });
    
    // Close dropdown when pressing escape key
    $(document).keyup(function(e) {
        if (e.keyCode === 27) { // Escape key
            $('.profile-dropdown').removeClass('show');
        }
    });
    
    // Prevent dropdown from closing when clicking inside it
    $('.profile-dropdown').click(function(e) {
        e.stopPropagation();
    });
}

/**
 * Cart functionality
 */
function initializeCart() {
    // Add to cart buttons
    $(document).on('click', '.add-to-cart-btn', function(e) {
        e.preventDefault();
        const itemId = $(this).data('item-id');
        const quantity = 1;
        
        addToCart(itemId, quantity, $(this));
    });
    
    // Update cart item quantity - handled by cart template
    // $(document).on('click', '.quantity-btn', function(e) {
    //     e.preventDefault();
    //     const $btn = $(this);
    //     const $item = $btn.closest('.cart-item');
    //     const itemId = $item.data('item-id');
    //     const currentQuantity = parseInt($item.find('.quantity-display').text());
    //     
    //     let newQuantity = currentQuantity;
    //     if ($btn.find('.fa-plus').length) {
    //         newQuantity = currentQuantity + 1;
    //     } else if ($btn.find('.fa-minus').length) {
    //         newQuantity = Math.max(1, currentQuantity - 1);
    //     }
    //     
    //     updateCartItem(itemId, newQuantity);
    // });
    
    // Remove item from cart - handled by cart template
    // $(document).on('click', '.remove-item-btn', function(e) {
    //     e.preventDefault();
    //     const itemId = $(this).data('item-id');
    //     
    //     if (confirm('Are you sure you want to remove this item from your cart?')) {
    //         removeFromCart(itemId);
    //     }
    // });
}

/**
 * Add item to cart
 */
function addToCart(itemId, quantity, $button) {
    if (!$button) {
        $button = $(`.add-to-cart-btn[data-item-id="${itemId}"]`);
    }
    
    // Show loading state
    const originalText = $button.html();
    $button.html('<i class="fas fa-spinner fa-spin"></i> Adding...');
    $button.prop('disabled', true);
    
    // Make AJAX request
    $.ajax({
        url: '/api/add-to-cart/',
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        },
        contentType: 'application/json',
        data: JSON.stringify({
            item_id: itemId,
            quantity: quantity
        }),
        success: function(response) {
            if (response.success) {
                // Update cart count
                updateCartCount(response.cart_count);
                
                // Show success notification
                showNotification(response.message, 'success');
                
                // Update button state
                $button.html('<i class="fas fa-check"></i> Added!');
                setTimeout(() => {
                    $button.html(originalText);
                    $button.prop('disabled', false);
                }, 2000);
            } else {
                showNotification(response.message, 'error');
                $button.html(originalText);
                $button.prop('disabled', false);
            }
        },
        error: function(xhr, status, error) {
            console.error('Add to cart error:', error);
            showNotification('Something went wrong. Please try again.', 'error');
            $button.html(originalText);
            $button.prop('disabled', false);
        }
    });
}

/**
 * Update cart item quantity
 */
function updateCartItem(itemId, quantity, plates) {
    const requestData = {
        item_id: itemId
    };
    
    // Add quantity or plates based on what's provided
    if (quantity !== undefined) {
        requestData.quantity = quantity;
    }
    if (plates !== undefined) {
        requestData.plates = plates;
    }
    
    $.ajax({
        url: '/api/update-cart/',
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        },
        contentType: 'application/json',
        data: JSON.stringify(requestData),
        success: function(response) {
            if (response.success) {
                // Update cart count
                updateCartCount(response.cart_count);
                
                // Reload page to update totals
                if (window.location.pathname.includes('/cart/')) {
                    location.reload();
                }
            } else {
                showNotification(response.message || 'Failed to update quantity', 'error');
            }
        },
        error: function(xhr, status, error) {
            console.error('Update cart error:', error);
            showNotification('Something went wrong. Please try again.', 'error');
        }
    });
}

/**
 * Remove item from cart
 */
function removeFromCart(itemId) {
    $.ajax({
        url: '/api/remove-from-cart/',
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        },
        contentType: 'application/json',
        data: JSON.stringify({
            item_id: itemId
        }),
        success: function(response) {
            if (response.success) {
                // Update cart count
                updateCartCount(response.cart_count);
                
                // Remove item from DOM
                $(`.cart-item[data-item-id="${itemId}"]`).fadeOut(function() {
                    $(this).remove();
                    
                    // Check if cart is empty
                    if ($('.cart-item').length === 0 && window.location.pathname.includes('/cart/')) {
                        location.reload();
                    }
                });
                
                showNotification('Item removed from cart', 'success');
            } else {
                showNotification('Failed to remove item', 'error');
            }
        },
        error: function(xhr, status, error) {
            console.error('Remove from cart error:', error);
            showNotification('Something went wrong. Please try again.', 'error');
        }
    });
}

/**
 * Update cart count display
 */
function updateCartCount(count) {
    if (count !== undefined) {
        // Update all cart count elements (both desktop and mobile)
        $('.cart-count').text(count);
    } else {
        // Fetch current cart count from server
        $.ajax({
            url: '/api/cart-count/',
            method: 'GET',
            success: function(response) {
                // Update all cart count elements (both desktop and mobile)
                $('.cart-count').text(response.count || 0);
            },
            error: function() {
                // Fallback to session storage or default for all cart count elements
                const storedCount = sessionStorage.getItem('cart_count') || 0;
                $('.cart-count').text(storedCount);
            }
        });
    }
}

/**
 * Notification system
 */
function initializeNotifications() {
    // Auto-hide existing notifications
    setTimeout(() => {
        $('.alert').fadeOut();
    }, 5000);
}

function showNotification(message, type = 'info') {
    const iconClass = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';
    
    const notification = $(`
        <div class="notification notification-${type}">
            <i class="fas ${iconClass}"></i>
            <span>${message}</span>
            <button class="notification-close" onclick="$(this).parent().fadeOut()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `);
    
    $('body').append(notification);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        notification.fadeOut(() => notification.remove());
    }, 5000);
}

/**
 * Modal functionality
 */
function initializeModals() {
    // Close modal when clicking outside
    $(document).click(function(e) {
        if ($(e.target).hasClass('modal')) {
            closeModal();
        }
    });
    
    // Close modal with escape key
    $(document).keyup(function(e) {
        if (e.keyCode === 27) { // Escape key
            closeModal();
        }
    });
}

function openModal(modalId) {
    $(`#${modalId}`).addClass('active');
    $('body').addClass('modal-open');
}

function closeModal() {
    $('.modal').removeClass('active');
    $('body').removeClass('modal-open');
}

/**
 * Form validation
 */
function validateForm(formSelector) {
    const $form = $(formSelector);
    let isValid = true;
    
    // Clear previous errors
    $form.find('.error-message').remove();
    $form.find('.form-group').removeClass('error');
    
    // Validate required fields
    $form.find('[required]').each(function() {
        const $field = $(this);
        const value = $field.val().trim();
        
        if (!value) {
            showFieldError($field, 'This field is required');
            isValid = false;
        }
    });
    
    // Validate email fields
    $form.find('input[type="email"]').each(function() {
        const $field = $(this);
        const value = $field.val().trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        
        if (value && !emailRegex.test(value)) {
            showFieldError($field, 'Please enter a valid email address');
            isValid = false;
        }
    });
    
    // Validate phone fields
    $form.find('input[type="tel"]').each(function() {
        const $field = $(this);
        const value = $field.val().trim();
        const phoneRegex = /^[\+]?[0-9\s\-\(\)]{10,}$/;
        
        if (value && !phoneRegex.test(value)) {
            showFieldError($field, 'Please enter a valid phone number');
            isValid = false;
        }
    });
    
    return isValid;
}

function showFieldError($field, message) {
    const $formGroup = $field.closest('.form-group');
    $formGroup.addClass('error');
    
    const errorMessage = $(`<div class="error-message">${message}</div>`);
    $formGroup.append(errorMessage);
}

/**
 * Utility functions
 */
function getCSRFToken() {
    // Try to get CSRF token from meta tag
    let token = $('meta[name="csrf-token"]').attr('content');
    
    // If not found, try to get from cookie
    if (!token) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                token = value;
                break;
            }
        }
    }
    
    return token;
}

function formatPrice(price) {
    return new Intl.NumberFormat('en-NG', {
        style: 'currency',
        currency: 'NGN',
        minimumFractionDigits: 0
    }).format(price);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-NG', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Search functionality
 */
function initializeSearch() {
    const $searchInput = $('.search-input');
    const $searchBar = $('.search-bar');
    
    if ($searchInput.length && $searchBar.length) {
        // Handle search bar active state
        $searchInput.on('focus', function() {
            $searchBar.addClass('active');
            // Don't hide menu content on focus - let search results show
        });
        
        $searchInput.on('blur', function() {
            // Only remove active state if input is empty
            if ($(this).val().trim() === '') {
                $searchBar.removeClass('active');
                showMenuContent();
            }
        });
        
        // Keep active state if there's content
        $searchInput.on('input', function() {
            if ($(this).val().trim() !== '') {
                $searchBar.addClass('active');
                // Don't hide menu content - let search results show
            } else {
                $searchBar.removeClass('active');
                showMenuContent();
            }
        });
        
        const debouncedSearch = debounce(function() {
            const query = $searchInput.val().trim();
            if (query.length >= 2) {
                performSearch(query);
            } else {
                clearSearchResults();
            }
        }, 300);
        
        $searchInput.on('input', debouncedSearch);
    }
}

function performSearch(query) {
    // Get all menu items (both homepage and menu page)
    const $menuItems = $('.menu-item-card, .item-card');
    
    console.log('Searching for:', query);
    console.log('Total items found:', $menuItems.length);
    
    if (query.length >= 2) {
        let matchCount = 0;
        
        // First, hide ALL items
        $menuItems.removeClass('show');
        $menuItems.css('display', 'none');
        $menuItems.css('opacity', '0');
        
        // Special test case - show all items if searching for "showall"
        if (query.toLowerCase() === 'showall') {
            $menuItems.each(function() {
                const $item = $(this);
                $item.addClass('show');
                $item.css({
                    'display': 'flex !important',
                    'opacity': '1 !important',
                    'visibility': 'visible !important',
                    'transform': 'translateY(0) !important'
                });
                matchCount++;
            });
        } else {
            // Show only matching items
            $menuItems.each(function() {
                const $item = $(this);
                
                // Try different selectors for item name
                let itemName = '';
                if ($item.find('.menu-item-name').length) {
                    itemName = $item.find('.menu-item-name').text().toLowerCase();
                } else if ($item.find('.item-name').length) {
                    itemName = $item.find('.item-name').text().toLowerCase();
                } else if ($item.find('h3').length) {
                    itemName = $item.find('h3').text().toLowerCase();
                }
                
                const itemCategory = $item.data('category') ? $item.data('category').toLowerCase() : '';
                
                console.log(`Checking item: "${itemName}" in category: "${itemCategory}"`);
                
                // Check if query matches item name or category
                if (itemName.includes(query.toLowerCase()) || itemCategory.includes(query.toLowerCase())) {
                    $item.addClass('show');
                    $item.css({
                        'display': 'flex !important',
                        'opacity': '1 !important',
                        'visibility': 'visible !important',
                        'transform': 'translateY(0) !important'
                    });
                    matchCount++;
                    console.log(`✓ Match found: "${itemName}"`);
                }
            });
        }
        
        console.log(`Total matches: ${matchCount}`);
        
        // Hide category filters during search
        $('.category-section').hide();
        
        // Ensure menu content is visible to show search results
        $('.menu-content').show();
        
    } else {
        // Clear search and show all items
        clearSearchResults();
    }
}

function clearSearchResults() {
    // Clear search results and restore category filter
    // Show category filters again
    $('.category-section').show();
    
    // Remove search results indicator
    $('.search-results-indicator').remove();
    
    // Ensure menu content is visible
    $('.menu-content').show();
    
    // Restore the saved category filter
    const savedCategory = localStorage.getItem('selectedCategory') || 'all';
    applyCategoryFilter(savedCategory);
}

function showSearchResults(query) {
    // Remove existing search results indicator
    $('.search-results-indicator').remove();
    
    // Count visible items
    const visibleItems = $('.menu-item-card.show').length;
    
    // Create search results indicator
    const searchIndicator = $(`
        <div class="search-results-indicator">
            <div class="container">
                <p>Found ${visibleItems} result${visibleItems !== 1 ? 's' : ''} for "${query}"</p>
                <button class="clear-search-btn" onclick="clearSearch()">
                    <i class="fas fa-times"></i> Clear Search
                </button>
            </div>
        </div>
    `);
    
    // Insert after category section
    $('.category-section').after(searchIndicator);
}

function clearSearch() {
    // Clear the search input
    $('.search-input').val('');
    
    // Remove active state from search bar
    $('.search-bar').removeClass('active');
    
    // Clear search results
    clearSearchResults();
    
    // Show menu content again
    showMenuContent();
}

function applyCategoryFilter(category) {
    // Update active button
    $('.filter-btn').removeClass('active');
    $(`.filter-btn[data-category="${category}"]`).addClass('active');
    
    // Filter items using CSS classes for smooth transitions (both homepage and menu page)
    const $allItems = $('.menu-item-card, .item-card');
    
    if (category === 'all') {
        $allItems.removeClass('show').addClass('show');
    } else {
        $allItems.removeClass('show');
        $(`.menu-item-card[data-category="${category}"], .item-card[data-category="${category}"]`).addClass('show');
    }
}

/**
 * Hide menu content when search is active
 */
function hideMenuContent() {
    $('.page-header, .category-section, .menu-content, .menu-page .page-header, .menu-page .category-section, .menu-page .menu-content').hide();
}

/**
 * Show menu content when search is inactive
 */
function showMenuContent() {
    $('.page-header, .category-section, .menu-content, .menu-page .page-header, .menu-page .category-section, .menu-page .menu-content').show();
}

/**
 * Lazy loading for images
 */
function initializeLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
}

/**
 * Initialize all components when DOM is ready
 */
$(document).ready(function() {
    initializeLazyLoading();
    initializeSearch();
    
    // Add loading states to forms (excluding modal forms that have their own handlers)
    $('form').on('submit', function() {
        const $form = $(this);
        const $submitBtn = $form.find('button[type="submit"]');
        
        // Skip modal forms that have their own submit handlers
        if ($form.attr('id') === 'loginForm' || 
            $form.attr('id') === 'createAccountForm' || 
            $form.attr('id') === 'otpForm') {
            return;
        }
        
        if ($submitBtn.length) {
            $submitBtn.prop('disabled', true);
            $submitBtn.html('<i class="fas fa-spinner fa-spin"></i> Processing...');
        }
    });
    
    // Add smooth transitions to all links
    $('a[href^="/"]').click(function(e) {
        const href = $(this).attr('href');
        if (href && !href.includes('#') && !$(this).hasClass('no-transition')) {
            $('body').addClass('page-transition');
        }
    });
});

/**
 * Page transition effects
 */
$(window).on('load', function() {
    $('body').removeClass('page-transition');
});

/**
 * Error handling
 */
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
    // You could send this to an error tracking service
});

/**
 * Service Worker registration (for PWA features)
 */
// Service worker registration removed to prevent console errors
