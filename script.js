document.addEventListener('DOMContentLoaded', () => {

    // --- Mobile Hamburger ---
    const navToggle = document.querySelector('.mobile-nav-toggle');
    const primaryNav = document.getElementById('primary-navigation');

    if (navToggle && primaryNav) {
        navToggle.addEventListener('click', () => {
            const isVisible = primaryNav.getAttribute('data-visible') === 'true';
            
            if (isVisible) {
                primaryNav.setAttribute('data-visible', false);
                navToggle.setAttribute('aria-expanded', false);
            } else {
                primaryNav.setAttribute('data-visible', true);
                navToggle.setAttribute('aria-expanded', true);
            }
        });
    }
    
    // --- Typed.js animation for Home page ---
    if (document.getElementById('typed-element')) {
        const options = {
            strings: ["aceum", "a scouting analyst", "a data analyst"],
            typeSpeed: 70,
            backSpeed: 50,
            backDelay: 1500,
            startDelay: 500,
            loop: true,
            showCursor: true,
            cursorChar: '|',
        };
        const typed = new Typed('#typed-element', options);
    }
    
    // --- Work Page Filter and Modal Logic ---
    const filterContainer = document.querySelector('.work-filters');
    if (filterContainer) {
        const workGrid = document.querySelector('.work-grid');
        const filterBtns = filterContainer.querySelectorAll('.filter-btn');
        const workItems = document.querySelectorAll('.work-item');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const filterValue = btn.getAttribute('data-filter');
                workGrid.style.height = workGrid.offsetHeight + 'px';
                workItems.forEach(item => {
                    item.style.display = 'none';
                });
                setTimeout(() => {
                    workItems.forEach(item => {
                        if (item.dataset.category === filterValue || filterValue === 'all') {
                            item.style.display = 'block';
                        }
                    });
                    workGrid.style.height = null;
                }, 150);
            });
        });
    }

    // Modals
    const previewBtns = document.querySelectorAll('.preview-btn[data-modal-target]');
    const modals = document.querySelectorAll('.modal');
    const closeBtns = document.querySelectorAll('.close-btn');

    previewBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const modalId = btn.getAttribute('data-modal-target');
            const modal = document.getElementById(modalId);
            if (modal) {
                openModal(modal);
            }
        });
    });

    const openModal = (modal) => {
        modal.style.display = 'block';
        setTimeout(() => modal.classList.add('show'), 10);
        initializeSlider(modal);
    };

    const closeModal = (modal) => {
        modal.classList.remove('show');
        setTimeout(() => modal.style.display = 'none', 300);
    };

    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            closeModal(btn.closest('.modal'));
        });
    });

    window.addEventListener('click', (e) => {
        modals.forEach(modal => {
            if (e.target === modal) {
                closeModal(modal);
            }
        });
    });

    // Modal image slider
    const initializeSlider = (modal) => {
        const sliders = modal.querySelectorAll('.modal-slider');
        sliders.forEach(slider => {
            const images = slider.querySelectorAll('.slider-images img');
            const prevArrow = slider.querySelector('.prev-arrow');
            const nextArrow = slider.querySelector('.next-arrow');
            let currentIndex = 0;

            if (images.length <= 1) {
                if(prevArrow) prevArrow.style.display = 'none';
                if(nextArrow) nextArrow.style.display = 'none';
                return;
            } else {
                 if(prevArrow) prevArrow.style.display = 'flex';
                if(nextArrow) nextArrow.style.display = 'flex';
            }

            const showSlide = (index) => {
                images.forEach((img, i) => {
                    img.classList.remove('active-slide');
                    if (i === index) {
                        img.classList.add('active-slide');
                    }
                });
            };

            if(prevArrow) {
                prevArrow.onclick = () => {
                    currentIndex = (currentIndex > 0) ? currentIndex - 1 : images.length - 1;
                    showSlide(currentIndex);
                };
            }
            
            if(nextArrow) {
                nextArrow.onclick = () => {
                    currentIndex = (currentIndex < images.length - 1) ? currentIndex + 1 : 0;
                    showSlide(currentIndex);
                };
            }
            
            showSlide(currentIndex);
        });
    };

    // --- Tap-to-display on Mob ---
    const workItems = document.querySelectorAll('.work-item');
    if (workItems.length > 0) {
        workItems.forEach(item => {
            item.addEventListener('click', function(event) {
                event.stopPropagation();
                const wasActive = this.classList.contains('is-active');
                workItems.forEach(i => i.classList.remove('is-active'));
                if (!wasActive) {
                    this.classList.add('is-active');
                }
            });
        });
    }

    const timelineItems = document.querySelectorAll('.team-history li');
    if (timelineItems.length > 0) {
        timelineItems.forEach(item => {
            item.addEventListener('click', function(event) {
                event.stopPropagation();
                const wasActive = this.classList.contains('is-active');
                timelineItems.forEach(i => i.classList.remove('is-active'));
                if (!wasActive) {
                    this.classList.add('is-active');
                }
            });
        });
    }

    // general click listener
    document.addEventListener('click', function() {
        if (workItems.length > 0) {
            workItems.forEach(i => i.classList.remove('is-active'));
        }
        if (timelineItems.length > 0) {
            timelineItems.forEach(i => i.classList.remove('is-active'));
        }
    });

});