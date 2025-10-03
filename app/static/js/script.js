document.addEventListener('DOMContentLoaded', function() {
    // Initialize map (in a real app, this would use Leaflet or Google Maps)
    const mapContainer = document.getElementById('locationsMap');
    if (mapContainer) {
        // This is where you would initialize your map library
        console.log('Map container ready for initialization');
    }

    // Location card click handlers
    const locationCards = document.querySelectorAll('.location-card');
    locationCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on an action button
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                return;
            }
            
            const locationName = this.querySelector('h3').textContent;
            console.log(`Viewing details for ${locationName}`);
            // In real implementation, this would open a detail view or modal
        });
    });

    // Filter functionality
    const searchInput = document.querySelector('.location-search input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            filterLocations(searchTerm);
        });
    }

    function filterLocations(searchTerm) {
        locationCards.forEach(card => {
            const locationName = card.querySelector('h3').textContent.toLowerCase();
            const locationId = card.querySelector('.detail-value').textContent.toLowerCase();
            
            if (locationName.includes(searchTerm) || locationId.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // Export button
    const exportBtn = document.querySelector('button:has(.ri-download-line)');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            alert('Exporting location data...');
            // In real implementation, this would generate a CSV or PDF
        });
    }

    // Add location button
    const addLocationBtn = document.querySelector('button:has(.ri-add-line)');
    if (addLocationBtn) {
        addLocationBtn.addEventListener('click', function() {
            console.log('Opening add location form');
            // In real implementation, this would open a modal form
        });
    }
});

//     document.addEventListener('DOMContentLoaded', function() {
//     // Toggle camera registration form
//     const addCameraBtn = document.querySelector('button:has(.ri-add-line)');
//     const cancelRegistrationBtn = document.getElementById('cancelRegistration');
//     const registrationForm = document.getElementById('cameraRegistrationForm');
    
//     if (addCameraBtn && registrationForm) {
//         addCameraBtn.addEventListener('click', function() {
//             registrationForm.classList.remove('hidden');
//             window.scrollTo({
//                 top: registrationForm.offsetTop - 20,
//                 behavior: 'smooth'
//             });
//         });
//     }
    
//     if (cancelRegistrationBtn && registrationForm) {
//         cancelRegistrationBtn.addEventListener('click', function() {
//             registrationForm.classList.add('hidden');
//         });
//     }

//     // Test RTSP stream buttons
//     const testRtspButtons = document.querySelectorAll('.rtsp-test-btn');
//     testRtspButtons.forEach(button => {
//         button.addEventListener('click', function(e) {
//             e.stopPropagation();
//             const cameraCard = this.closest('.camera-card');
//             const cameraId = cameraCard.querySelector('h3').textContent;
//             alert(`Testing RTSP stream for ${cameraId}`);
//             // In real implementation, this would ping the camera stream
//         });
//     });

// });

document.addEventListener('DOMContentLoaded', function() {
    // Initialize signal timing chart
    const signalTimingChart = echarts.init(document.getElementById('signalTimingChart'));
    const option = {
        animation: false,
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            borderColor: '#e2e8f0',
            textStyle: {
                color: '#1f2937'
            }
        },
        legend: {
            data: ['North-South Green', 'East-West Green', 'Cycle Length'],
            textStyle: {
                color: '#1f2937'
            },
            right: 0
        },
        grid: {
            left: '3%',
            right: '3%',
            bottom: '3%',
            top: '15%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: ['6a', '7a', '8a', '9a', '10a', '11a', '12p', '1p', '2p', '3p', '4p', '5p', '6p'],
            axisLine: {
                lineStyle: {
                    color: '#e2e8f0'
                }
            },
            axisLabel: {
                color: '#64748b'
            }
        },
        yAxis: {
            type: 'value',
            name: 'Seconds',
            axisLine: {
                show: false
            },
            axisLabel: {
                color: '#64748b'
            },
            splitLine: {
                lineStyle: {
                    color: '#e2e8f0'
                }
            }
        },
        series: [
            {
                name: 'North-South Green',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: 'rgba(16, 185, 129, 1)'
                },
                symbol: 'none',
                data: [40, 45, 50, 45, 40, 40, 40, 40, 40, 40, 40, 45, 50]
            },
            {
                name: 'East-West Green',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: 'rgba(239, 68, 68, 1)'
                },
                symbol: 'none',
                data: [30, 25, 20, 25, 30, 30, 30, 30, 30, 30, 30, 25, 20]
            },
            {
                name: 'Cycle Length',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 2,
                    color: 'rgba(59, 130, 246, 1)',
                    type: 'dashed'
                },
                symbol: 'none',
                data: [120, 120, 130, 120, 120, 120, 120, 120, 120, 120, 120, 120, 130]
            }
        ]
    };
    signalTimingChart.setOption(option);
    window.addEventListener('resize', function() {
        signalTimingChart.resize();
    });

    // Signal box interactions
    const signalBoxes = document.querySelectorAll('.signal-box');
    signalBoxes.forEach(box => {
        box.addEventListener('click', function() {
            const direction = this.getAttribute('data-direction');
            alert(`Showing detailed controls for ${direction} signal`);
        });
    });

    // Control mode buttons
    const controlModeButtons = document.querySelectorAll('.flex.items-center.space-x-3 button');
    controlModeButtons.forEach(button => {
        button.addEventListener('click', function() {
            controlModeButtons.forEach(btn => {
                btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'text-primary');
                btn.classList.add('border-slate-200');
            });
            
            if (this.textContent === 'AI Auto') {
                this.classList.add('bg-primary', 'text-white');
                this.classList.remove('border-slate-200');
            } else {
                this.classList.add('border-primary', 'text-primary');
                this.classList.remove('border-slate-200');
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {

    // Form input listeners for live preview
    const previewFields = [
        { input: 'location-name', preview: 'preview-name' },
        { input: 'location-id', preview: 'preview-id' },
        { input: 'location-zone', preview: 'preview-zone' },
        { input: 'location-country', preview: 'preview-country' },
        { input: 'location-address', preview: 'preview-address' }
    ];
    
    previewFields.forEach(field => {
        const inputElement = document.getElementById(field.input);
        if (inputElement) {
            inputElement.addEventListener('input', updatePreview);
        }
    });
    
    // Coordinate inputs
    const latInput = document.getElementById('location-lat');
    const lngInput = document.getElementById('location-lng');
    
    if (latInput && lngInput) {
        latInput.addEventListener('input', updateCoordinatesPreview);
        lngInput.addEventListener('input', updateCoordinatesPreview);
    }
    
    // Map click handler (simulated)
    const mapPreview = document.querySelector('.map-preview');
    if (mapPreview) {
        mapPreview.addEventListener('click', function(e) {
            // In a real app, this would get actual coordinates from the map click
            const lat = (Math.random() * 180 - 90).toFixed(6);
            const lng = (Math.random() * 360 - 180).toFixed(6);
            
            latInput.value = lat;
            lngInput.value = lng;
            
            updateCoordinatesPreview();
        });
    }
    
    // Update preview function
    function updatePreview() {
        previewFields.forEach(field => {
            const inputElement = document.getElementById(field.input);
            const previewElement = document.getElementById(field.preview);
            
            if (inputElement && previewElement) {
                if (inputElement.tagName === 'SELECT') {
                    const selectedOption = inputElement.options[inputElement.selectedIndex];
                    previewElement.textContent = selectedOption.text;
                } else {
                    previewElement.textContent = inputElement.value || '-';
                }
            }
        });
        
        // Update location type in preview
        const selectedType = document.querySelector('.location-type-option.selected');
        if (selectedType) {
            document.getElementById('preview-type').textContent = 
                selectedType.querySelector('h3').textContent;
        }
    }
    
    function updateCoordinatesPreview() {
        const lat = latInput.value;
        const lng = lngInput.value;
        
        if (lat && lng) {
            document.getElementById('preview-coords').textContent = `${lat}, ${lng}`;
        } else {
            document.getElementById('preview-coords').textContent = '-';
        }
    }
    
    // Initialize preview
    updatePreview();
});

document.addEventListener('DOMContentLoaded', function() {
    // Navigation functionality
    const navItems = document.querySelectorAll('.settings-nav-item');
    const sections = document.querySelectorAll('.settings-section, .danger-zone');
    
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            
            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');
            
            // Scroll to section
            const targetSection = document.getElementById(targetId);
            if (targetSection) {
                window.scrollTo({
                    top: targetSection.offsetTop - 100,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Copy API key functionality
    const copyApiKeyBtn = document.querySelector('button:has(.ri-file-copy-line)');
    if (copyApiKeyBtn) {
        copyApiKeyBtn.addEventListener('click', function() {
            const apiKey = document.querySelector('.api-key-value').textContent;
            navigator.clipboard.writeText(apiKey).then(() => {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="ri-check-line mr-1"></i> Copied';
                this.classList.remove('bg-blue-100', 'text-blue-700', 'hover:bg-blue-200');
                this.classList.add('bg-green-100', 'text-green-700', 'hover:bg-green-200');
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.classList.remove('bg-green-100', 'text-green-700', 'hover:bg-green-200');
                    this.classList.add('bg-blue-100', 'text-blue-700', 'hover:bg-blue-200');
                }, 2000);
            });
        });
    }

    // Toggle switches functionality
    const toggleSwitches = document.querySelectorAll('.custom-switch input[type="checkbox"]');
    toggleSwitches.forEach(switchEl => {
        switchEl.addEventListener('change', function() {
            const settingName = this.closest('.setting-item').querySelector('.setting-label label').textContent;
            console.log(`${settingName} changed to: ${this.checked ? 'ON' : 'OFF'}`);
            // In real implementation, this would save to backend
        });
    });

    // Save changes button
    const saveBtn = document.querySelector('button:has(.ri-save-line)');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            // Show loading state
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="ri-loader-4-line animate-spin mr-2"></i> Saving...';
            this.disabled = true;
            
            // Simulate API call
            setTimeout(() => {
                this.innerHTML = originalText;
                this.disabled = false;
                
                // Show success message
                const alertDiv = document.createElement('div');
                alertDiv.className = 'fixed top-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-lg shadow-lg z-50';
                alertDiv.innerHTML = '<div class="flex items-center"><i class="ri-checkbox-circle-line mr-2"></i> <span>All changes saved successfully</span></div>';
                document.body.appendChild(alertDiv);
                
                setTimeout(() => {
                    alertDiv.remove();
                }, 3000);
            }, 1000);
        });
    }

    // Danger zone buttons
    const dangerZoneBtns = document.querySelectorAll('.danger-zone button');
    dangerZoneBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const action = this.textContent.trim();
            if (confirm(`Are you absolutely sure you want to ${action}? This action cannot be undone and will affect all users.`)) {
                // Show loading state
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="ri-loader-4-line animate-spin mr-2"></i> Processing...';
                this.disabled = true;
                
                // Simulate API call
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                    alert(`${action} has been initiated. This may take several minutes to complete.`);
                }, 1500);
            }
        });
    });
    
    // Active section detection for navigation
    function updateActiveNav() {
        const scrollPosition = window.scrollY + 150;
        
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            
            if (scrollPosition >= sectionTop && scrollPosition < sectionTop + sectionHeight) {
                const id = section.getAttribute('id');
                navItems.forEach(nav => {
                    nav.classList.remove('active');
                    if (nav.getAttribute('href') === `#${id}`) {
                        nav.classList.add('active');
                    }
                });
            }
        });
    }
    
    window.addEventListener('scroll', updateActiveNav);
    
    // Team Member Modal Functionality
    const addTeamMemberBtn = document.getElementById('add-team-member-btn');
    const addTeamMemberModal = document.getElementById('add-team-member-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const cancelAddMemberBtn = document.getElementById('cancel-add-member');
    const submitAddMemberBtn = document.getElementById('submit-add-member');
    const addTeamMemberForm = document.getElementById('add-team-member-form');
    
    // Open modal
    addTeamMemberBtn.addEventListener('click', function() {
        addTeamMemberModal.classList.remove('hidden');
        setTimeout(() => {
            addTeamMemberModal.classList.add('show');
        }, 10);
    });
    
    // Close modal functions
    function closeModal() {
        addTeamMemberModal.classList.remove('show');
        setTimeout(() => {
            addTeamMemberModal.classList.add('hidden');
        }, 300);
    }
    
    closeModalBtn.addEventListener('click', closeModal);
    cancelAddMemberBtn.addEventListener('click', closeModal);
    
    // Close modal when clicking outside
    addTeamMemberModal.addEventListener('click', function(e) {
        if (e.target === addTeamMemberModal) {
            closeModal();
        }
    });
    
    // Submit form
    submitAddMemberBtn.addEventListener('click', function() {
        // Validate form
        if (!addTeamMemberForm.checkValidity()) {
            addTeamMemberForm.reportValidity();
            return;
        }
        
        // Get form values
        const name = document.getElementById('member-name').value;
        const email = document.getElementById('member-email').value;
        const role = document.getElementById('member-role').value;
        const department = document.getElementById('member-department').value;
        
        // Show loading state
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="ri-loader-4-line animate-spin mr-2"></i> Adding...';
        this.disabled = true;
        
        // Simulate API call
        setTimeout(() => {
            // Reset button
            this.innerHTML = originalText;
            this.disabled = false;
            
            // Close modal
            closeModal();
            
            // Show success message
            const alertDiv = document.createElement('div');
            alertDiv.className = 'fixed top-4 right-4 bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded-lg shadow-lg z-50';
            alertDiv.innerHTML = `<div class="flex items-center"><i class="ri-checkbox-circle-line mr-2"></i> <span>Invitation sent to ${name}</span></div>`;
            document.body.appendChild(alertDiv);
            
            // Add new team member to the list (in a real app, this would come from the backend)
            const teamMembersContainer = document.querySelector('#team-management .team-member:last-child').parentNode;
            const newMemberHTML = `
                <div class="team-member">
                    <div class="team-member-avatar">
                        <i class="ri-user-line"></i>
                    </div>
                    <div class="flex-1">
                        <h3 class="text-sm font-medium">${name}</h3>
                        <p class="text-xs text-slate-500">${role}</p>
                    </div>
                    <div class="text-xs text-slate-500 mr-4">Invitation sent</div>
                    <button class="text-slate-400 hover:text-primary transition-colors">
                        <i class="ri-more-2-line"></i>
                    </button>
                </div>
            `;
            
            teamMembersContainer.insertAdjacentHTML('beforeend', newMemberHTML);
            
            // Reset form
            addTeamMemberForm.reset();
            
            // Remove success message after 3 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 3000);
        }, 1500);
    });
});