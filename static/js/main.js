// Bitcoin Dada Certificate System - Enhanced JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize animations
    initAnimations();
    
    // Initialize tooltips
    initTooltips();
    
    // Initialize form enhancements
    initFormEnhancements();
    
    // Initialize Bitcoin timestamping features
    initBitcoinFeatures();
});

function initAnimations() {
    // Animate elements on scroll
    const animatedElements = document.querySelectorAll('.card, .stats-card, .feature-icon');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.1 });
    
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.6s ease-out';
        observer.observe(el);
    });
    
    // Add floating animation to Bitcoin icon
    const bitcoinIcon = document.querySelector('.bitcoin-float');
    if (bitcoinIcon) {
        bitcoinIcon.classList.add('animate-float');
    }
}

function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function initFormEnhancements() {
    // Add character counters
    const textInputs = document.querySelectorAll('input[type="text"], textarea');
    textInputs.forEach(input => {
        input.addEventListener('input', function() {
            if (this.maxLength > 0) {
                const counter = this.parentNode.querySelector('.char-counter') || 
                               createCharCounter(this);
                counter.textContent = `${this.value.length}/${this.maxLength}`;
            }
        });
    });
    
    // Enhanced file input
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileName = this.files[0]?.name || 'No file chosen';
            const label = this.parentNode.querySelector('.file-label') ||
                         createFileLabel(this);
            label.textContent = fileName;
        });
    });
}

function initBitcoinFeatures() {
    // Bitcoin timestamping confirmation
    const timestampButtons = document.querySelectorAll('.timestamp-bitcoin');
    timestampButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('This will timestamp the certificate to the Bitcoin blockchain. This action cannot be undone. Continue?')) {
                e.preventDefault();
            } else {
                showLoading('Timestamping to Bitcoin...');
            }
        });
    });
    
    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-copy-target');
            const targetElement = document.querySelector(targetId);
            
            if (targetElement) {
                navigator.clipboard.writeText(targetElement.textContent).then(() => {
                    showToast('Copied to clipboard!', 'success');
                }).catch(() => {
                    showToast('Failed to copy', 'error');
                });
            }
        });
    });
}

function createCharCounter(input) {
    const counter = document.createElement('div');
    counter.className = 'char-counter form-text text-end';
    counter.textContent = `0/${input.maxLength}`;
    input.parentNode.appendChild(counter);
    return counter;
}

function createFileLabel(input) {
    const label = document.createElement('div');
    label.className = 'file-label form-text';
    input.parentNode.appendChild(label);
    return label;
}

function showLoading(message = 'Loading...') {
    // Create loading overlay
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        color: white;
        font-size: 1.2rem;
    `;
    
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    
    const text = document.createElement('div');
    text.textContent = message;
    text.style.marginTop = '1rem';
    
    overlay.appendChild(spinner);
    overlay.appendChild(text);
    document.body.appendChild(overlay);
    
    return overlay;
}

function hideLoading(overlay) {
    if (overlay && overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
    }
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Bitcoin price ticker (optional feature)
function initBitcoinTicker() {
    const tickerElement = document.querySelector('#bitcoin-price-ticker');
    if (tickerElement) {
        fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')
            .then(response => response.json())
            .then(data => {
                const price = data.bitcoin.usd;
                tickerElement.innerHTML = `
                    <i class="fab fa-bitcoin me-1"></i>
                    BTC: $${price.toLocaleString()}
                `;
            })
            .catch(() => {
                tickerElement.innerHTML = `
                    <i class="fab fa-bitcoin me-1"></i>
                    Bitcoin: Network Secured
                `;
            });
    }
}

// Certificate verification enhancement
function enhanceVerification() {
    const verifyForm = document.querySelector('#verifyForm');
    if (verifyForm) {
        verifyForm.addEventListener('submit', function(e) {
            const certId = document.querySelector('#cert_id').value.trim();
            if (certId) {
                showLoading('Verifying certificate...');
            }
        });
    }
}

// Initialize when page loads
window.addEventListener('load', function() {
    initBitcoinTicker();
    enhanceVerification();
});

// Export functions for global access
window.BitcoinDada = {
    showLoading,
    hideLoading,
    showToast,
    initBitcoinTicker
};