document.addEventListener('DOMContentLoaded', function() {
            // Check if user is admin (this would typically come from your backend)
            // For demonstration, we'll use a URL parameter or randomize it
            const urlParams = new URLSearchParams(window.location.search);
            const isAdmin = urlParams.get('admin') === 'true' || Math.random() > 0.5;
            
            // Get DOM elements
            const adminBanner = document.getElementById('adminBanner');
            const settingsLink = document.getElementById('settingsLink');
            const userMenuButton = document.getElementById('userMenuButton');
            const userMenu = document.getElementById('userMenu');
            
            // Show/hide admin features based on user role
            if (isAdmin) {
                adminBanner.classList.remove('hidden');
                // For admins, we might show additional options
            } else {
                // For non-admin users, ensure settings link is visible
                settingsLink.style.display = 'flex';
            }
            
            // Toggle user menu
            userMenuButton.addEventListener('click', function(e) {
                e.stopPropagation();
                userMenu.classList.toggle('active');
            });
            
            // Close user menu when clicking elsewhere
            document.addEventListener('click', function() {
                userMenu.classList.remove('active');
            });
            
            // Prevent menu from closing when clicking inside it
            userMenu.addEventListener('click', function(e) {
                e.stopPropagation();
            });
            
            // Simple filter functionality
            const filterButtons = document.querySelectorAll('.filter-btn');
            const incidentCards = document.querySelectorAll('.incident-card');
            
            filterButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const filter = this.getAttribute('data-filter');
                    
                    // Remove active class from all buttons
                    filterButtons.forEach(btn => btn.classList.remove('bg-primary', 'text-white'));
                    // Add active class to clicked button
                    this.classList.add('bg-primary', 'text-white');
                    
                    // Filter incidents
                    incidentCards.forEach(card => {
                        if (filter === 'all') {
                            card.style.display = 'block';
                        } else {
                            const type = card.querySelector('.incident-type-badge').classList[1];
                            if (type === filter) {
                                card.style.display = 'block';
                            } else {
                                card.style.display = 'none';
                            }
                        }
                    });
                });
            });
        });