/* ============================================================
   UPSC DIGEST AGENT — Product Webpage JavaScript
   Handles: Scroll reveals, navbar behavior, mobile menu,
            smooth scrolling, counter animations
   ============================================================ */

(function () {
    'use strict';

    // ===== NAVBAR SCROLL BEHAVIOR =====
    const navbar = document.getElementById('navbar');
    let lastScrollY = 0;

    function handleNavbarScroll() {
        const currentScrollY = window.scrollY;
        if (currentScrollY > 40) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        lastScrollY = currentScrollY;
    }

    window.addEventListener('scroll', handleNavbarScroll, { passive: true });

    // ===== MOBILE MENU TOGGLE =====
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');

            // Toggle icon between menu and X
            const isOpen = navLinks.classList.contains('open');
            navToggle.innerHTML = isOpen
                ? '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
                : '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';
        });

        // Close menu when clicking a link
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('open');
                navToggle.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>';
            });
        });
    }

    // ===== SMOOTH SCROLLING =====
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const navHeight = navbar ? navbar.offsetHeight : 0;
                const targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });

    // ===== SCROLL REVEAL OBSERVER =====
    const revealElements = document.querySelectorAll('.reveal, .stagger');

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                // Don't unobserve — keeps animation from replaying
                // revealObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -60px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));

    // ===== COUNTER ANIMATION =====
    function animateCounter(element, target, duration = 1200) {
        const start = 0;
        const startTime = performance.now();
        const isNumber = !isNaN(parseInt(target));

        if (!isNumber) return;

        const targetNum = parseInt(target);

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out quad
            const eased = 1 - (1 - progress) * (1 - progress);
            const current = Math.floor(eased * targetNum);

            element.textContent = current + (target.includes('+') ? '+' : '');

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.textContent = target;
            }
        }

        requestAnimationFrame(update);
    }

    // Animate stat counters when hero is visible
    const heroStats = document.querySelectorAll('.hero__stat-value');
    let statsAnimated = false;

    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !statsAnimated) {
                statsAnimated = true;
                heroStats.forEach(stat => {
                    const text = stat.textContent.trim();
                    animateCounter(stat, text);
                });
            }
        });
    }, { threshold: 0.3 });

    if (heroStats.length > 0) {
        statsObserver.observe(heroStats[0].parentElement.parentElement);
    }

    // ===== PIPELINE NODE HOVER GLOW =====
    const pipelineNodes = document.querySelectorAll('.pipeline-node');
    pipelineNodes.forEach(node => {
        node.addEventListener('mouseenter', () => {
            node.style.boxShadow = '0 4px 20px rgba(59, 130, 246, 0.12), inset 0 1px 0 rgba(255,255,255,0.05)';
        });
        node.addEventListener('mouseleave', () => {
            node.style.boxShadow = '';
        });
    });

    // ===== PARALLAX EFFECT ON HERO VISUAL =====
    const heroVisual = document.querySelector('.hero__visual');
    if (heroVisual) {
        window.addEventListener('scroll', () => {
            const scrolled = window.scrollY;
            if (scrolled < 800) {
                const parallaxY = scrolled * 0.08;
                heroVisual.style.transform = `translateY(${parallaxY}px)`;
            }
        }, { passive: true });
    }

    // ===== MOUSE PARALLAX ON LAPTOP MOCKUP =====
    const laptopMockup = document.querySelector('.laptop-mockup');
    if (laptopMockup) {
        const hero = document.querySelector('.hero');
        hero.addEventListener('mousemove', (e) => {
            const rect = hero.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width - 0.5;
            const y = (e.clientY - rect.top) / rect.height - 0.5;

            laptopMockup.style.transform = `rotateY(${x * 5}deg) rotateX(${-y * 3}deg)`;
        });

        hero.addEventListener('mouseleave', () => {
            laptopMockup.style.transform = 'rotateY(0) rotateX(0)';
            laptopMockup.style.transition = 'transform 0.5s ease';
            setTimeout(() => {
                laptopMockup.style.transition = '';
            }, 500);
        });
    }

    // ===== INITIAL LUCIDE ICONS =====
    document.addEventListener('DOMContentLoaded', () => {
        if (window.lucide) {
            lucide.createIcons();
        }
    });

})();
