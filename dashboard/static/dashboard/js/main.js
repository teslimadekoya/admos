// Dashboard JavaScript functionality
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle functionality
    const menuToggleBtn = document.getElementById('menu-toggle-btn');
    const sidebar = document.getElementById('sidebar');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');

    if (menuToggleBtn && sidebar) {
        menuToggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });
    }

    if (closeSidebarBtn && sidebar) {
        closeSidebarBtn.addEventListener('click', function() {
            sidebar.classList.remove('active');
        });
    }

    // Close sidebar when clicking outside
    document.addEventListener('click', function(event) {
        if (sidebar && !sidebar.contains(event.target) && menuToggleBtn && !menuToggleBtn.contains(event.target)) {
            sidebar.classList.remove('active');
        }
    });

    // Responsive sidebar behavior
    function handleResize() {
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('active');
        }
    }

    window.addEventListener('resize', handleResize);
    handleResize(); // Initial check

    // Auto-submit form when category filter changes (but not for search input)
    const categoryFilter = document.querySelector('.category-filter');
    if (categoryFilter) {
        categoryFilter.addEventListener('change', function() {
            console.log('Category filter changed, submitting form');
            this.form.submit();
        });
    }
    
    // Prevent auto-submit for search input - require clicking search button
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                console.log('Enter pressed, submitting form');
                this.form.submit();
            }
        });
    }
    
    // Undo notification functionality
    const undoNotification = document.getElementById('undo-notification');
    const undoBtn = document.getElementById('undo-btn');
    const dismissBtn = document.getElementById('dismiss-undo');
    const undoMessage = document.querySelector('.undo-message');
    const undoProgress = document.querySelector('.undo-progress');
    
    let undoTimeout;
    let undoUrl;
    
    // Check for success messages that indicate a deletion
    const successMessages = document.querySelectorAll('.alert-success');
    console.log('Found success messages:', successMessages.length);
    
    successMessages.forEach(message => {
        const text = message.textContent;
        console.log('Success message text:', text);
        if (text.includes('deleted successfully')) {
            if (text.includes('Item')) {
                console.log('Showing item undo notification');
                showUndoNotification('Item deleted', '/dashboard/items/undo-delete/');
            } else if (text.includes('Category')) {
                console.log('Showing category undo notification');
                showUndoNotification('Category deleted', '/dashboard/categories/undo-delete/');
            }
        }
    });
    
    // Also check for success messages after a short delay (in case they're added dynamically)
    setTimeout(() => {
        const delayedMessages = document.querySelectorAll('.alert-success');
        delayedMessages.forEach(message => {
            const text = message.textContent;
            if (text.includes('deleted successfully')) {
                if (text.includes('Item')) {
                    console.log('Showing delayed item undo notification');
                    showUndoNotification('Item deleted', '/dashboard/items/undo-delete/');
                } else if (text.includes('Category')) {
                    console.log('Showing delayed category undo notification');
                    showUndoNotification('Category deleted', '/dashboard/categories/undo-delete/');
                }
            }
        });
    }, 100);
    
    // Watch for new success messages being added to the page
    const messagesContainer = document.querySelector('.messages');
    if (messagesContainer) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1 && node.classList && node.classList.contains('alert-success')) {
                            const text = node.textContent;
                            console.log('New success message detected:', text);
                            if (text.includes('deleted successfully')) {
                                if (text.includes('Item')) {
                                    console.log('Showing item undo notification from observer');
                                    showUndoNotification('Item deleted', '/dashboard/items/undo-delete/');
                                } else if (text.includes('Category')) {
                                    console.log('Showing category undo notification from observer');
                                    showUndoNotification('Category deleted', '/dashboard/categories/undo-delete/');
                                }
                            }
                        }
                    });
                }
            });
        });
        
        observer.observe(messagesContainer, { childList: true, subtree: true });
        console.log('Started watching for new success messages');
    }
    
    function showUndoNotification(message, url) {
        console.log('showUndoNotification called with:', message, url);
        console.log('undoNotification element:', undoNotification);
        console.log('undoMessage element:', undoMessage);
        
        if (!undoNotification || !undoMessage) {
            console.error('Undo notification elements not found!');
            return;
        }
        
        undoMessage.textContent = message;
        undoUrl = url;
        undoNotification.style.display = 'block';
        
        console.log('Undo notification should now be visible');
        
        // Reset progress bar animation
        if (undoProgress) {
            undoProgress.style.animation = 'none';
            undoProgress.offsetHeight; // Trigger reflow
            undoProgress.style.animation = 'countdown 30s linear forwards';
        }
        
        // Auto-hide after 30 seconds
        undoTimeout = setTimeout(() => {
            hideUndoNotification();
        }, 30000);
    }
    
    function hideUndoNotification() {
        undoNotification.style.display = 'none';
        if (undoTimeout) {
            clearTimeout(undoTimeout);
        }
    }
    
    // Undo button click
    if (undoBtn) {
        undoBtn.addEventListener('click', function() {
            if (undoUrl) {
                // Create a form to submit the undo request
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = undoUrl;
                
                // Add CSRF token
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
                if (csrfToken) {
                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrfmiddlewaretoken';
                    csrfInput.value = csrfToken.value;
                    form.appendChild(csrfInput);
                }
                
                document.body.appendChild(form);
                form.submit();
            }
        });
    }
    
    // Dismiss button click
    if (dismissBtn) {
        dismissBtn.addEventListener('click', hideUndoNotification);
    }
    
    // Test function - you can call this from browser console to test the undo notification
    window.testUndoNotification = function() {
        console.log('testUndoNotification called');
        showUndoNotification('Test Item deleted', '/dashboard/items/undo-delete/');
    };
    
    // Make sure the function is available globally
    console.log('Undo notification system loaded. testUndoNotification available:', typeof window.testUndoNotification);
});

// Global function for sorting orders
function changeSort(sortValue) {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.set('sort', sortValue);
    window.location.href = currentUrl.toString();
}
